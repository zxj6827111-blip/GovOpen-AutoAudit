#!/usr/bin/env python3
"""
详细检测报告生成器
生成包含每条规则检查依据、截图证据和评分明细的Markdown报告
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class DetailedReportGenerator:
    """生成详细的Markdown格式检测报告"""
    
    def __init__(self, batch_dir: Path):
        """
        Args:
            batch_dir: 批次目录路径，如 runs/batch_xxx
        """
        self.batch_dir = Path(batch_dir)
        self.export_dir = self.batch_dir / "export"
        self.summary_data = None
        self.issues_data = None
        self.rule_results = {}
        
    def load_data(self):
        """加载批次数据"""
        # 加载summary
        summary_path = self.export_dir / "summary.json"
        if summary_path.exists():
            with open(summary_path, 'r', encoding='utf-8') as f:
                self.summary_data = json.load(f)
        
        # 加载issues
        issues_path = self.export_dir / "issues.json"
        if issues_path.exists():
            with open(issues_path, 'r', encoding='utf-8') as f:
                self.issues_data = json.load(f)
        
        # 加载每个站点的详细结果
        for site_dir in self.batch_dir.glob("site_*"):
            site_id = site_dir.name.replace("site_", "")
            trace_path = site_dir / "trace.json"
            
            if trace_path.exists():
                with open(trace_path, 'r', encoding='utf-8') as f:
                    trace = json.load(f)
                self.rule_results[site_id] = {
                    "trace": trace,
                    "screenshots": list(site_dir.glob("screenshot_*.jpg")),
                    "dir": site_dir
                }
    
    def generate_report(self, rulepack_path: Optional[Path] = None) -> str:
        """
        生成详细Markdown报告
        
        Args:
            rulepack_path: 规则包路径，用于获取规则中文描述
            
        Returns:
            报告内容字符串
        """
        self.load_data()
        
        # 加载规则包获取中文描述
        rules_dict = {}
        items_dict = {}
        rulepack_meta = {}
        
        if rulepack_path:
            rules_path = Path(rulepack_path) / "rules.json"
            rulepack_json = Path(rulepack_path) / "rulepack.json"
            
            if rules_path.exists():
                with open(rules_path, 'r', encoding='utf-8') as f:
                    rules_list = json.load(f)
                    for rule in rules_list:
                        rules_dict[rule["rule_id"]] = rule
            
            if rulepack_json.exists():
                with open(rulepack_json, 'r', encoding='utf-8') as f:
                    rulepack_meta = json.load(f)
                    # 构建items字典
                    for item in rulepack_meta.get("scoring", {}).get("items", []):
                        items_dict[item["item_id"]] = item
        
        # 构建报告
        lines = []
        
        # 报告头部
        lines.append("# 政务公开检测详细报告\n")
        lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 基本信息
        lines.append("## 📋 基本信息\n")
        lines.append("| 项目 | 内容 |")
        lines.append("|------|------|")
        
        if self.summary_data:
            lines.append(f"| 检测批次 | `{self.summary_data.get('batch_id', 'N/A')}` |")
            lines.append(f"| 检测时间 | {self.summary_data.get('timestamp', 'N/A')} |")
            lines.append(f"| 规则包 | {self.summary_data.get('rule_pack_id', 'N/A')} |")
        
        if rulepack_meta:
            indicator = rulepack_meta.get("indicator", {})
            lines.append(f"| 检测指标 | {indicator.get('indicator_name', 'N/A')} |")
            lines.append(f"| 满分 | {indicator.get('full_score', 0)} 分 |")
        
        lines.append("")
        
        # 统计摘要
        lines.append("## 📊 检测结果统计\n")
        
        if self.summary_data and self.summary_data.get("statistics"):
            stats = self.summary_data["statistics"]
            total = stats.get("total_rules", 0)
            passed = stats.get("pass", 0)
            failed = stats.get("fail", 0)
            uncertain = stats.get("uncertain", 0)
            
            # 计算通过率
            pass_rate = (passed / total * 100) if total > 0 else 0
            
            lines.append(f"| 状态 | 数量 | 占比 |")
            lines.append("|------|------|------|")
            lines.append(f"| ✅ 通过 | {passed} | {pass_rate:.1f}% |")
            lines.append(f"| ❌ 未通过 | {failed} | {(failed/total*100) if total > 0 else 0:.1f}% |")
            lines.append(f"| ⚠️ 不确定 | {uncertain} | {(uncertain/total*100) if total > 0 else 0:.1f}% |")
            lines.append(f"| **总计** | **{total}** | 100% |")
            lines.append("")
        
        # 分隔线
        lines.append("---\n")
        
        # 详细检查结果
        lines.append("## 📝 检查明细\n")
        
        # 遍历每个检查项（如果有规则包元数据）
        if items_dict:
            for item_id, item in items_dict.items():
                lines.append(f"### {item_id} {item.get('item_name', '')}\n")
                lines.append(f"**满分：{item.get('full_score', 0)}分 | 单项扣分上限：{item.get('cap_deduction', 0)}分**\n")
                
                # 找到该检查项下的所有规则
                item_rules = [r for r in rules_dict.values() if r.get("item_id") == item_id]
                
                if item_rules:
                    lines.append("| 检查要素 | 状态 | 所在栏目 | 匹配依据 | 扣分 |")
                    lines.append("|----------|------|----------|----------|------|")
                    
                    for rule in item_rules:
                        rule_id = rule["rule_id"]
                        element = rule.get("element", rule_id)
                        
                        # 查找该规则的检测结果
                        result = self._find_rule_result(rule_id)
                        
                        if result:
                            status = result.get("status", "UNCERTAIN")
                            status_icon = "✅" if status == "PASS" else ("❌" if status == "FAIL" else "⚠️")
                            column = result.get("matched_column", "-")
                            keywords = ", ".join(result.get("matched_keywords", [])) or result.get("detail", "-")
                            deduction = result.get("score_delta", 0)
                        else:
                            status_icon = "⚠️"
                            column = "-"
                            keywords = "未检测"
                            deduction = 0
                        
                        lines.append(f"| {element} | {status_icon} | {column} | {keywords[:30]}{'...' if len(keywords) > 30 else ''} | {deduction} |")
                    
                    lines.append("")
                
                # 添加截图证据
                lines.append("**截图证据：**\n")
                self._add_screenshots_for_item(lines, item_id, rules_dict)
                lines.append("")
        
        else:
            # 没有规则包元数据时，直接列出所有结果
            lines.append("### 规则检查结果\n")
            
            if self.issues_data:
                for issue in self.issues_data.get("issues", []):
                    rule_id = issue.get("rule_id", "")
                    status = issue.get("status", "UNCERTAIN")
                    reason = issue.get("reason", "")
                    
                    status_icon = "❌" if status == "FAIL" else "⚠️"
                    lines.append(f"- {status_icon} **{rule_id}**: {reason}")
                
                lines.append("")
        
        # 未通过规则详情
        lines.append("---\n")
        lines.append("## ❌ 未通过规则详情\n")
        
        if self.issues_data:
            for issue in self.issues_data.get("issues", []):
                if issue.get("status") == "FAIL":
                    rule_id = issue.get("rule_id", "")
                    rule_info = rules_dict.get(rule_id, {})
                    
                    lines.append(f"### {rule_id}\n")
                    lines.append(f"- **检查要素**：{rule_info.get('element', 'N/A')}")
                    lines.append(f"- **扣分**：{issue.get('score_delta', 0)} 分")
                    lines.append(f"- **原因**：{issue.get('reason', 'N/A')}")
                    lines.append(f"- **说明**：{rule_info.get('notes', 'N/A')}")
                    lines.append("")
        else:
            lines.append("*无未通过规则*\n")
        
        # 访问页面列表
        lines.append("---\n")
        lines.append("## 🔗 深度导航访问的页面\n")
        
        for site_id, site_data in self.rule_results.items():
            lines.append(f"### 站点: {site_id}\n")
            lines.append("| 序号 | 类型 | URL |")
            lines.append("|------|------|-----|")
            
            for idx, trace_item in enumerate(site_data.get("trace", []), 1):
                step = trace_item.get("step", "")
                url = trace_item.get("url", "")
                step_name = "入口页" if step == "entry" else "深度导航"
                lines.append(f"| {idx} | {step_name} | {url} |")
            
            lines.append("")
        
        # 截图列表
        lines.append("---\n")
        lines.append("## 📸 截图证据\n")
        
        for site_id, site_data in self.rule_results.items():
            screenshots = site_data.get("screenshots", [])
            if screenshots:
                lines.append(f"### 站点: {site_id}\n")
                for ss in screenshots[:10]:  # 最多显示10张
                    rel_path = ss.relative_to(self.batch_dir)
                    lines.append(f"![{ss.name}]({rel_path})\n")
        
        return "\n".join(lines)
    
    def _find_rule_result(self, rule_id: str) -> Optional[Dict]:
        """查找指定规则的检测结果"""
        # 从issues中查找
        if self.issues_data:
            for issue in self.issues_data.get("issues", []):
                if issue.get("rule_id") == rule_id:
                    return issue
        
        # TODO: 从summary中的rule_results查找更详细的结果
        return None
    
    def _add_screenshots_for_item(self, lines: List[str], item_id: str, rules_dict: Dict):
        """添加检查项相关的截图"""
        # 简化处理：显示第一个站点的前2张截图
        for site_id, site_data in self.rule_results.items():
            screenshots = site_data.get("screenshots", [])
            if screenshots:
                for ss in screenshots[:2]:
                    rel_path = ss.relative_to(self.batch_dir)
                    lines.append(f"![{item_id}证据]({rel_path})")
                break
    
    def save_report(self, output_path: Optional[Path] = None, rulepack_path: Optional[Path] = None) -> Path:
        """
        保存报告到文件
        
        Args:
            output_path: 输出路径，默认为 export/report_detail.md
            rulepack_path: 规则包路径
            
        Returns:
            报告文件路径
        """
        if output_path is None:
            output_path = self.export_dir / "report_detail.md"
        
        content = self.generate_report(rulepack_path)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"详细报告已保存到: {output_path}")
        return output_path


def generate_detailed_report(batch_id: str, rulepack_path: str = None) -> str:
    """
    便捷函数：为指定批次生成详细报告
    
    Args:
        batch_id: 批次ID，如 batch_xxx
        rulepack_path: 规则包路径
        
    Returns:
        报告文件路径
    """
    from pathlib import Path
    
    # 查找批次目录
    runs_dir = Path("runs")
    batch_dir = runs_dir / batch_id
    
    if not batch_dir.exists():
        raise FileNotFoundError(f"批次目录不存在: {batch_dir}")
    
    generator = DetailedReportGenerator(batch_dir)
    
    rulepack = Path(rulepack_path) if rulepack_path else None
    output_path = generator.save_report(rulepack_path=rulepack)
    
    return str(output_path)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python detailed_report.py <batch_id> [rulepack_path]")
        print("例如: python detailed_report.py batch_7d12190f rulepacks/suqian_zhidugongkai")
        sys.exit(1)
    
    batch_id = sys.argv[1]
    rulepack = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        path = generate_detailed_report(batch_id, rulepack)
        print(f"✅ 详细报告已生成: {path}")
    except Exception as e:
        print(f"❌ 生成报告失败: {e}")
        sys.exit(1)
