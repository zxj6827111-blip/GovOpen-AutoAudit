import json
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List

from .storage import RUNS_DIR, write_json


def summarize(batch_id: str, site_results: List[Dict], rule_pack_id: str, version: str) -> Dict:
    """生成summary.json, issues.json, failures.json和evidence.zip"""
    from datetime import datetime
    
    # 统计规则结果
    rule_stats = {"PASS": 0, "FAIL": 0, "UNCERTAIN": 0, "NOT-ASSESSABLE": 0}
    total_pages = 0
    
    for result in site_results:
        for rule_result in result.get("rule_results", []):
            status = rule_result.get("status", "UNKNOWN")
            if status in rule_stats:
                rule_stats[status] += 1
        
        # 统计页面数（如果有coverage_stats）
        coverage = result.get("coverage_stats", {})
        total_pages += coverage.get("pages_fetched", 0)
    
    total_rules = sum(rule_stats.values())
    
    # 增强的summary结构
    summary = {
        "batch_id": batch_id,
        "rule_pack_id": rule_pack_id,
        "rule_pack_version": version,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "status": "done",  # 如果所有site都done则为done
        
        "statistics": {
            "total_sites": len(site_results),
            "total_rules": total_rules,
            "total_pages_fetched": total_pages,
            
            "rule_results": rule_stats,
            
            "pass_rate": round(rule_stats["PASS"] / total_rules, 3) if total_rules > 0 else 0,
            "fail_rate": round(rule_stats["FAIL"] / total_rules, 3) if total_rules > 0 else 0,
            "uncertain_rate": round(rule_stats["UNCERTAIN"] / total_rules, 3) if total_rules > 0 else 0,
        },
        
        "site_results": []
    }
    
    # 构建site_results汇总
    for result in site_results:
        site_rule_stats = {"PASS": 0, "FAIL": 0, "UNCERTAIN": 0, "NOT-ASSESSABLE": 0}
        for rule_result in result.get("rule_results", []):
            status = rule_result.get("status", "UNKNOWN")
            if status in site_rule_stats:
                site_rule_stats[status] += 1
        
        summary["site_results"].append({
            "site_id": result["site_id"],
            "status": result["status"],
            "pass_count": site_rule_stats["PASS"],
            "fail_count": site_rule_stats["FAIL"],
            "uncertain_count": site_rule_stats["UNCERTAIN"],
            "coverage": result.get("coverage_stats", {})
        })
    
    # 生成issues.json (FAIL规则详情)
    issues = []
    issue_id = 1
    for result in site_results:
        for rule_result in result.get("rule_results", []):
            if rule_result.get("status") == "FAIL":
                issues.append({
                    "issue_id": f"issue_{issue_id}",
                    "rule_id": rule_result.get("rule_id"),
                    "site_id": result["site_id"],
                    "status": "FAIL",
                    "score_delta": rule_result.get("score_delta", 0),
                    "reason": rule_result.get("reason"),
                    "evidence_ids": rule_result.get("evidence_ids", [])
                })
                issue_id += 1
    
    issues_data = {
        "issues": issues,
        "total_issues": len(issues)
    }
    
    # 生成failures.json (站点级失败)
    failures = []
    for result in site_results:
        if result.get("status") == "partial" and result.get("failure_reason"):
            failures.append({
                "site_id": result["site_id"],
                "reason": result.get("failure_reason"),
                "trace": result.get("trace_path"),
                "last_url": result.get("failure_url"),
                "screenshot": result.get("failure_screenshot"),
            })
    
    failures_data = {
        "failures": failures,
        "total_failures": len(failures)
    }
    
    # 写入文件
    base_dir = RUNS_DIR / batch_id / "export"
    base_dir.mkdir(parents=True, exist_ok=True)
    
    summary_path = base_dir / "summary.json"
    issues_path = base_dir / "issues.json"
    failures_path = base_dir / "failures.json"
    
    write_json(summary_path, summary)
    write_json(issues_path, issues_data)
    write_json(failures_path, failures_data)
    
    evidence_zip = create_evidence_zip(batch_id)
    
    # ✅ 生成Markdown报告
    from .report_generator import generate_markdown_report
    report_path = base_dir / "report.md"
    generate_markdown_report(summary, issues_data, failures_data, report_path)
    
    return {
        "summary": str(summary_path),
        "issues": str(issues_path),
        "failures": str(failures_path),
        "evidence_zip": evidence_zip,
        "report": str(report_path)  # ✅ 新增report.md
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
