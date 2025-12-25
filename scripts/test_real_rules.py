#!/usr/bin/env python3
"""
测试真实规则评估
验证rule_engine能否正确处理jiangsu_suqian_v1_1的所有20条规则
"""
import json
import sys
from pathlib import Path

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from autoaudit.rule_engine import RuleEngine

def test_real_rules():
    # 加载真实规则
    rules_file = ROOT_DIR / "rulepacks" / "jiangsu_suqian_v1_1" / "rules.json"
    if not rules_file.exists():
        print(f"❌ Rules file not found: {rules_file}")
        return False
    
    rules = json.load(open(rules_file, encoding="utf-8"))
    print(f"✅ Loaded {len(rules)} rules from jiangsu_suqian_v1_1")
    
    # 模拟页面数据（覆盖不同场景）
    mock_pages = [
        {
            "url": "http://test.gov.cn",
            "body": "<html><body>机构设置 联系电话：025-12345 办公地址：南京市</body></html>",
            "snapshot": "test1.html",
            "site_id": "test",
            "status_code": 200
        },
        {
            "url": "http://test.gov.cn/budget",
            "body": "<html><body>财政预决算公开 2024年预算报告</body></html>",
            "snapshot": "test2.html",
            "site_id": "test",
            "status_code": 200
        },
        {
            "url": "http://test.gov.cn/search",
            "body": "<html><body><form id='search-form'>网站搜索</form></body></html>",
            "snapshot": "test3.html",
            "site_id": "test",
            "status_code": 200
        }
    ]
    
    engine = RuleEngine(rules)
    
    # 测试每种evaluator类型
    evaluator_types = {}
    success_count = 0
    error_count = 0
    
    print("\n开始测试规则评估...")
    for idx, rule in enumerate(rules, 1):
        rule_id = rule.get("rule_id", f"unknown-{idx}")
        evaluator_type = rule.get("evaluator", {}).get("type", "unknown")
        
        # 统计evaluator类型
        evaluator_types[evaluator_type] = evaluator_types.get(evaluator_type, 0) + 1
        
        try:
            result = engine._evaluate_rule(rule, mock_pages)
            status = result.get("status")
            reason = result.get("reason", "N/A")
            
            print(f"  [{idx:2d}] {rule_id:40s} | {evaluator_type:20s} | {status:12s} | {reason}")
            
            # 检查必需字段
            if "rule_id" not in result:
                print(f"    ⚠️  Missing rule_id in result")
                error_count += 1
            elif "status" not in result:
                print(f"    ⚠️  Missing status in result")
                error_count += 1
            else:
                success_count += 1
                
                # 检查FAIL必有evidence_ids
                if status == "FAIL":
                    if "evidence_ids" not in result or not result["evidence_ids"]:
                        print(f"    ❌ FAIL without evidence_ids!")
                        error_count += 1
                        success_count -= 1
                        
        except Exception as e:
            print(f"  [{idx:2d}] {rule_id:40s} | {evaluator_type:20s} | ❌ ERROR: {e}")
            error_count += 1
    
    print(f"\n" + "="*80)
    print(f"测试完成:")
    print(f"  ✅ 成功: {success_count}/{len(rules)}")
    print(f"  ❌ 失败: {error_count}/{len(rules)}")
    
    print(f"\nEvaluator类型分布:")
    for etype, count in sorted(evaluator_types.items()):
        print(f"  - {etype:25s}: {count:2d} 条规则")
    
    if error_count == 0:
        print(f"\n🎉 所有{len(rules)}条规则评估成功！")
        return True
    else:
        print(f"\n⚠️  存在{error_count}个错误，需要修复")
        return False

if __name__ == "__main__":
    success = test_real_rules()
    sys.exit(0 if success else 1)
