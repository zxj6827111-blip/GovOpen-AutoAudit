"""
Markdown报告生成器
从summary.json, issues.json, failures.json生成人类可读的报告
"""
from typing import Dict
from pathlib import Path


def generate_markdown_report(
    summary: Dict,
    issues: Dict,
    failures: Dict,
    output_path: Path
) -> str:
    """生成Markdown报告"""
    
    md = []
    
    # 标题和元数据
    md.append(f"# 批次评估报告\n\n")
    md.append(f"**批次ID**: `{summary['batch_id']}`  \n")
    md.append(f"**规则包**: {summary['rule_pack_id']} v{summary['rule_pack_version']}  \n")
    md.append(f"**评估时间**: {summary.get('timestamp', 'N/A')}  \n")
    md.append(f"**状态**: {summary.get('status', 'unknown').upper()}  \n")
    md.append("\n---\n\n")
    
    # 统计概览
    stats = summary.get('statistics', {})
    md.append("## 📊 评估概览\n\n")
    md.append(f"- **总站点数**: {stats.get('total_sites', 0)}\n")
    md.append(f"- **总规则数**: {stats.get('total_rules', 0)}\n")
    md.append(f"- **抓取页面数**: {stats.get('total_pages_fetched', 0)}\n")
    md.append("\n")
    
    # 规则结果统计
    rule_results = stats.get('rule_results', {})
    md.append("### 规则评估结果\n\n")
    md.append(f"- ✅ **PASS**: {rule_results.get('PASS', 0)}\n")
    md.append(f"- ❌ **FAIL**: {rule_results.get('FAIL', 0)}\n")
    md.append(f"- ⚠️ **UNCERTAIN**: {rule_results.get('UNCERTAIN', 0)}\n")
    md.append(f"- 🔒 **NOT-ASSESSABLE**: {rule_results.get('NOT-ASSESSABLE', 0)}\n")
    md.append("\n")
    
    # 通过率
    pass_rate = stats.get('pass_rate', 0)
    fail_rate = stats.get('fail_rate', 0)
    uncertain_rate = stats.get('uncertain_rate', 0)
    
    md.append("### 通过率分析\n\n")
    md.append(f"- **通过率**: {pass_rate:.1%}\n")
    md.append(f"- **失败率**: {fail_rate:.1%}\n")
    md.append(f"- **不确定率**: {uncertain_rate:.1%}\n")
    md.append("\n---\n\n")
    
    # 站点结果概览
    md.append("## 🏢 站点结果概览\n\n")
    site_results = summary.get('site_results', [])
    
    if site_results:
        md.append("| 站点ID | 状态 | PASS | FAIL | UNCERTAIN |\n")
        md.append("|--------|------|------|------|----------|\n")
        
        for site in site_results:
            site_id = site.get('site_id', 'unknown')
            status_icon = "✅" if site.get('status') == "done" else "⚠️"
            md.append(f"| {site_id} | {status_icon} {site.get('status', 'unknown')} | "
                     f"{site.get('pass_count', 0)} | "
                     f"{site.get('fail_count', 0)} | "
                     f"{site.get('uncertain_count', 0)} |\n")
        md.append("\n")
    else:
        md.append("无站点数据。\n\n")
    
    md.append("---\n\n")
    
    # 不符合项详情
    md.append("## ❌ 不符合项明细\n\n")
    issue_list = issues.get('issues', [])
    total_issues = issues.get('total_issues', 0)
    
    if total_issues > 0:
        md.append(f"**共发现 {total_issues} 个不符合项**\n\n")
        md.append("| Issue ID | 规则ID | 站点ID | 原因 | 证据数量 |\n")
        md.append("|----------|--------|--------|------|----------|\n")
        
        for issue in issue_list[:50]:  # 最多显示50个
            issue_id = issue.get('issue_id', 'N/A')
            rule_id = issue.get('rule_id', 'N/A')
            site_id = issue.get('site_id', 'N/A')
            reason = issue.get('reason', 'N/A')
            evidence_count = len(issue.get('evidence_ids', []))
            
            md.append(f"| {issue_id} | `{rule_id}` | {site_id} | {reason} | {evidence_count} |\n")
        
        if total_issues > 50:
            md.append(f"\n*（仅显示前50个，共{total_issues}个不符合项）*\n")
    else:
        md.append("✅ **无不符合项** - 所有规则均PASS或UNCERTAIN！\n")
    
    md.append("\n---\n\n")
    
    # 失败信息
    md.append("## ⚠️ 站点级失败\n\n")
    failure_list = failures.get('failures', [])
    total_failures = failures.get('total_failures', 0)
    
    if total_failures > 0:
        md.append(f"**共发现 {total_failures} 个站点级失败**\n\n")
        md.append("| 站点ID | 失败原因 | 最后访问URL |\n")
        md.append("|--------|----------|-------------|\n")
        
        for failure in failure_list:
            site_id = failure.get('site_id', 'N/A')
            reason = failure.get('reason', 'N/A')
            last_url = failure.get('last_url', 'N/A')
            md.append(f"| {site_id} | {reason} | {last_url} |\n")
        md.append("\n")
    else:
        md.append("✅ 无站点级失败。\n\n")
    
    md.append("---\n\n")
    
    # 证据
    md.append("## 📦 证据包\n\n")
    md.append("所有证据文件已打包至 `evidence.zip`，包含：\n")
    md.append("- 截图文件 (`.jpg`)\n")
    md.append("- 页面快照 (`.html`)\n")
    md.append("- 追踪日志 (`trace.json`)\n\n")
    
    # 写入文件
    report_content = "".join(md)
    output_path.write_text(report_content, encoding="utf-8")
    
    return str(output_path)
