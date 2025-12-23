import json
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List

from .storage import RUNS_DIR, write_json


def summarize(batch_id: str, site_results: List[Dict], rule_pack_id: str, version: str) -> Dict:
    summary = {
        "batch_id": batch_id,
        "rule_pack_id": rule_pack_id,
        "rule_pack_version": version,
        "sites": [],
    }
    issues = []
    failures = []
    for result in site_results:
        summary["sites"].append(
            {
                "site_id": result["site_id"],
                "status": result["status"],
                "coverage": result.get("coverage_stats", {}),
            }
        )
        for rule_result in result.get("rule_results", []):
            if rule_result.get("status") == "FAIL":
                issues.append(
                    {
                        "site_id": result["site_id"],
                        "rule_id": rule_result.get("rule_id"),
                        "reason": rule_result.get("reason"),
                        "evidence": rule_result.get("evidence", []),
                    }
                )
        if result.get("status") == "partial" and result.get("failure_reason"):
            failures.append(
                {
                    "site_id": result["site_id"],
                    "reason": result.get("failure_reason"),
                    "trace": result.get("trace_path"),
                    "last_url": result.get("failure_url"),
                    "screenshot": result.get("failure_screenshot"),
                }
            )
    base_dir = RUNS_DIR / batch_id / "export"
    base_dir.mkdir(parents=True, exist_ok=True)
    summary_path = base_dir / "summary.json"
    issues_path = base_dir / "issues.json"
    failures_path = base_dir / "failures.json"
    write_json(summary_path, summary)
    write_json(issues_path, issues)
    write_json(failures_path, failures)
    evidence_zip = create_evidence_zip(batch_id)
    return {
        "summary": str(summary_path),
        "issues": str(issues_path),
        "failures": str(failures_path),
        "evidence_zip": evidence_zip,
    }


def create_evidence_zip(batch_id: str) -> str:
    run_dir = RUNS_DIR / batch_id
    export_dir = run_dir / "export"
    evidence_zip = export_dir / "evidence.zip"
    with zipfile.ZipFile(evidence_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in run_dir.rglob("*"):
            if path.is_dir():
                continue
            if str(export_dir) in str(path):
                continue
            zf.write(path, path.relative_to(run_dir))
    return str(evidence_zip)
