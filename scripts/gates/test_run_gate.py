#!/usr/bin/env python3
"""Tests for scripts/gates/run_gate.py (ARK-5365, ADR-059 S3).

Stdlib unittest only.  Git fixtures create throwaway repositories with
signing disabled so the suite runs on any machine.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_gate  # noqa: E402


def make_git_repo():
    tmp = tempfile.mkdtemp(prefix="gate-test-")
    def git(*args):
        subprocess.run(["git", "-C", tmp] + list(args), check=True,
                       capture_output=True)
    git("init", "-q")
    git("config", "user.email", "gate@example.invalid")
    git("config", "user.name", "Gate Test")
    git("config", "commit.gpgsign", "false")
    return tmp


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def commit_all(root):
    subprocess.run(["git", "-C", root, "add", "-A"], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", root, "commit", "-qm", "init"], check=True,
                   capture_output=True)


class MaterialHashTest(unittest.TestCase):
    def setUp(self):
        self.root = make_git_repo()
        write(os.path.join(self.root, "a.txt"), "alpha\n")
        write(os.path.join(self.root, "sub", "b.txt"), "beta\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_matches_pos_py_formula(self):
        expected = hashlib.sha256()
        for rel in ("a.txt", os.path.join("sub", "b.txt")):
            with open(os.path.join(self.root, rel), "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            expected.update(rel.encode("utf-8") + b"\0" +
                            digest.encode("ascii") + b"\n")
        material, count = run_gate.material_hash(self.root)
        self.assertEqual(material, expected.hexdigest())
        self.assertEqual(count, 2)

    def test_untracked_non_ignored_included(self):
        before, _ = run_gate.material_hash(self.root)
        write(os.path.join(self.root, "untracked.txt"), "gamma\n")
        after, count = run_gate.material_hash(self.root)
        self.assertNotEqual(before, after)
        self.assertEqual(count, 3)

    def test_proof_or_stop_excluded(self):
        before, _ = run_gate.material_hash(self.root)
        write(os.path.join(self.root, run_gate.EVDIR,
                           "stories", "x", "gates", "q.json"), "{}\n")
        after, count = run_gate.material_hash(self.root)
        self.assertEqual(before, after)
        self.assertEqual(count, 2)

    def test_content_change_sensitive(self):
        before, _ = run_gate.material_hash(self.root)
        write(os.path.join(self.root, "a.txt"), "changed\n")
        after, _ = run_gate.material_hash(self.root)
        self.assertNotEqual(before, after)


class StoryIdTest(unittest.TestCase):
    def test_task_branch_strips_b_prefix(self):
        self.assertEqual(run_gate.resolve_story_id("b-ARK-5365", None),
                         "ark-5365")

    def test_plain_branch_slugified(self):
        self.assertEqual(
            run_gate.resolve_story_id("feature/mandate-albion-secure", None),
            "feature-mandate-albion-secure")

    def test_explicit_wins(self):
        self.assertEqual(run_gate.resolve_story_id("b-ARK-5365", "ARK-5365"),
                         "ark-5365")

    def test_env_story(self):
        old = os.environ.get("POS_STORY")
        os.environ["POS_STORY"] = "ARK-9999"
        try:
            self.assertEqual(run_gate.resolve_story_id("b-ARK-5365", None),
                             "ark-9999")
        finally:
            if old is None:
                del os.environ["POS_STORY"]
            else:
                os.environ["POS_STORY"] = old


class TrivyParserTest(unittest.TestCase):
    def test_blocking_severities_only(self):
        payload = {"Results": [
            {"Target": "lock.json", "Vulnerabilities": [
                {"VulnerabilityID": "CVE-1", "Severity": "CRITICAL",
                 "Title": "bad"},
                {"VulnerabilityID": "CVE-2", "Severity": "MODERATE"},
                {"VulnerabilityID": "CVE-3", "Severity": "HIGH"}]},
            {"Target": "main.tf", "Misconfigurations": [
                {"ID": "AVD-1", "Severity": "HIGH", "Title": "open"},
                {"ID": "AVD-2", "Severity": "LOW"}]}]}
        findings = run_gate.parse_trivy(payload)
        self.assertEqual(sorted(f["rule"] for f in findings),
                         ["AVD-1", "CVE-1", "CVE-3"])
        self.assertTrue(all(f["category"] == "security" for f in findings))

    def test_empty_payload(self):
        self.assertEqual(run_gate.parse_trivy({}), [])


class OsvParserTest(unittest.TestCase):
    def test_critical_and_high_block(self):
        payload = {"results": [{"packages": [
            {"package": {"name": "lodash", "version": "4.17.4"},
             "vulnerabilities": [
                 {"id": "GHSA-1",
                  "database_specific": {"severity": "CRITICAL"}},
                 {"id": "GHSA-2",
                  "database_specific": {"severity": "HIGH"}},
                 {"id": "GHSA-3",
                  "database_specific": {"severity": "MODERATE"}},
                 {"id": "GHSA-4"}]}]}]}
        findings = run_gate.parse_osv(payload)
        self.assertEqual(sorted(f["rule"] for f in findings),
                         ["GHSA-1", "GHSA-2"])
        self.assertEqual(findings[0]["file"], "lodash@4.17.4")

    def test_missing_severity_not_blocking(self):
        payload = {"results": [{"packages": [
            {"package": {"name": "x", "version": "1"},
             "vulnerabilities": [{"id": "GHSA-9"}]}]}]}
        self.assertEqual(run_gate.parse_osv(payload), [])


class GitleaksParserTest(unittest.TestCase):
    def test_all_findings_block_as_high(self):
        leaks = [{"RuleID": "aws-key", "File": "k8s/s.yaml", "StartLine": 3},
                 {"RuleID": "generic", "File": "b.txt", "StartLine": 9}]
        findings = run_gate.parse_gitleaks(leaks)
        self.assertEqual(len(findings), 2)
        self.assertTrue(all(f["category"] == "security" for f in findings))
        self.assertEqual(findings[0]["severity"], "high")
        self.assertEqual(findings[0]["rule"], "aws-key")


class GitleaksScopeTest(unittest.TestCase):
    """stage_gitleaks scopes --log-opts to the base ref (ARK-5433):
    diff-scoped <base>..HEAD when a base ref resolves, whole-tree --all
    only when there is no base ref or it cannot be resolved."""

    def setUp(self):
        self.root = make_git_repo()
        write(os.path.join(self.root, "a.txt"), "x\n")
        commit_all(self.root)
        self._orig_run_tool = run_gate.run_tool
        self.captured = []

        def fake_run_tool(root, cmd, timeout):
            self.captured.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        run_gate.run_tool = fake_run_tool

    def tearDown(self):
        run_gate.run_tool = self._orig_run_tool
        shutil.rmtree(self.root, ignore_errors=True)

    def _log_opts(self):
        cmd = self.captured[0]
        return cmd[cmd.index("--log-opts") + 1]

    def test_base_ref_scopes_to_diff(self):
        branch = subprocess.run(
            ["git", "-C", self.root, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
        findings, ok, error = run_gate.stage_gitleaks(
            self.root, self.root, branch)
        self.assertIsNone(error)
        self.assertTrue(ok)
        self.assertEqual(self._log_opts(), "%s..HEAD" % branch)

    def test_no_base_ref_scans_whole_tree(self):
        findings, ok, error = run_gate.stage_gitleaks(self.root, self.root,
                                                      None)
        self.assertIsNone(error)
        self.assertTrue(ok)
        self.assertEqual(self._log_opts(), "--all")

    def test_unresolvable_base_ref_fails_closed_whole_tree(self):
        findings, ok, error = run_gate.stage_gitleaks(
            self.root, self.root, "no-such-ref")
        self.assertIsNone(error)
        self.assertTrue(ok)
        self.assertEqual(self._log_opts(), "--all")


class SemgrepParserTest(unittest.TestCase):
    def test_error_results_block(self):
        payload = {"results": [
            {"check_id": "ci.shell", "path": "wf.yml",
             "extra": {"severity": "ERROR", "message": "injection"}},
            {"check_id": "ci.other", "path": "x.py",
             "extra": {"severity": "WARNING"}}]}
        findings = run_gate.parse_semgrep(payload)
        self.assertEqual([f["rule"] for f in findings], ["ci.shell"])
        self.assertEqual(findings[0]["severity"], "high")


class QualMappingTest(unittest.TestCase):
    def test_verdict_mapping(self):
        self.assertEqual(run_gate.map_qual_verdict("REWORK-REQUIRED"), "block")
        self.assertEqual(run_gate.map_qual_verdict("MAINTAINABLE"), "pass")
        self.assertEqual(run_gate.map_qual_verdict("CONDITIONAL-PASS"), "pass")

    def test_clause5_categorisation(self):
        self.assertEqual(
            run_gate.categorise_qual_finding({"rule": "ratchet-cyclomatic"}),
            "clause-5")
        self.assertEqual(
            run_gate.categorise_qual_finding({"rule": "structural-sloc"}),
            "clause-5")
        self.assertEqual(
            run_gate.categorise_qual_finding({"rule": "docstring-ratio"}),
            "quality")
        self.assertEqual(
            run_gate.categorise_qual_finding({"rule": "model-finding"}),
            "quality")

    def test_gate_policy_demotes_non_clause5(self):
        policy = run_gate.build_gate_policy()
        for rule in ("clone-in-diff", "docstring-ratio", "suppression-bare"):
            self.assertNotIn(rule, policy["blocking_rules"])
        for rule in ("structural-cyclomatic", "structural-cognitive",
                     "structural-sloc", "structural-nesting",
                     "structural-params", "ratchet-cyclomatic",
                     "ratchet-cognitive", "ratchet-sloc", "ratchet-nesting",
                     "model-finding"):
            self.assertIn(rule, policy["blocking_rules"])


class DocsOnlyTest(unittest.TestCase):
    def test_all_docs(self):
        self.assertTrue(run_gate.is_docs_only(["README.md", "docs/a.adoc"]))

    def test_mixed(self):
        self.assertFalse(run_gate.is_docs_only(["README.md", "x.py"]))

    def test_empty_is_not_docs_only(self):
        self.assertFalse(run_gate.is_docs_only([]))


class ArtefactTest(unittest.TestCase):
    def setUp(self):
        self.root = make_git_repo()
        write(os.path.join(self.root, "a.txt"), "x\n")
        commit_all(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_schema_shape(self):
        artefact = run_gate.build_verdict("secure", "pass", "ok", [],
                                          "ark-5365", self.root)
        self.assertEqual(artefact["schema"], "pos-gate/1")
        self.assertEqual(artefact["kind"], "gateVerdict")
        self.assertEqual(artefact["gate"], "secure")
        self.assertEqual(artefact["verdict"], "pass")
        self.assertIsNone(artefact["attestation"])
        self.assertRegex(artefact["materialHash"], r"^[0-9a-f]{64}$")
        self.assertRegex(artefact["commitSha"], r"^[0-9a-f]{7,40}$")
        self.assertRegex(artefact["createdAt"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertEqual(artefact["story"], "ark-5365")

    def test_write_and_reload(self):
        finding = {"category": "quality", "rule": "x", "severity": "high",
                   "file": "a.py", "message": "m"}
        artefact = run_gate.build_verdict("qual", "block", "bad", [finding],
                                          "ark-5365", self.root)
        path = run_gate.emit_verdict(artefact, self.root, "ark-5365")
        self.assertIn(os.path.join("gates", "qual.json"), path)
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), artefact)


class ExitCodesTest(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(run_gate.EXIT_PASS, 0)
        self.assertEqual(run_gate.EXIT_BLOCK, 1)
        self.assertEqual(run_gate.EXIT_OPERATIONAL, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
