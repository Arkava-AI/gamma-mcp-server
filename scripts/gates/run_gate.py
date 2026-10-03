#!/usr/bin/env python3
"""run_gate.py — headless mechanical gate runner (ARK-5365, ADR-059 S3).

Executes the deterministic mechanical checks for the albion-secure and
albion-qual gates and emits verdict artefacts in the ARK-5364 schema
(pos-gate/1) at .proof-or-stop/stories/<story>/gates/<kind>.json, bound to
the gate-relevant material hash (pos.py-exact algorithm) and the HEAD
commit SHA.  pos.py `gate` verification consumes these artefacts.

Verdict provenance (ADR-059 S3): the CI run itself is the attestation —
the runner's own execution on the PR's own tree is forge-proof by
construction.  The attestation field stays null in v1; server-side
attestation mechanics are ARK-5364 schema surface only.

Exit codes: 0 pass, 1 block, 2 operational failure (fail-closed).

Stdlib only, Python 3.9+.
"""

import argparse
import copy
import datetime
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True

EVDIR = ".proof-or-stop"
GATE_SCHEMA = "pos-gate/1"
GATE_KIND = "gateVerdict"
GATE_FINDING_CATEGORIES = ("security", "quality", "clause-5")
BLOCKING_SEVERITIES = ("CRITICAL", "HIGH")

EXIT_PASS = 0
EXIT_BLOCK = 1
EXIT_OPERATIONAL = 2

VENDOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "vendor")
VENDOR_PREFIX = "scripts/gates/vendor/"
QUALITY_SCRIPT = os.path.join(VENDOR_DIR, "quality.py")

if VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)
import quality  # noqa: E402  (vendored deterministic quality engine)

# Files the qual scan never needs: documentation and workflow plumbing.
QUAL_EXCLUDE_PREFIXES = ("docs/", ".github/", VENDOR_PREFIX)
QUAL_EXCLUDE_SUFFIXES = (".md", ".mdx", ".adoc", ".rst", ".txt", ".json",
                         ".yaml", ".yml", ".toml", ".cfg", ".ini", ".svg",
                         ".png", ".jpg", ".lock")

SEMGREP_SUFFIXES = (".py", ".sh", ".yaml", ".yml", ".tf", ".js", ".ts",
                    ".go", ".rs", ".java")

DEP_BASENAMES = ("package-lock.json", "npm-shrinkwrap.json", "yarn.lock",
                 "pnpm-lock.yaml", "requirements.txt", "requirements-*.txt",
                 "Pipfile.lock", "poetry.lock", "pyproject.toml", "go.mod",
                 "go.sum", "Cargo.lock", "composer.lock", "Gemfile.lock")

DOC_SUFFIXES = (".md", ".mdx", ".adoc", ".rst", ".txt")


# --------------------------------------------------------------------------
# Git plumbing
# --------------------------------------------------------------------------

def git(root, *args, check=True):
    proc = subprocess.run(["git", "-C", root] + list(args),
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args),
                                                  proc.stderr.strip()))
    return proc


def head_hash(root):
    proc = git(root, "rev-parse", "HEAD", check=False)
    return proc.stdout.strip() if proc.returncode == 0 else "EMPTY"


def slugify(raw):
    return re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")[:64] or "story"


def resolve_story_id(branch, cli_story):
    """Mirror pos.py story resolution: explicit > POS_STORY > branch slug
    with the b- prefix stripped (task branches b-<TASKID> map to stories
    initialised under the bare task id).  Detached HEADs resolve to the
    pos.py fallback slug "story"."""
    if cli_story:
        return slugify(cli_story)
    env = os.environ.get("POS_STORY")
    if env:
        return slugify(env)
    if branch in ("HEAD", ""):
        branch = "story"
    slug = slugify(branch)
    if slug.startswith("b-") and len(slug) > 2:
        return slug[2:]
    return slug


# --------------------------------------------------------------------------
# Material hash — pos.py-exact algorithm (ARK-5364)
# --------------------------------------------------------------------------

