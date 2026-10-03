#!/usr/bin/env python3
"""quality.py — deterministic engine for the arkava-quality-checker gate.

Doctrine (inherited from pos.py / cyber.py): the LLM reads code and orchestrates;
verified code computes every metric, threshold, band, delta, waiver decision, and
the verdict. The model never decides whether a unit is over a complexity band —
this engine does, reproducibly, offline, stdlib-only.

Subcommands
  selftest                     10 embedded scenarios; last line "10/10 … ALL PASS"
  scan     --files … --json    native metrics (Python AST; generic line metrics)
  check    --scan … [--base-scan …] [--ingest tool:path …] [--model-findings …]
           [--policy …] [--waivers …] --json
                               policy join → clause verdicts → gate verdict
  policy   [--policy …]        print the effective policy (defaults ⊕ overrides)

Exit codes: scan/policy 0 ok, 2 operational failure.
            check 0 = MAINTAINABLE or CONDITIONAL-PASS, 1 = REWORK-REQUIRED,
            2 = operational failure (never a verdict).

Python 3.9+. UK English. No third-party imports.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import io
import json
import os
import re
import sys
import tokenize
from datetime import date, datetime

ENGINE_VERSION = "1.0.0"   # behaviour version — bump only on behaviour change
ENGINE_REVISED = "2026-08-03"  # date this file was last amended

# ---------------------------------------------------------------------------
# Default policy — thresholds carry their evidence base in references/
# evidence-base.md (SIG benchmark-derived risk bands via Alves et al. 2010;
# McCabe 1976 / NIST 500-235 CC guidance; SonarSource cognitive-complexity
# default 15; lint-ecosystem consensus for nesting/parameter counts).
# Overridable per repo via .arkava/quality-policy.json — overrides win.
# ---------------------------------------------------------------------------

DEFAULT_POLICY = {
    "bands": {
        # value >= medium → medium; >= high → high; >= very_high → very-high
        "unit_cyclomatic": {"medium": 11, "high": 16, "very_high": 26},
        "unit_cognitive": {"medium": 16, "high": 26, "very_high": 41},
        "unit_sloc": {"medium": 61, "high": 101, "very_high": 201},
        "unit_nesting": {"medium": 4, "high": 6, "very_high": 8},
        "unit_params": {"medium": 6, "high": 8, "very_high": 11},
        "file_sloc": {"medium": 801, "high": 1501, "very_high": 3001},
    },
    # Rules whose HIGH(+) findings block the gate. Everything else is advisory.
    "blocking_rules": [
        "structural-cyclomatic",
        "structural-cognitive",
        "structural-sloc",
        "structural-nesting",
        "structural-params",
        "ratchet-cyclomatic",
        "ratchet-cognitive",
        "ratchet-sloc",
        "ratchet-nesting",
        "clone-in-diff",
        "docstring-ratio",
        "suppression-bare",
        "model-finding",
    ],
    "advisory_rules": ["file-sloc", "todo-untracked", "commented-out-code",
                       "annotation-ratio", "ingest"],
    # Docstring floor over public units in the head scan (new units when a
    # base scan allows new/pre-existing distinction).
    "min_public_docstring_ratio": 0.8,
    "min_annotated_ratio": 0.9,          # advisory corroboration; mypy owns depth
    "clone_min_statements": 4,
    "clone_min_sloc": 8,
    "ticket_pattern": "ARK-\\d+",
    "suppression_justification_min_chars": 10,
    # Ratchet: worsening into >= high blocks; worsening within lower bands advises.
    "ratchet_blocking_from": "high",
    "ingest_blocking": False,            # lint/type gates already block in delivery
    "unwaivable_severities": ["critical"],
    "waiver_max_days": 90,
}

SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "very-high": 4,
                  "critical": 5}

GENERIC_COMMENT_PREFIXES = {
    ".py": "#", ".sh": "#", ".yaml": "#", ".yml": "#", ".toml": "#", ".tf": "#",
    ".js": "//", ".jsx": "//", ".ts": "//", ".tsx": "//", ".go": "//",
    ".rs": "//", ".java": "//", ".c": "//", ".h": "//", ".cpp": "//",
    ".sql": "--", ".lua": "--",
}

SUPPRESSION_PATTERNS = [
    # (marker-name, regex matching the marker itself)
    ("noqa", re.compile(r"#\s*noqa\b(?::\s*[A-Z0-9, ]+)?", re.IGNORECASE)),
    ("type-ignore", re.compile(r"#\s*type:\s*ignore\b(?:\[[^\]]*\])?")),
    ("pragma-no-cover", re.compile(r"#\s*pragma:\s*no\s*cover\b")),
    ("nosec", re.compile(r"#\s*nosec\b(?:\s*[A-Z0-9, ]+)?")),
    ("eslint-disable", re.compile(r"//\s*eslint-disable(?:-next-line|-line)?\b[^\n]*?(?=--|$)")),
    ("ts-ignore", re.compile(r"//\s*@ts-(?:ignore|expect-error|nocheck)\b")),
    ("trivy-ignore", re.compile(r"#\s*trivy:ignore\b[^\s]*")),
]

TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)

CODE_SIGNAL_NODES = (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Return,
                     ast.Import, ast.ImportFrom, ast.FunctionDef,
                     ast.AsyncFunctionDef, ast.ClassDef, ast.If, ast.For,
                     ast.While, ast.With, ast.Raise, ast.Delete)

DIRECTIVE_RE = re.compile(
    r"^\s*(noqa|type:|pragma|ruff:|mypy:|isort:|fmt:|coding[:=]|!|-\*-|"
    r"pylint:|nosec|trivy:|yamllint|shellcheck|license|copyright|spdx)",
    re.IGNORECASE,
)


def _err(msg: str) -> None:
    sys.stderr.write("quality.py: %s\n" % msg)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


# ---------------------------------------------------------------------------
# Cyclomatic complexity (radon-compatible approximation, fixture-locked)
# ---------------------------------------------------------------------------

class _CyclomaticVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.count = 1

    def visit_If(self, node: ast.If) -> None:
        self.count += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.count += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.count += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.count += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.count += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.count += 1
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self.count += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.count += len(node.values) - 1
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.count += 1 + len(node.ifs)
        self.generic_visit(node)

    def _visit_match_case(self, node: ast.AST) -> None:  # 3.10+ only
        self.count += 1
        self.generic_visit(node)

    def visit(self, node: ast.AST) -> None:
        if node.__class__.__name__ == "match_case":
            self._visit_match_case(node)
            return
        super().visit(node)

    # Do not descend into nested defs — they are measured as their own units.
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        pass

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        pass

    def visit_Lambda(self, node: ast.Lambda) -> None:
        pass


def cyclomatic_complexity(fn: ast.AST) -> int:
    v = _CyclomaticVisitor()
    body = getattr(fn, "body", [])
    for child in body:
        v.visit(child)
    # decorators/args defaults are not control flow; ignore.
    return v.count


# ---------------------------------------------------------------------------
# Cognitive complexity (SonarSource-spec approximation, fixture-locked):
# +1+nesting for if/for/while/except/ternary; +1 flat for elif/else;
# +1 per boolean-operator sequence (per BoolOp node); +1 for direct recursion;
# nesting increases inside control structures and nested defs/lambdas.
# ---------------------------------------------------------------------------

def cognitive_complexity(fn: ast.AST) -> int:
    fn_name = getattr(fn, "name", None)
    total = 0

    def walk_expr(node: ast.AST, nesting: int) -> None:
        nonlocal total
        if isinstance(node, ast.BoolOp):
            total += 1
        if isinstance(node, ast.IfExp):
            total += 1 + nesting
            walk_expr(node.test, nesting)
            walk_expr(node.body, nesting + 1)
            walk_expr(node.orelse, nesting + 1)
            return
        if isinstance(node, ast.Lambda):
            walk_expr(node.body, nesting + 1)
            return
        if isinstance(node, ast.Call) and fn_name is not None:
            f = node.func
            if isinstance(f, ast.Name) and f.id == fn_name:
                total += 1
        for child in ast.iter_child_nodes(node):
            walk_expr(child, nesting)

    def handle_if(node: ast.If, nesting: int, as_elif: bool) -> None:
        nonlocal total
        total += 1 if as_elif else (1 + nesting)
        walk_expr(node.test, nesting)
        walk_stmts(node.body, nesting + 1)
        orelse = node.orelse
        if len(orelse) == 1 and isinstance(orelse[0], ast.If):
            handle_if(orelse[0], nesting, as_elif=True)
        elif orelse:
            total += 1  # else — flat increment per spec
            walk_stmts(orelse, nesting + 1)

    def walk_stmts(stmts, nesting: int) -> None:
        nonlocal total
        for node in stmts:
            if isinstance(node, ast.If):
                handle_if(node, nesting, as_elif=False)
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
                total += 1 + nesting
                for f in ast.iter_child_nodes(node):
                    if isinstance(f, ast.expr):
                        walk_expr(f, nesting)
                walk_stmts(node.body, nesting + 1)
                walk_stmts(node.orelse, nesting + 1)
            elif isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))):
                walk_stmts(node.body, nesting)
                for handler in node.handlers:
                    total += 1 + nesting
                    walk_stmts(handler.body, nesting + 1)
                walk_stmts(node.orelse, nesting)
                walk_stmts(node.finalbody, nesting)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    walk_expr(item.context_expr, nesting)
                walk_stmts(node.body, nesting)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk_stmts(node.body, nesting + 1)
            elif isinstance(node, ast.ClassDef):
                walk_stmts(node.body, nesting + 1)
            else:
                walk_expr(node, nesting)

    walk_stmts(getattr(fn, "body", []), 0)
    return total


def max_nesting(fn: ast.AST) -> int:
    deepest = 0

    def handle_if(node: ast.If, depth: int) -> None:
        nonlocal deepest
        deepest = max(deepest, depth + 1)
        walk(node.body, depth + 1)
        orelse = node.orelse
        if len(orelse) == 1 and isinstance(orelse[0], ast.If):
            handle_if(orelse[0], depth)  # elif continues the same chain depth
        elif orelse:
            walk(orelse, depth + 1)

    def walk(stmts, depth: int) -> None:
        nonlocal deepest
        for node in stmts:
            if isinstance(node, ast.If):
                handle_if(node, depth)
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.While,
                                   ast.With, ast.AsyncWith, ast.Try,
                                   getattr(ast, "TryStar", ast.Try))):
                deepest = max(deepest, depth + 1)
                for attr in ("body", "orelse", "finalbody"):
                    walk(getattr(node, attr, []), depth + 1)
                for handler in getattr(node, "handlers", []):
                    walk(handler.body, depth + 1)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef)):
                walk(node.body, depth)  # nested defs measured separately

    walk(getattr(fn, "body", []), 0)
    return deepest


# ---------------------------------------------------------------------------
# Clone hashing — type-2 clones (identifiers/literals normalised)
# ---------------------------------------------------------------------------

class _Normaliser(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name) -> ast.AST:
        self.generic_visit(node)
        return ast.copy_location(ast.Name(id="N", ctx=node.ctx), node)

    def visit_arg(self, node: ast.arg) -> ast.AST:
        self.generic_visit(node)
        node.arg = "N"
        node.annotation = None
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        return ast.copy_location(ast.Constant(value="C"), node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        node.name = "F"
        node.returns = None
        node.decorator_list = []
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self.generic_visit(node)
        node.name = "F"
        node.returns = None
        node.decorator_list = []
        return node


def _strip_docstring(body):
    if body and isinstance(body[0], ast.Expr) and \
            isinstance(getattr(body[0], "value", None), ast.Constant) and \
            isinstance(body[0].value.value, str):
        return body[1:]
    return body


def clone_hash(fn: ast.AST, min_statements: int, min_sloc: int,
               unit_sloc: int) -> "str | None":
    body = _strip_docstring(list(getattr(fn, "body", [])))
    if len(body) < min_statements or unit_sloc < min_sloc:
        return None
    clone = copy.deepcopy(fn)
    clone.body = _strip_docstring(clone.body)  # type: ignore[attr-defined]
    normalised = _Normaliser().visit(clone)
    dump = ast.dump(normalised, annotate_fields=False, include_attributes=False)
    return hashlib.sha256(dump.encode("utf-8")).hexdigest()[:20]


# ---------------------------------------------------------------------------
# Python file scan
# ---------------------------------------------------------------------------

def _unit_sloc(node: ast.AST, source_lines) -> int:
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)
    count = 0
    for i in range(start - 1, min(end, len(source_lines))):
        stripped = source_lines[i].strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _annotated(fn) -> bool:
    args = list(getattr(fn.args, "posonlyargs", [])) + fn.args.args
    names = [a for a in args if a.arg not in ("self", "cls")]
    extra = [a for a in (fn.args.vararg, fn.args.kwarg) if a is not None]
    kwonly = list(fn.args.kwonlyargs)
    all_args = names + extra + kwonly
    if any(a.annotation is None for a in all_args):
        return False
    return fn.returns is not None


def _params_count(fn) -> int:
    args = list(getattr(fn.args, "posonlyargs", [])) + fn.args.args
    names = [a for a in args if a.arg not in ("self", "cls")]
    return len(names) + len(fn.args.kwonlyargs)


def _comment_lines_and_findings(source: str, policy: dict):
    """Tokenise comments once: density, suppressions, TODOs, commented-out code."""
    comment_rows = []  # (line, text)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                comment_rows.append((tok.start[0], tok.string))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass

    ticket_re = re.compile(policy.get("ticket_pattern", "ARK-\\d+"))
    min_just = int(policy.get("suppression_justification_min_chars", 10))
    suppressions, todos = [], []

    for line_no, text in comment_rows:
        for marker, pattern in SUPPRESSION_PATTERNS:
            m = pattern.search(text)
            if m:
                remainder = (text[:m.start()] + text[m.end():])
                remainder = remainder.replace("#", " ").replace("//", " ")
                remainder = re.sub(r"[-—:\s]+", " ", remainder).strip()
                suppressions.append({
                    "line": line_no, "marker": marker,
                    "bare": len(remainder) < min_just,
                })
        tm = TODO_RE.search(text)
        if tm:
            todos.append({
                "line": line_no,
                "text": text.strip()[:120],
                "tracked": bool(ticket_re.search(text)),
            })

    # Commented-out code: comment lines whose stripped text parses as Python
    # containing signal statements (per line, so prose sharing the run cannot
    # mask real code). Single-line heuristic: multi-line block constructs that
    # only parse together are not detected. Directive lines excluded.
    commented_out = []
    runs, current = [], []
    lines = source.splitlines()
    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if stripped.startswith("#"):
            body = stripped.lstrip("#").strip()
            if not DIRECTIVE_RE.match(body):
                current.append((idx, body))
                continue
        if current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)

    def parses_as_code(text: str) -> bool:
        if not text or TODO_RE.search(text):
            return False
        wrapped = "def _w():\n    " + text
        for candidate in (text, wrapped):
            try:
                tree = ast.parse(candidate)
            except (SyntaxError, ValueError, MemoryError):
                continue
            for n in ast.walk(tree):
                if isinstance(n, ast.AnnAssign):
                    if n.value is not None:  # "note: text" parses valueless
                        return True
                    continue
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and n.name == "_w":
                    continue
                if isinstance(n, CODE_SIGNAL_NODES):
                    return True
                if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):
                    return True
        return False

    for run in runs:
        block = []
        for idx, body in run:
            if parses_as_code(body):
                block.append(idx)
            elif block:
                commented_out.append({"line_start": block[0],
                                      "line_end": block[-1]})
                block = []
        if block:
            commented_out.append({"line_start": block[0],
                                  "line_end": block[-1]})

    return len(comment_rows), suppressions, todos, commented_out


def scan_python_file(path: str, source: str, policy: dict) -> dict:
    lines = source.splitlines()
    sloc = sum(1 for ln in lines if ln.strip() and not ln.strip().startswith("#"))
    comment_count, suppressions, todos, commented_out = \
        _comment_lines_and_findings(source, policy)

    row = {
        "path": path, "lang": "python", "sloc": sloc,
        "comment_lines": comment_count,
        "comment_density": round(comment_count / sloc, 3) if sloc else 0.0,
        "module_docstring": False, "parse_error": None,
        "suppressions": suppressions, "todos": todos,
        "commented_out": commented_out, "units": [],
    }

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        row["parse_error"] = "line %s: %s" % (exc.lineno, exc.msg)
        return row

    row["module_docstring"] = ast.get_docstring(tree) is not None
    min_stmts = int(policy.get("clone_min_statements", 4))
    min_sloc = int(policy.get("clone_min_sloc", 8))

    def add_unit(node, qualname: str, kind: str) -> None:
        unit_sloc = _unit_sloc(node, lines)
        entry = {
            "qualname": qualname, "type": kind, "lineno": node.lineno,
            "end_lineno": getattr(node, "end_lineno", node.lineno),
            "sloc": unit_sloc, "is_public": _is_public(node.name),
            "has_docstring": ast.get_docstring(node) is not None,
        }
        if kind in ("function", "method"):
            entry.update({
                "cyclomatic": cyclomatic_complexity(node),
                "cognitive": cognitive_complexity(node),
                "nesting_max": max_nesting(node),
                "params": _params_count(node),
                "annotated": _annotated(node),
                "clone_hash": clone_hash(node, min_stmts, min_sloc, unit_sloc),
            })
        row["units"].append(entry)

    def walk(nodes, prefix: str, inside_class: bool) -> None:
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = prefix + node.name
                add_unit(node, qual, "method" if inside_class else "function")
                walk(node.body, qual + ".", False)
            elif isinstance(node, ast.ClassDef):
                qual = prefix + node.name
                add_unit(node, qual, "class")
                walk(node.body, qual + ".", True)

    walk(tree.body, "", False)
    return row


def scan_generic_file(path: str, source: str, policy: dict) -> dict:
    ext = os.path.splitext(path)[1].lower()
    prefix = GENERIC_COMMENT_PREFIXES.get(ext)
    lines = source.splitlines()
    sloc = comment_count = 0
    todos = []
    ticket_re = re.compile(policy.get("ticket_pattern", "ARK-\\d+"))
    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        if prefix and stripped.startswith(prefix):
            comment_count += 1
        else:
            sloc += 1
        tm = TODO_RE.search(stripped)
        if tm:
            todos.append({"line": idx, "text": stripped[:120],
                          "tracked": bool(ticket_re.search(stripped))})
    return {
        "path": path, "lang": "generic", "sloc": sloc,
        "comment_lines": comment_count,
        "comment_density": round(comment_count / sloc, 3) if sloc else 0.0,
        "module_docstring": None, "parse_error": None,
        "suppressions": [], "todos": todos, "commented_out": [], "units": [],
    }


def run_scan(files, policy: dict) -> dict:
    out = {"engine_version": ENGINE_VERSION, "generated_by": "quality.py scan",
           "files": [], "clone_pairs": [], "errors": []}
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
        except OSError as exc:
            out["errors"].append({"path": path, "error": str(exc)})
            continue
        if path.endswith(".py"):
            out["files"].append(scan_python_file(path, source, policy))
        else:
            out["files"].append(scan_generic_file(path, source, policy))

    seen = {}
    for frow in out["files"]:
        for unit in frow["units"]:
            h = unit.get("clone_hash")
            if not h:
                continue
            key = (frow["path"], unit["qualname"])
            if h in seen and seen[h] != key:
                out["clone_pairs"].append({
                    "hash": h,
                    "a": {"file": seen[h][0], "qualname": seen[h][1]},
                    "b": {"file": frow["path"], "qualname": unit["qualname"]},
                })
            else:
                seen.setdefault(h, key)
    return out


# ---------------------------------------------------------------------------
# Ingest — normalise external tool output to finding rows
# ---------------------------------------------------------------------------

def ingest_rows(kind: str, payload) -> "list[dict]":
    rows = []
    if kind == "ruff":
        for item in payload:
            rows.append({"tool": "ruff", "rule": str(item.get("code")),
                         "file": item.get("filename", ""),
                         "line": (item.get("location") or {}).get("row", 0),
                         "severity": "medium",
                         "message": str(item.get("message", ""))[:200]})
    elif kind == "eslint":
        for f in payload:
            for m in f.get("messages", []):
                rows.append({"tool": "eslint",
                             "rule": str(m.get("ruleId") or "parse"),
                             "file": f.get("filePath", ""),
                             "line": m.get("line", 0),
                             "severity": "medium" if m.get("severity") == 2
                             else "low",
                             "message": str(m.get("message", ""))[:200]})
    elif kind == "jscpd":
        for dup in (payload.get("duplicates") or []):
            first = dup.get("firstFile") or {}
            second = dup.get("secondFile") or {}
            rows.append({"tool": "jscpd", "rule": "duplication",
                         "file": first.get("name", ""),
                         "line": (first.get("start") or 0),
                         "severity": "high",
                         "message": "clone of %s:%s (%s lines)" % (
                             second.get("name", "?"), second.get("start", "?"),
                             dup.get("lines", "?"))})
    elif kind == "lizard":
        # lizard --csv: NLOC,CCN,token,param,length,location,file,function,...
        for line in payload if isinstance(payload, list) else []:
            parts = [p.strip().strip('"') for p in str(line).split(",")]
            if len(parts) < 8 or not parts[1].isdigit():
                continue
            rows.append({"tool": "lizard", "rule": "ccn",
                         "file": parts[6], "line": 0,
                         "severity": "info",
                         "message": "CCN=%s params=%s nloc=%s fn=%s" % (
                             parts[1], parts[3], parts[0], parts[7]),
                         "ccn": int(parts[1]), "function": parts[7]})
    elif kind == "generic":
        for item in payload:
            sev = str(item.get("severity", "medium")).lower()
            rows.append({"tool": str(item.get("tool", "generic")),
                         "rule": str(item.get("rule", "generic")),
                         "file": str(item.get("file", "")),
                         "line": int(item.get("line", 0) or 0),
                         "severity": sev if sev in SEVERITY_ORDER else "medium",
                         "message": str(item.get("message", ""))[:200]})
    else:
        raise ValueError("unknown ingest kind: %s" % kind)
    return rows


# ---------------------------------------------------------------------------
# Policy / waivers
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_policy(path: "str | None"):
    degraded = []
    policy = copy.deepcopy(DEFAULT_POLICY)
    if path:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                override = json.load(fh)
            if not isinstance(override, dict):
                raise ValueError("policy root must be an object")
            policy = _deep_merge(policy, override)
        except (OSError, ValueError) as exc:
            degraded.append("policy file unusable (%s) — defaults applied: %s"
                            % (path, exc))
            _err("WARNING: %s" % degraded[-1])
    return policy, degraded


def load_waivers(path: "str | None"):
    degraded = []
    waivers = []
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            waivers = data.get("waivers", data) if isinstance(data, dict) else data
            if not isinstance(waivers, list):
                raise ValueError("waivers must be a list")
        except (OSError, ValueError) as exc:
            degraded.append("waiver ledger unusable (%s) — treated as no waivers"
                            % exc)
            _err("WARNING: %s" % degraded[-1])
            waivers = []
    return waivers, degraded


def _waiver_status(waiver: dict, severity: str, policy: dict, today: date):
    if severity in policy.get("unwaivable_severities", ["critical"]):
        return "rejected", "severity '%s' is never waivable" % severity
    if not waiver.get("approved_by"):
        return "rejected", "missing approved_by"
    if not waiver.get("reason"):
        return "rejected", "missing reason"
    expires = waiver.get("expires")
    if not expires:
        return "rejected", "missing expires"
    try:
        exp = datetime.strptime(str(expires), "%Y-%m-%d").date()
    except ValueError:
        return "rejected", "expires not YYYY-MM-DD"
    if exp < today:
        return "rejected", "expired %s" % expires
    return "applied", None


# ---------------------------------------------------------------------------
# Check — the policy join
# ---------------------------------------------------------------------------

def band_for(value, bands: dict) -> "str | None":
    if value is None:
        return None
    label = None
    for name in ("medium", "high", "very_high"):
        threshold = bands.get(name)
        if threshold is not None and value >= threshold:
            label = name
    return {"very_high": "very-high"}.get(label, label)


_METRIC_RULES = [
    ("cyclomatic", "unit_cyclomatic", "structural-cyclomatic"),
    ("cognitive", "unit_cognitive", "structural-cognitive"),
    ("sloc", "unit_sloc", "structural-sloc"),
    ("nesting_max", "unit_nesting", "structural-nesting"),
    ("params", "unit_params", "structural-params"),
]


def _finding(rule, severity, file, ref, message, blocking):
    return {"key": "%s:%s:%s" % (rule, file, ref), "rule": rule,
            "severity": severity, "file": file, "ref": str(ref),
            "message": message, "blocking": bool(blocking), "status": "open"}


def run_check(head: dict, base: "dict | None", ingested: "list[dict]",
              model_findings: "list[dict]", policy: dict, waivers: "list[dict]",
              degraded: "list[str]", today: "date | None" = None) -> dict:
    today = today or date.today()
    bands = policy["bands"]
    blocking_rules = set(policy.get("blocking_rules", []))
    findings = []

    base_units = {}
    if base:
        for frow in base.get("files", []):
            for unit in frow.get("units", []):
                base_units[(frow["path"], unit["qualname"])] = unit

    public_units = 0
    public_with_doc = 0
    annotated_ok = 0
    annotated_total = 0

    for frow in head.get("files", []):
        path = frow["path"]
        if frow.get("parse_error"):
            degraded.append("parse error in %s (%s) — native metrics unavailable"
                            % (path, frow["parse_error"]))
        fband = band_for(frow.get("sloc"), bands["file_sloc"])
        if fband:
            findings.append(_finding(
                "file-sloc", fband, path, "file",
                "file has %s source lines" % frow["sloc"],
                "file-sloc" in blocking_rules and
                SEVERITY_ORDER[fband] >= SEVERITY_ORDER["high"]))

        for s in frow.get("suppressions", []):
            if s.get("bare"):
                findings.append(_finding(
                    "suppression-bare", "high", path, s["line"],
                    "bare %s suppression without justification" % s["marker"],
                    "suppression-bare" in blocking_rules))
        for t in frow.get("todos", []):
            if not t.get("tracked"):
                findings.append(_finding(
                    "todo-untracked", "low", path, t["line"],
                    "TODO/FIXME without ticket reference: %s" % t["text"],
                    False))
        for c in frow.get("commented_out", []):
            findings.append(_finding(
                "commented-out-code", "medium", path,
                "%s-%s" % (c["line_start"], c["line_end"]),
                "commented-out code block (lines %s-%s)"
                % (c["line_start"], c["line_end"]), False))

        for unit in frow.get("units", []):
            key = (path, unit["qualname"])
            in_base = key in base_units
            if unit.get("is_public") and unit["type"] != "class":
                if not in_base:
                    public_units += 1
                    if unit.get("has_docstring"):
                        public_with_doc += 1
                if "annotated" in unit:
                    annotated_total += 1
                    if unit["annotated"]:
                        annotated_ok += 1

            if unit["type"] == "class":
                continue

            for metric, band_key, rule in _METRIC_RULES:
                value = unit.get(metric)
                b = band_for(value, bands[band_key])
                if b is None:
                    continue
                blocking = (rule in blocking_rules and
                            SEVERITY_ORDER[b] >= SEVERITY_ORDER["high"])
                if in_base:
                    prior = band_for(base_units[key].get(metric),
                                     bands[band_key])
                    prior_rank = SEVERITY_ORDER.get(prior or "info", 0)
                    if SEVERITY_ORDER[b] > prior_rank:
                        r_rule = rule.replace("structural-", "ratchet-")
                        r_block = (r_rule in blocking_rules and
                                   SEVERITY_ORDER[b] >= SEVERITY_ORDER[
                                       policy.get("ratchet_blocking_from",
                                                  "high")])
                        findings.append(_finding(
                            r_rule, b, path, unit["qualname"],
                            "%s worsened %s → %s (%s=%s)" % (
                                unit["qualname"], prior or "clean", b,
                                metric, value), r_block))
                    # pre-existing debt at unchanged band: advisory only
                    elif SEVERITY_ORDER[b] >= SEVERITY_ORDER["high"]:
                        findings.append(_finding(
                            rule, b, path, unit["qualname"],
                            "pre-existing: %s %s=%s (band %s, unchanged)" % (
                                unit["qualname"], metric, value, b), False))
                else:
                    findings.append(_finding(
                        rule, b, path, unit["qualname"],
                        "new unit %s has %s=%s (band %s)" % (
                            unit["qualname"], metric, value, b), blocking))

    for pair in head.get("clone_pairs", []):
        findings.append(_finding(
            "clone-in-diff", "high", pair["a"]["file"],
            "%s~%s" % (pair["a"]["qualname"], pair["b"]["qualname"]),
            "type-2 clone: %s:%s duplicates %s:%s" % (
                pair["a"]["file"], pair["a"]["qualname"],
                pair["b"]["file"], pair["b"]["qualname"]),
            "clone-in-diff" in blocking_rules))

    doc_ratio = (public_with_doc / public_units) if public_units else None
    min_ratio = float(policy.get("min_public_docstring_ratio", 0.8))
    if doc_ratio is not None and doc_ratio < min_ratio:
        findings.append(_finding(
            "docstring-ratio", "high", "(scan)", "public-units",
            "public docstring ratio %.2f below floor %.2f (%s/%s %s units)"
            % (doc_ratio, min_ratio, public_with_doc, public_units,
               "new public" if base else "public"),
            "docstring-ratio" in blocking_rules))

    ann_ratio = (annotated_ok / annotated_total) if annotated_total else None
    if ann_ratio is not None and \
            ann_ratio < float(policy.get("min_annotated_ratio", 0.9)):
        findings.append(_finding(
            "annotation-ratio", "medium", "(scan)", "signatures",
            "fully-annotated signature ratio %.2f below %.2f"
            % (ann_ratio, policy.get("min_annotated_ratio", 0.9)), False))

    ingest_blocking = bool(policy.get("ingest_blocking", False))
    for row in ingested:
        if row.get("tool") == "lizard" and "ccn" in row:
            b = band_for(row["ccn"], bands["unit_cyclomatic"])
            if b is None:
                continue
            findings.append(_finding(
                "structural-cyclomatic", b, row["file"],
                row.get("function", "?"),
                "lizard CCN=%s for %s" % (row["ccn"], row.get("function")),
                "structural-cyclomatic" in blocking_rules and
                SEVERITY_ORDER[b] >= SEVERITY_ORDER["high"]))
            continue
        sev = row.get("severity", "medium")
        findings.append(_finding(
            "ingest", sev, row.get("file", ""), row.get("line", 0),
            "[%s/%s] %s" % (row.get("tool"), row.get("rule"),
                            row.get("message")),
            ingest_blocking and SEVERITY_ORDER.get(sev, 2) >=
            SEVERITY_ORDER["high"]))

    model_open = 0
    for mf in model_findings:
        if not mf.get("verified") or mf.get("refuted"):
            continue
        sev = str(mf.get("severity", "medium")).lower()
        if sev not in SEVERITY_ORDER:
            sev = "medium"
        blocking = ("model-finding" in blocking_rules and
                    SEVERITY_ORDER[sev] >= SEVERITY_ORDER["high"])
        if blocking:
            model_open += 1
        findings.append(_finding(
            "model-finding", sev, mf.get("file", "(model)"),
            mf.get("id", "?"),
            "[%s] %s" % (mf.get("clause", "model"),
                         str(mf.get("title", ""))[:160]), blocking))

    # Waivers
    waiver_report = {"applied": [], "rejected": []}
    waiver_map = {w.get("key"): w for w in waivers if isinstance(w, dict)}
    for finding in findings:
        w = waiver_map.get(finding["key"])
        if not w:
            continue
        status, why = _waiver_status(w, finding["severity"], policy, today)
        if status == "applied":
            finding["status"] = "waived"
            finding["blocking"] = False
            waiver_report["applied"].append(
                {"key": finding["key"], "approved_by": w.get("approved_by"),
                 "expires": w.get("expires")})
        else:
            waiver_report["rejected"].append(
                {"key": finding["key"], "reason": why})

    # Clause table
    def clause(cid, name, rules):
        rows = [f for f in findings if f["rule"] in rules]
        open_blocking = [f for f in rows
                         if f["blocking"] and f["status"] == "open"]
        return {"id": cid, "name": name,
                "status": "fail" if open_blocking else "pass",
                "findings": len(rows), "blocking_open": len(open_blocking)}

    clauses = [
        clause(1, "Structural simplicity",
               ["structural-cyclomatic", "structural-cognitive",
                "structural-sloc", "structural-nesting", "structural-params",
                "file-sloc"]),
        clause(2, "No duplication", ["clone-in-diff"]),
        clause(3, "Comments and documentation floor",
               ["docstring-ratio", "commented-out-code", "todo-untracked"]),
        clause(4, "Typing and suppression hygiene",
               ["suppression-bare", "annotation-ratio", "ingest"]),
        clause(5, "Ratchet — no worse than base",
               ["ratchet-cyclomatic", "ratchet-cognitive", "ratchet-sloc",
                "ratchet-nesting", "ratchet-params"]),
        clause(6, "Model review (adversarially verified)", ["model-finding"]),
    ]

    blocking_open = [f for f in findings
                     if f["blocking"] and f["status"] == "open"]
    if blocking_open:
        verdict = "REWORK-REQUIRED"
    elif waiver_report["applied"] or degraded:
        verdict = "CONDITIONAL-PASS"
    else:
        verdict = "MAINTAINABLE"

    findings.sort(key=lambda f: (-SEVERITY_ORDER.get(f["severity"], 0),
                                 f["rule"], f["file"], f["ref"]))
    return {
        "engine_version": ENGINE_VERSION,
        "verdict": verdict,
        "clauses": clauses,
        "counts": {
            "findings": len(findings),
            "blocking_open": len(blocking_open),
            "waived": len(waiver_report["applied"]),
            "advisory": len([f for f in findings
                             if not f["blocking"] and f["status"] == "open"]),
            "model_blocking_open": model_open,
        },
        "metrics_summary": {
            "public_docstring_ratio": doc_ratio,
            "annotated_ratio": ann_ratio,
            "files": len(head.get("files", [])),
            "units": sum(len(f.get("units", []))
                         for f in head.get("files", [])),
            "base_scan": bool(base),
        },
        "findings": findings,
        "waivers": waiver_report,
        "degraded": degraded,
        "policy_sha256": sha256_text(json.dumps(policy, sort_keys=True))[:16],
    }


# ---------------------------------------------------------------------------
# Selftest — 10 scenarios; build.sh greps the final "10/10 … ALL PASS" line
# ---------------------------------------------------------------------------

FIXTURE_METRICS = '''
def alpha(a, b, c):
    """Doc."""
    total = 0
    for i in range(a):
        if i % 2 == 0 and b:
            total += i
        elif c:
            total -= 1
    try:
        total /= b
    except ZeroDivisionError:
        total = 0
    return total
'''

FIXTURE_DIVERGENCE = '''
def nested(x):
    """Doc."""
    if x > 0:
        if x > 1:
            if x > 2:
                return 3
    return 0


def flat(x):
    """Doc."""
    if x == 1:
        return 1
    elif x == 2:
        return 2
    elif x == 3:
        return 3
    return 0
'''

FIXTURE_DOCSTRINGS = '''
"""Module doc."""


def visible(x: int) -> int:
    """Documented."""
    return x


def exposed(x: int) -> int:
    return x


def _hidden(x):
    return x


class Widget:
    """Documented class."""

    def render(self) -> str:
        return "w"
'''

FIXTURE_COMMENTS = '''
import os


def run(x: int) -> int:
    """Doc."""
    # This explains why the offset exists: upstream API is 1-indexed.
    # result = compute(x)
    # return result + OFFSET
    # TODO: remove the offset once upstream fixes indexing
    # TODO(ARK-1234): migrate to v2 endpoint
    value = int(os.environ.get("OFFSET", "1"))  # noqa
    safe = x + value  # noqa: PLR2004 — offset bound is a domain constant
    return safe
'''

FIXTURE_CLONES = '''
def first_totaliser(items):
    """Doc."""
    if not items:
        return 0
    total = 0
    for item in items:
        if item > 0:
            total += item
        else:
            total -= item
    return total


def second_totaliser(rows):
    """Doc."""
    if not rows:
        return 0
    accumulated = 0
    for row in rows:
        if row > 0:
            accumulated += row
        else:
            accumulated -= row
    return accumulated


def different(items):
    """Doc."""
    if not items:
        return None
    best = None
    for item in items:
        if best is None or item < best:
            best = item
    return best
'''

FIXTURE_COMPLEX_UNIT = '''
def tangled(a, b, c, d, e, f, g, h):
    """Doc."""
    out = 0
    for i in range(a):
        if a and b and c and d:
            if b:
                if c:
                    if d:
                        if e:
                            out += 1
    if f:
        out += 1
    if g:
        out += 1
    if h:
        out += 1
    if a:
        out += 1
    if b:
        out += 1
    if c:
        out += 1
    if d:
        out += 1
    if e:
        out += 1
    return out
'''

FIXTURE_BASE_SIMPLE = '''
def evolve(x: int) -> int:
    """Doc."""
    if x > 0:
        return x
    return -x
'''

FIXTURE_HEAD_WORSE = '''
def evolve(x: int) -> int:
    """Doc."""
    if x > 0 and x < 100:
        if x % 2:
            if x % 3:
                if x % 5:
                    if x % 7:
                        if x % 11:
                            if x % 13:
                                if x % 17:
                                    if x % 19:
                                        if x % 23:
                                            if x % 29:
                                                if x % 31:
                                                    if x % 37:
                                                        return 1
    return -x
'''

RUFF_FIXTURE = json.dumps([
    {"code": "F401", "filename": "src/mod.py",
     "location": {"row": 3, "column": 1},
     "message": "'os' imported but unused"},
    {"code": "E722", "filename": "src/mod.py",
     "location": {"row": 40, "column": 1},
     "message": "do not use bare 'except'"},
])

ESLINT_FIXTURE = json.dumps([
    {"filePath": "src/app.ts", "messages": [
        {"ruleId": "complexity", "severity": 2, "line": 12,
         "message": "Function has a complexity of 21."},
        {"ruleId": "no-unused-vars", "severity": 1, "line": 30,
         "message": "unused variable"},
    ]},
])


def _scan_source(source: str, path: str = "fixture.py",
                 policy: "dict | None" = None) -> dict:
    policy = policy or copy.deepcopy(DEFAULT_POLICY)
    return {"engine_version": ENGINE_VERSION, "generated_by": "selftest",
            "files": [scan_python_file(path, source, policy)],
            "clone_pairs": [], "errors": []}


def _attach_clones(scan: dict) -> dict:
    seen = {}
    scan["clone_pairs"] = []
    for frow in scan["files"]:
        for unit in frow["units"]:
            h = unit.get("clone_hash")
            if not h:
                continue
            key = (frow["path"], unit["qualname"])
            if h in seen and seen[h] != key:
                scan["clone_pairs"].append({
                    "hash": h,
                    "a": {"file": seen[h][0], "qualname": seen[h][1]},
                    "b": {"file": frow["path"], "qualname": unit["qualname"]}})
            else:
                seen.setdefault(h, key)
    return scan


def selftest() -> int:
    results = []
    policy = copy.deepcopy(DEFAULT_POLICY)

    def record(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    # 1 — AST metric exactness
    try:
        scan = _scan_source(FIXTURE_METRICS)
        unit = scan["files"][0]["units"][0]
        ok = (unit["cyclomatic"] == 6 and unit["cognitive"] == 6 and
              unit["params"] == 3 and unit["nesting_max"] == 2 and
              unit["has_docstring"] and unit["is_public"])
        record("ast-metric-exactness", ok,
               "cyc=%s cog=%s params=%s nest=%s" % (
                   unit["cyclomatic"], unit["cognitive"], unit["params"],
                   unit["nesting_max"]))
    except Exception as exc:  # noqa: BLE001 — selftest must report, not crash
        record("ast-metric-exactness", False, repr(exc))

    # 2 — cognitive/cyclomatic divergence on nesting
    try:
        scan = _scan_source(FIXTURE_DIVERGENCE)
        units = {u["qualname"]: u for u in scan["files"][0]["units"]}
        n, f = units["nested"], units["flat"]
        ok = (n["cyclomatic"] == 4 and f["cyclomatic"] == 4 and
              n["cognitive"] == 6 and f["cognitive"] == 3 and
              n["cognitive"] > f["cognitive"])
        record("cognitive-nesting-divergence", ok,
               "nested cog=%s flat cog=%s" % (n["cognitive"], f["cognitive"]))
    except Exception as exc:  # noqa: BLE001
        record("cognitive-nesting-divergence", False, repr(exc))

    # 3 — docstring coverage and publicness
    try:
        scan = _scan_source(FIXTURE_DOCSTRINGS)
        result = run_check(scan, None, [], [], policy, [], [])
        ratio = result["metrics_summary"]["public_docstring_ratio"]
        # public non-class units: visible(doc), exposed(no), render(no) → 1/3
        finding = [f for f in result["findings"]
                   if f["rule"] == "docstring-ratio"]
        ok = (abs(ratio - (1 / 3)) < 1e-9 and len(finding) == 1 and
              finding[0]["blocking"])
        record("docstring-coverage", ok, "ratio=%.3f" % ratio)
    except Exception as exc:  # noqa: BLE001
        record("docstring-coverage", False, repr(exc))

    # 4 — comment analysis: commented-out code, TODO tracking, suppressions
    try:
        scan = _scan_source(FIXTURE_COMMENTS)
        frow = scan["files"][0]
        result = run_check(scan, None, [], [], policy, [], [])
        rules = [f["rule"] for f in result["findings"]]
        bare = [s for s in frow["suppressions"] if s["bare"]]
        justified = [s for s in frow["suppressions"] if not s["bare"]]
        ok = (len(frow["commented_out"]) == 1 and
              len([t for t in frow["todos"] if not t["tracked"]]) == 1 and
              len([t for t in frow["todos"] if t["tracked"]]) == 1 and
              len(bare) == 1 and len(justified) == 1 and
              rules.count("suppression-bare") == 1 and
              rules.count("commented-out-code") == 1 and
              rules.count("todo-untracked") == 1)
        record("comment-analysis", ok,
               "co=%s todos=%s bare=%s" % (len(frow["commented_out"]),
                                           len(frow["todos"]), len(bare)))
    except Exception as exc:  # noqa: BLE001
        record("comment-analysis", False, repr(exc))

    # 5 — type-2 clone detection
    try:
        scan = _attach_clones(_scan_source(FIXTURE_CLONES))
        pairs = scan["clone_pairs"]
        names = sorted([pairs[0]["a"]["qualname"], pairs[0]["b"]["qualname"]]) \
            if pairs else []
        ok = (len(pairs) == 1 and
              names == ["first_totaliser", "second_totaliser"])
        record("clone-detection", ok, "pairs=%s" % len(pairs))
    except Exception as exc:  # noqa: BLE001
        record("clone-detection", False, repr(exc))

    # 6 — threshold bands and policy override
    try:
        scan = _scan_source(FIXTURE_COMPLEX_UNIT)
        unit = scan["files"][0]["units"][0]
        result = run_check(scan, None, [], [], policy, [], [])
        cyc_blockers = [f for f in result["findings"]
                        if f["rule"] == "structural-cyclomatic"
                        and f["blocking"]]
        relaxed = _deep_merge(policy, {"bands": {"unit_cyclomatic":
                                                 {"medium": 90, "high": 95,
                                                  "very_high": 99},
                                                 "unit_cognitive":
                                                 {"medium": 900, "high": 950,
                                                  "very_high": 999},
                                                 "unit_params":
                                                 {"medium": 90, "high": 95,
                                                  "very_high": 99}}})
        result2 = run_check(scan, None, [], [], relaxed, [], [])
        cyc_after = [f for f in result2["findings"]
                     if f["rule"] == "structural-cyclomatic"]
        ok = (unit["cyclomatic"] >= 16 and len(cyc_blockers) == 1 and
              result["verdict"] == "REWORK-REQUIRED" and
              len(cyc_after) == 0)
        record("threshold-policy-override", ok,
               "cyc=%s blockers=%s" % (unit["cyclomatic"], len(cyc_blockers)))
    except Exception as exc:  # noqa: BLE001
        record("threshold-policy-override", False, repr(exc))

    # 7 — ratchet vs new-unit classification
    try:
        base = _scan_source(FIXTURE_BASE_SIMPLE)
        head = _scan_source(FIXTURE_HEAD_WORSE)
        result = run_check(head, base, [], [], policy, [], [])
        ratchets = [f for f in result["findings"]
                    if f["rule"].startswith("ratchet-") and f["blocking"]]
        improved = run_check(base, head, [], [], policy, [], [])
        improved_ratchets = [f for f in improved["findings"]
                             if f["rule"].startswith("ratchet-")]
        ok = (len(ratchets) >= 1 and result["verdict"] == "REWORK-REQUIRED"
              and len(improved_ratchets) == 0
              and improved["verdict"] == "MAINTAINABLE")
        record("ratchet-delta", ok,
               "worsened=%s improved-ratchets=%s" % (
                   len(ratchets), len(improved_ratchets)))
    except Exception as exc:  # noqa: BLE001
        record("ratchet-delta", False, repr(exc))

    # 8 — ingest normalisation + malformed ingest degrades, never crashes
    try:
        ruff_rows = ingest_rows("ruff", json.loads(RUFF_FIXTURE))
        eslint_rows = ingest_rows("eslint", json.loads(ESLINT_FIXTURE))
        degraded = []
        try:
            json.loads("{not json")
        except ValueError as exc:
            degraded.append("ingest ruff:/tmp/broken.json unusable: %s" % exc)
        scan = _scan_source(FIXTURE_BASE_SIMPLE)
        result = run_check(scan, None, ruff_rows + eslint_rows, [], policy,
                           [], degraded)
        ingests = [f for f in result["findings"] if f["rule"] == "ingest"]
        ok = (len(ruff_rows) == 2 and len(eslint_rows) == 2 and
              len(ingests) == 4 and
              all(not f["blocking"] for f in ingests) and
              result["verdict"] == "CONDITIONAL-PASS" and
              result["degraded"])
        record("ingest-normalisation", ok,
               "rows=%s verdict=%s" % (len(ingests), result["verdict"]))
    except Exception as exc:  # noqa: BLE001
        record("ingest-normalisation", False, repr(exc))

    # 9 — waiver ledger: applied, expired-rejected, critical-unwaivable
    try:
        scan = _attach_clones(_scan_source(FIXTURE_CLONES))
        key = None
        pre = run_check(scan, None, [], [], policy, [], [])
        for f in pre["findings"]:
            if f["rule"] == "clone-in-diff":
                key = f["key"]
        good = [{"key": key, "reason": "sanctioned duplication pending E12",
                 "approved_by": "Amer Altaf", "expires": "2999-01-01"}]
        expired = [{"key": key, "reason": "old", "approved_by": "Amer Altaf",
                    "expires": "2020-01-01"}]
        crit_model = [{"id": "M1", "title": "test asserts nothing",
                       "severity": "critical", "clause": "tests",
                       "verified": True, "refuted": False}]
        r_good = run_check(scan, None, [], [], policy, good, [],
                           today=date(2026, 7, 22))
        r_expired = run_check(scan, None, [], [], policy, expired, [],
                              today=date(2026, 7, 22))
        r_crit = run_check(_scan_source(FIXTURE_BASE_SIMPLE), None, [],
                           crit_model, policy,
                           [{"key": "model-finding:(model):M1",
                             "reason": "x", "approved_by": "Amer Altaf",
                             "expires": "2999-01-01"}], [],
                           today=date(2026, 7, 22))
        ok = (r_good["verdict"] == "CONDITIONAL-PASS" and
              len(r_good["waivers"]["applied"]) == 1 and
              r_expired["verdict"] == "REWORK-REQUIRED" and
              len(r_expired["waivers"]["rejected"]) == 1 and
              r_crit["verdict"] == "REWORK-REQUIRED" and
              len(r_crit["waivers"]["rejected"]) == 1)
        record("waiver-ledger", ok,
               "good=%s expired=%s crit=%s" % (
                   r_good["verdict"], r_expired["verdict"],
                   r_crit["verdict"]))
    except Exception as exc:  # noqa: BLE001
        record("waiver-ledger", False, repr(exc))

    # 10 — verdict maths + malformed policy fails safe
    try:
        clean = run_check(_scan_source(FIXTURE_BASE_SIMPLE), None, [], [],
                          policy, [], [])
        degraded_only = run_check(_scan_source(FIXTURE_BASE_SIMPLE), None, [],
                                  [], policy, [], ["tool missing: lizard"])
        pol2, deg2 = load_policy("/nonexistent/policy-%d.json" % os.getpid())
        ok = (clean["verdict"] == "MAINTAINABLE" and
              clean["counts"]["blocking_open"] == 0 and
              degraded_only["verdict"] == "CONDITIONAL-PASS" and
              pol2["bands"]["unit_cyclomatic"]["high"] ==
              DEFAULT_POLICY["bands"]["unit_cyclomatic"]["high"] and
              len(deg2) == 1)
        record("verdict-maths-failsafe", ok,
               "clean=%s degraded=%s" % (clean["verdict"],
                                         degraded_only["verdict"]))
    except Exception as exc:  # noqa: BLE001
        record("verdict-maths-failsafe", False, repr(exc))

    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print("%s %-32s %s" % ("PASS" if ok else "FAIL", name, detail))
    print("%d/%d %s" % (passed, len(results),
                        "ALL PASS" if passed == len(results) else "FAILURES"))
    return 0 if passed == len(results) else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="quality.py", description=__doc__)
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("selftest")

    p_scan = sub.add_parser("scan")
    p_scan.add_argument("--files", nargs="+", required=True)
    p_scan.add_argument("--policy")
    p_scan.add_argument("--json", dest="json_out")

    p_check = sub.add_parser("check")
    p_check.add_argument("--scan", required=True)
    p_check.add_argument("--base-scan")
    p_check.add_argument("--ingest", action="append", default=[],
                         metavar="KIND:PATH")
    p_check.add_argument("--model-findings")
    p_check.add_argument("--policy")
    p_check.add_argument("--waivers")
    p_check.add_argument("--json", action="store_true")

    p_pol = sub.add_parser("policy")
    p_pol.add_argument("--policy")

    args = parser.parse_args(argv)

    if args.cmd == "selftest":
        return selftest()

    if args.cmd == "policy":
        policy, degraded = load_policy(args.policy)
        print(json.dumps({"policy": policy, "degraded": degraded}, indent=2))
        return 0

    if args.cmd == "scan":
        policy, _ = load_policy(args.policy)
        result = run_scan(args.files, policy)
        payload = json.dumps(result, indent=2)
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as fh:
                fh.write(payload)
            print("scan written: %s (%d files, %d units)" % (
                args.json_out, len(result["files"]),
                sum(len(f["units"]) for f in result["files"])))
        else:
            print(payload)
        return 0 if not result["errors"] else 2

    if args.cmd == "check":
        degraded = []
        policy, deg_p = load_policy(args.policy)
        degraded.extend(deg_p)
        try:
            with open(args.scan, "r", encoding="utf-8") as fh:
                head = json.load(fh)
        except (OSError, ValueError) as exc:
            _err("cannot read head scan: %s" % exc)
            return 2
        base = None
        if args.base_scan:
            try:
                with open(args.base_scan, "r", encoding="utf-8") as fh:
                    base = json.load(fh)
            except (OSError, ValueError) as exc:
                degraded.append("base scan unusable (%s) — ratchet clause "
                                "not evaluated" % exc)
        ingested = []
        for spec in args.ingest:
            if ":" not in spec:
                degraded.append("ingest spec '%s' malformed (want KIND:PATH)"
                                % spec)
                continue
            kind, path = spec.split(":", 1)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    if kind == "lizard":
                        payload = fh.read().splitlines()
                    else:
                        payload = json.load(fh)
                ingested.extend(ingest_rows(kind, payload))
            except (OSError, ValueError) as exc:
                degraded.append("ingest %s unusable: %s" % (spec, exc))
        model_findings = []
        if args.model_findings:
            try:
                with open(args.model_findings, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                model_findings = data.get("findings", data) \
                    if isinstance(data, dict) else data
            except (OSError, ValueError) as exc:
                degraded.append("model findings unusable: %s" % exc)
        waivers, deg_w = load_waivers(args.waivers)
        degraded.extend(deg_w)

        result = run_check(head, base, ingested, model_findings, policy,
                           waivers, degraded)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("verdict: %s  (blocking open: %d, waived: %d, "
                  "advisory: %d, degraded: %d)" % (
                      result["verdict"], result["counts"]["blocking_open"],
                      result["counts"]["waived"],
                      result["counts"]["advisory"], len(result["degraded"])))
            for c in result["clauses"]:
                print("  clause %d %-38s %s" % (c["id"], c["name"],
                                                c["status"].upper()))
        return 0 if result["verdict"] in ("MAINTAINABLE",
                                          "CONDITIONAL-PASS") else 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