def listed_files(root):
    tracked = git(root, "ls-files", "-z").stdout.split("\0")
    untracked = git(root, "ls-files", "--others", "--exclude-standard",
                    "-z").stdout.split("\0")
    files = set(f for f in tracked + untracked if f)
    files = [f for f in files
             if f != EVDIR and not f.startswith(EVDIR + "/")]
    return sorted(files)


def file_digest(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except FileNotFoundError:
        return "MISSING"
    except IsADirectoryError:
        return "DIR"
    except PermissionError:
        return "UNREADABLE"


def material_hash(root):
    h = hashlib.sha256()
    files = listed_files(root)
    for f in files:
        h.update(f.encode("utf-8") + b"\0" +
                 file_digest(os.path.join(root, f)).encode("ascii") + b"\n")
    return h.hexdigest(), len(files)


# --------------------------------------------------------------------------
# Verdict artefact (pos-gate/1)
# --------------------------------------------------------------------------

def now_iso():
    return (datetime.datetime.now(datetime.timezone.utc)
            .isoformat(timespec="seconds").replace("+00:00", "Z"))


def build_verdict(gate, verdict, summary, findings, story, root):
    material, _ = material_hash(root)
    return {
        "schema": GATE_SCHEMA,
        "kind": GATE_KIND,
        "story": story,
        "gate": gate,
        "verdict": verdict,
        "summary": summary,
        "materialHash": material,
        "commitSha": head_hash(root),
        "findings": findings,
        "attestation": None,
        "createdAt": now_iso(),
    }


def emit_verdict(artefact, root, story):
    sdir = os.path.join(root, EVDIR, "stories", story)
    gdir = os.path.join(sdir, "gates")
    os.makedirs(gdir, exist_ok=True)
    gi = os.path.join(root, EVDIR, ".gitignore")
    if not os.path.exists(gi):
        with open(gi, "w", encoding="utf-8") as fh:
            fh.write("*\n")
    path = os.path.join(gdir, "%s.json" % artefact["gate"])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(artefact, fh, sort_keys=True, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path


# --------------------------------------------------------------------------
# Secure-stage parsers (FORMAT:PATH outputs -> pos-gate/1 findings)
# --------------------------------------------------------------------------

def _sec_finding(rule, severity, file, message):
    return {"category": "security", "rule": rule, "severity": severity,
            "file": file, "message": message}


def parse_trivy(payload):
    findings = []
    for result in payload.get("Results", []):
        target = result.get("Target", "")
        for vuln in result.get("Vulnerabilities", []) or []:
            if vuln.get("Severity") in BLOCKING_SEVERITIES:
                findings.append(_sec_finding(
                    str(vuln.get("VulnerabilityID", "unknown")),
                    vuln["Severity"].lower(), target,
                    str(vuln.get("Title", ""))))
        for mis in result.get("Misconfigurations", []) or []:
            if mis.get("Severity") in BLOCKING_SEVERITIES:
                findings.append(_sec_finding(
                    str(mis.get("ID", "unknown")), mis["Severity"].lower(),
                    target, str(mis.get("Title", ""))))
    return findings


def parse_osv(payload):
    findings = []
    for result in payload.get("results", []) or []:
        for pkg in result.get("packages", []) or []:
            ident = "%s@%s" % (pkg.get("package", {}).get("name", "unknown"),
                               pkg.get("package", {}).get("version", "?"))
            for vuln in pkg.get("vulnerabilities", []) or []:
                severity = (vuln.get("database_specific", {}) or {}).get(
                    "severity")
                if severity in BLOCKING_SEVERITIES:
                    findings.append(_sec_finding(
                        str(vuln.get("id", "unknown")), severity.lower(),
                        ident, "known vulnerability in %s" % ident))
    return findings


def parse_gitleaks(leaks):
    findings = []
    for leak in leaks or []:
        findings.append(_sec_finding(
            str(leak.get("RuleID", "unknown")), "high",
            str(leak.get("File", "unknown")),
            "secret detected at line %s" % leak.get("StartLine", "?")))
    return findings


def parse_semgrep(payload):
    findings = []
    for result in payload.get("results", []) or []:
        extra = result.get("extra", {}) or {}
        if extra.get("severity") == "ERROR":
            findings.append(_sec_finding(
                str(result.get("check_id", "unknown")), "high",
                str(result.get("path", "unknown")),
                str(extra.get("message", ""))))
    return findings


# --------------------------------------------------------------------------
# Qual mapping (vendored quality.py verdicts -> pos-gate/1 findings)
# --------------------------------------------------------------------------

def map_qual_verdict(qual_verdict):
    if qual_verdict == "REWORK-REQUIRED":
        return "block"
    return "pass"


def categorise_qual_finding(finding):
    rule = finding.get("rule", "")
    if rule.startswith("structural-") or rule.startswith("ratchet-"):
        return "clause-5"
    return "quality"


def build_gate_policy():
    """Gate policy: ADR-059 blocks on clause-5 (simplicity principle)
    violations and model findings only.  clone-in-diff (clause 2),
    docstring-ratio (clause 3) and suppression-bare (clause 4) are
    demoted to advisory — they are not clause-5 surfaces."""
    policy = copy.deepcopy(quality.DEFAULT_POLICY)
    policy["blocking_rules"] = [
        "structural-cyclomatic", "structural-cognitive", "structural-sloc",
        "structural-nesting", "structural-params",
        "ratchet-cyclomatic", "ratchet-cognitive", "ratchet-sloc",
        "ratchet-nesting", "model-finding",
    ]
    return policy


# --------------------------------------------------------------------------
# Change surface
# --------------------------------------------------------------------------

def resolve_ref(root, ref):
    """Resolve a base ref across checkout layouts: bare branch names in
    CI checkouts only exist under refs/remotes/origin/."""
    for candidate in (ref, "origin/%s" % ref,
                      "refs/remotes/origin/%s" % ref):
        if git(root, "rev-parse", "--verify", "--quiet",
               candidate + "^{commit}", check=False).returncode == 0:
            return candidate
    return None


def changed_files(root, base_ref):
    if not base_ref:
        return []
    resolved = resolve_ref(root, base_ref)
    if not resolved:
        return []
    proc = git(root, "diff", "--name-only", "%s...HEAD" % resolved,
               check=False)
    if proc.returncode != 0:
        return []
    return [line for line in proc.stdout.splitlines() if line.strip()]


def is_docs_only(files):
    if not files:
        return False
    return all(f.lower().endswith(DOC_SUFFIXES) for f in files)


def qual_source_files(root):
    files = []
    for f in listed_files(root):
        if f.startswith(QUAL_EXCLUDE_PREFIXES):
            continue
        if f.lower().endswith(QUAL_EXCLUDE_SUFFIXES):
            continue
        files.append(f)
    return files


# --------------------------------------------------------------------------
# Secure stages — each returns (findings, ok, error)
# --------------------------------------------------------------------------

def run_tool(root, cmd, timeout):
    return subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                          timeout=timeout)


def _load_json(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def stage_trivy_fs(root, out):
    path = os.path.join(out, "trivy-fs.json")
    proc = run_tool(root, ["trivy", "fs", "--format", "json",
                           "--severity", "HIGH,CRITICAL", "--exit-code", "1",
                           "--ignore-unfixed", "--output", path, "."],
                    timeout=600)
    if proc.returncode not in (0, 1):
        return [], False, "trivy fs failed (exit %s)" % proc.returncode
    return parse_trivy(_load_json(path) or {}), proc.returncode == 0, None


def stage_trivy_config(root, out):
    path = os.path.join(out, "trivy-config.json")
    proc = run_tool(root, ["trivy", "config", "--format", "json",
                           "--severity", "HIGH,CRITICAL", "--exit-code", "1",
                           "--output", path, "."], timeout=600)
    if proc.returncode not in (0, 1):
        return [], False, "trivy config failed (exit %s)" % proc.returncode
    return parse_trivy(_load_json(path) or {}), proc.returncode == 0, None


def stage_gitleaks(root, out, base_ref):
    """Diff-scoped when a base ref is given (archaeological findings in
    history outside this PR are not its regression); whole-tree `--all`
    only on an empty base ref (dispatch mode fails closed on structural
    debt by design)."""
    path = os.path.join(out, "gitleaks.json")
    resolved = resolve_ref(root, base_ref) if base_ref else None
    log_opts = "%s..HEAD" % resolved if resolved else "--all"
    proc = run_tool(root, ["gitleaks", "detect", "--source", ".",
                           "--config", ".gitleaks.toml", "--redact",
                           "--exit-code", "1", "--report-format", "json",
                           "--report-path", path,
                           "--log-opts", log_opts], timeout=600)
    if proc.returncode not in (0, 1):
        return [], False, "gitleaks failed (exit %s)" % proc.returncode
    return parse_gitleaks(_load_json(path) or []), proc.returncode == 0, None


def _is_dep_surface(path):
    base = os.path.basename(path)
    for pattern in DEP_BASENAMES:
        if "*" in pattern:
            if fnmatch.fnmatch(base, pattern):
                return True
        elif base == pattern:
            return True
    return False


def osv_targets_for(root, base_ref):
    """Dependency surfaces to scan, or None to skip the stage.  Whole
    tree without a base ref; otherwise only changed dependency surfaces —
    pre-existing vulnerable pins in unchanged manifests are not this
    PR's regression (the scheduled osv-scanner.yml workflow covers the
    full tree advisorially)."""
    if not base_ref:
        return ["."]
    changed = [f for f in changed_files(root, base_ref)
               if _is_dep_surface(f)]
    return changed or None


def stage_osv(root, out, base_ref):
    targets = osv_targets_for(root, base_ref)
    if targets is None:
        return [], True, None
    path = os.path.join(out, "osv.json")
    cmd = ["osv-scanner", "scan", "--format", "json", "--output", path]
    if targets == ["."]:
        cmd.append("--recursive")
    proc = run_tool(root, cmd + targets, timeout=600)
    if proc.returncode not in (0, 1):
        return [], False, "osv-scanner failed (exit %s)" % proc.returncode
    return parse_osv(_load_json(path) or {}), proc.returncode == 0, None


def semgrep_targets_for(root, base_ref):
    """Diff-scoped targets, or None to skip the stage.  Pre-existing
    findings in unchanged files are not this PR's regression; an empty
    diff skips the stage rather than widening to the whole tree."""
    if not base_ref:
        return None
    changed = [f for f in changed_files(root, base_ref)
               if not f.startswith(QUAL_EXCLUDE_PREFIXES)
               and not f.startswith(VENDOR_PREFIX)
               and f.lower().endswith(SEMGREP_SUFFIXES)]
    return changed or None


def stage_semgrep(root, out, base_ref):
    targets = semgrep_targets_for(root, base_ref)
    if targets is None:
        return [], True, None
    path = os.path.join(out, "semgrep.json")
    proc = run_tool(root, ["semgrep", "scan", "--config", "p/ci",
                           "--metrics=off", "--quiet", "--json",
                           "--output", path] + targets, timeout=900)
    if proc.returncode not in (0, 1):
        return [], False, "semgrep failed (exit %s)" % proc.returncode
    return parse_semgrep(_load_json(path) or {}), proc.returncode == 0, None


def stage_kustomize_render(root, out):
    rendered_dir = os.path.join(out, "rendered")
    os.makedirs(rendered_dir, exist_ok=True)
    for kf in git(root, "ls-files", "*kustomization.y*ml").stdout.split():
        d = os.path.dirname(kf)
        proc = run_tool(root, ["kustomize", "build", d], timeout=120)
        if proc.returncode != 0:
            return [], False, "kustomize build %s failed: %s" % (
                d, proc.stderr.strip()[:200])
        slug = d.replace("/", "_")
        with open(os.path.join(rendered_dir, slug + ".yaml"), "w",
                  encoding="utf-8") as fh:
            fh.write(proc.stdout)
    path = os.path.join(out, "trivy-rendered.json")
    proc = run_tool(root, ["trivy", "config", "--format", "json",
                           "--severity", "HIGH,CRITICAL", "--exit-code", "1",
                           "--output", path, rendered_dir], timeout=600)
    if proc.returncode not in (0, 1):
        return [], False, "trivy on rendered failed (exit %s)" % (
            proc.returncode)
    return parse_trivy(_load_json(path) or {}), proc.returncode == 0, None


SECURE_STAGES = (
    ("trivy-fs", stage_trivy_fs),
    ("trivy-config", stage_trivy_config),
    ("gitleaks", stage_gitleaks),
    ("osv", stage_osv),
    ("semgrep", stage_semgrep),
    ("kustomize-render", stage_kustomize_render),
)


def run_secure_stages(root, out, base_ref, verbose):
    findings = []
    stages = []
    for name, fn in SECURE_STAGES:
        if fn in (stage_osv, stage_semgrep, stage_gitleaks):
            stage_findings, ok, error = fn(root, out, base_ref)
        else:
            stage_findings, ok, error = fn(root, out)
        if error:
            return None, error
        findings.extend(stage_findings)
        stages.append({"stage": name, "ok": ok,
                       "findings": len(stage_findings)})
        if verbose:
            print("secure/%s: %s (%d)" % (
                name, "ok" if ok else "findings", len(stage_findings)),
                file=sys.stderr)
    return {"findings": findings, "stages": stages}, None


# --------------------------------------------------------------------------
# Gate drivers
# --------------------------------------------------------------------------

def gate_secure(root, story, base_ref, workdir, verbose=False):
    """Mechanical security floor: trivy fs + config, gitleaks,
    osv-scanner (diff-scoped), semgrep (diff-scoped), kustomize render
    + trivy on rendered output."""
    out = os.path.join(workdir, "secure")
    os.makedirs(out, exist_ok=True)
    result, error = run_secure_stages(root, out, base_ref, verbose)
    if error:
        return None, error
    findings = result["findings"]
    verdict = "block" if findings else "pass"
    summary = ("albion-secure mechanical floor: %d blocking finding(s) "
               "across %d stages" % (len(findings),
                                     len(result["stages"]))) \
        if findings else "albion-secure mechanical floor: all stages clean"
    return {"verdict": verdict, "summary": summary, "findings": findings,
            "stages": result["stages"]}, None


def _write_gate_policy(out):
    policy_path = os.path.join(out, "gate-policy.json")
    with open(policy_path, "w", encoding="utf-8") as fh:
        json.dump(build_gate_policy(), fh, sort_keys=True, indent=2)
    return policy_path


def _scan_head(root, out, files):
    scan_path = os.path.join(out, "scan.json")
    proc = run_tool(root, [sys.executable, QUALITY_SCRIPT, "scan",
                           "--files"] + files + ["--json", scan_path],
                    timeout=600)
    if proc.returncode != 0:
        return None, "quality.py scan failed (exit %s)" % proc.returncode
    return scan_path, None


def _base_scan(root, out, base_ref, workdir):
    """Scan the merge-base tree for the ratchet; None when unavailable
    (quality.py then degrades the ratchet clause instead of failing)."""
    resolved = resolve_ref(root, base_ref)
    if not resolved:
        return None
    base_files = [f for f in git(root, "ls-tree", "-r", "--name-only",
                                 resolved).stdout.split()
                  if not f.startswith(QUAL_EXCLUDE_PREFIXES)
                  and not f.startswith(VENDOR_PREFIX)
                  and not f.lower().endswith(QUAL_EXCLUDE_SUFFIXES)]
    if not base_files:
        return None
    archive = subprocess.run(["git", "-C", root, "archive", resolved],
                             capture_output=True)
    base_root = os.path.join(workdir, "base-tree")
    os.makedirs(base_root, exist_ok=True)
    tar = subprocess.run(["tar", "-x", "-C", base_root],
                         input=archive.stdout, capture_output=True)
    if tar.returncode != 0:
        return None
    present = [f for f in base_files
               if os.path.exists(os.path.join(base_root, f))]
    if not present:
        return None
    base_scan = os.path.join(out, "base-scan.json")
    proc = run_tool(base_root,
                    [sys.executable, QUALITY_SCRIPT, "scan", "--files"]
                    + present + ["--json", base_scan], timeout=600)
    return base_scan if proc.returncode == 0 else None


def gate_qual(root, story, base_ref, workdir, verbose=False):
    """Mechanical quality floor via the vendored quality.py engine:
    scan + check with the gate policy (clause-5 proxies + model findings
    only), ratcheted against the merge-base when one is given.
    Docs-only diffs skip the scan stages (mechanical floor still runs:
    the artefact is still emitted and bound to the tree)."""
    out = os.path.join(workdir, "qual")
    os.makedirs(out, exist_ok=True)
    policy_path = _write_gate_policy(out)

    changed = changed_files(root, base_ref) if base_ref else None
    if changed is not None and is_docs_only(changed):
        return {"verdict": "pass",
                "summary": "albion-qual mechanical floor: docs-only diff, "
                           "scan stages skipped",
                "findings": [], "engine": quality.ENGINE_VERSION,
                "degraded": []}, None

    scan_path, error = _scan_head(root, out, qual_source_files(root))
    if error:
        return None, error
    cmd = [sys.executable, QUALITY_SCRIPT, "check", "--scan", scan_path,
           "--policy", policy_path, "--json"]
    base_scan = _base_scan(root, out, base_ref, workdir) if base_ref else None
    if base_scan:
        cmd += ["--base-scan", base_scan]
    proc = run_tool(root, cmd, timeout=600)
    if proc.returncode not in (0, 1, 2):
        return None, "quality.py check failed (exit %s)" % proc.returncode
    try:
        report = json.loads(proc.stdout)
    except ValueError:
        return None, "quality.py check produced no report (exit %s)" % (
            proc.returncode)
    verdict = map_qual_verdict(report.get("verdict", "REWORK-REQUIRED"))
    findings = []
    for f in report.get("findings", []):
        if not f.get("blocking"):
            continue
        findings.append({
            "category": categorise_qual_finding(f),
            "rule": str(f.get("rule", "unknown")),
            "severity": str(f.get("severity", "high")),
            "file": str(f.get("file", "unknown")),
            "message": str(f.get("message", "")),
        })
    summary = "albion-qual mechanical floor: %s (%d blocking finding(s))" % (
        report.get("verdict"), len(findings))
    return {"verdict": verdict, "summary": summary, "findings": findings,
            "engine": report.get("engine_version"),
            "degraded": report.get("degraded", [])}, None


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="run_gate.py",
        description="Headless mechanical gate runner (ADR-059 S3)")
    parser.add_argument("gate", choices=["secure", "qual"])
    parser.add_argument("--story", default=None,
                        help="story id (default: branch slug, b- stripped)")
    parser.add_argument("--base-ref", default=None,
                        help="merge-base ref for diff-scoped stages")
    parser.add_argument("--workdir", default=None,
                        help="scratch dir for scan outputs")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    root = os.getcwd()
    if git(root, "rev-parse", "--git-dir", check=False).returncode != 0:
        print("run_gate.py: not a git checkout: %s" % root, file=sys.stderr)
        return EXIT_OPERATIONAL

    story = resolve_story_id(
        git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        or "story", args.story)
    workdir = args.workdir or os.path.join(root, EVDIR, "stories", story,
                                           "gate-work")
    if os.path.isdir(workdir):
        shutil.rmtree(workdir)
    os.makedirs(workdir, exist_ok=True)

    driver = gate_secure if args.gate == "secure" else gate_qual
    try:
        result, error = driver(root, story, args.base_ref, workdir,
                               verbose=args.verbose)
    except (subprocess.TimeoutExpired, RuntimeError, OSError) as exc:
        result, error = None, str(exc)
    if error:
        print("run_gate.py: operational failure: %s" % error, file=sys.stderr)
        return EXIT_OPERATIONAL

    artefact = build_verdict(args.gate, result["verdict"],
                             result["summary"], result["findings"],
                             story, root)
    path = emit_verdict(artefact, root, story)
    print("gate %s: %s (%s)" % (args.gate, result["verdict"], path))
    print(json.dumps({"verdict": result["verdict"],
                      "findings": len(result["findings"])}))
    return EXIT_PASS if result["verdict"] == "pass" else EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(main())
