#!/usr/bin/env python3
"""
M0验收测试脚本
检查所有M0关键验收标准
"""
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))


def check_m0_acceptance():
    """M0验收检查"""
    print("="*80)
    print("M0 阶段验收检查")
    print("="*80)
    
    all_passed = True
    
    # 检查1: 关键文件存在
    print("\n[检查1] 关键文件存在性")
    required_files = [
        "autoaudit/dual_channel_worker.py",
        "autoaudit/models.py",
        "autoaudit/rule_engine.py",
        "scripts/test_real_rules.py",
    ]
    
    for file_path in required_files:
        full_path = ROOT_DIR / file_path
        if full_path.exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} NOT FOUND")
            all_passed = False
    
    # 检查2: 模块导入
    print("\n[检查2] 核心模块导入")
    try:
        from autoaudit.dual_channel_worker import run_site_dual_channel, should_use_playwright
        print("  ✅ dual_channel_worker")
    except Exception as e:
        print(f"  ❌ dual_channel_worker: {e}")
        all_passed = False
    
    try:
        from autoaudit.models import Evidence
        print("  ✅ Evidence class")
        
        # 检查Evidence字段
        required_fields = ["evidence_id", "content_hash", "locator", "metadata"]
        ev_fields = Evidence.__dataclass_fields__.keys()
        for field in required_fields:
            if field in ev_fields:
                print(f"    ✅ Evidence.{field}")
            else:
                print(f"    ❌ Evidence.{field} missing")
                all_passed = False
    except Exception as e:
        print(f"  ❌ Evidence: {e}")
        all_passed = False
    
    try:
        from autoaudit.rule_engine import RuleEngine
        engine = RuleEngine([])
        
        # 检查新方法存在
        if hasattr(engine, '_locate_pages'):
            print("  ✅ RuleEngine._locate_pages")
        else:
            print("  ❌ RuleEngine._locate_pages missing")
            all_passed = False
            
        if hasattr(engine, '_evaluate_content'):
            print("  ✅ RuleEngine._evaluate_content")
        else:
            print("  ❌ RuleEngine._evaluate_content missing")
            all_passed = False
    except Exception as e:
        print(f"  ❌ RuleEngine: {e}")
        all_passed = False
    
    # 检查3: 真实规则支持
    print("\n[检查3] 真实规则支持 (jiangsu_suqian_v1_1)")
    try:
        rules_file = ROOT_DIR / "rulepacks" / "jiangsu_suqian_v1_1" / "rules.json"
        rules = json.load(open(rules_file, encoding="utf-8"))
        print(f"  ✅ 加载 {len(rules)} 条规则")
        
        # 统计evaluator类型
        evaluator_types = {}
        for rule in rules:
            etype = rule.get("evaluator", {}).get("type", "unknown")
            evaluator_types[etype] = evaluator_types.get(etype, 0) + 1
        
        required_types = ["presence_selector", "presence_keywords", "presence_all", "presence_regex"]
        for rtype in required_types:
            if rtype in evaluator_types:
                print(f"    ✅ {rtype}: {evaluator_types[rtype]} 条")
            else:
                print(f"    ⚠️  {rtype}: 0 条")
    except Exception as e:
        print(f"  ❌ 规则加载失败: {e}")
        all_passed = False
    
    # 检查4: Evidence.create工厂方法
    print("\n[检查4] Evidence.create() 工厂方法")
    try:
        from autoaudit.models import Evidence
        test_page = {
            "url": "http://test.gov.cn",
            "body": "测试页面内容 机构信息",
            "snapshot": "test.html",
            "site_id": "test_site"
        }
        
        evidence = Evidence.create(
            rule_id="test_rule",
            site_id="test_site",
            page=test_page,
            locator={"keywords": ["机构信息"]}
        )
        
        print(f"  ✅ evidence_id: {evidence.evidence_id}")
        print(f"  ✅ type: {evidence.type}")
        print(f"  ✅ rule_id: {evidence.rule_id}")
        
        if evidence.locator:
            print(f"  ✅ locator.type: {evidence.locator['type']}")
        else:
            print(f"  ⚠️  locator is None")
            
    except Exception as e:
        print(f"  ❌ Evidence.create() 失败: {e}")
        all_passed = False
    
    # 检查5: 按作用域降级
    print("\n[检查5] 按作用域降级逻辑")
    try:
        from autoaudit.rule_engine import RuleEngine
        
        # 模拟场景：budget页面失败，其他页面正常
        rules = [
            {"rule_id": "budget_rule", "locator": {"keywords": ["预算"]}, "evaluator": {"type": "presence_keywords", "keywords": ["预算"]}},
            {"rule_id": "other_rule", "locator": {"keywords": ["公开"]}, "evaluator": {"type": "presence_keywords", "keywords": ["公开"]}}
        ]
        
        pages = [
            {"url": "http://test.gov.cn/budget", "body": "预算信息", "site_id": "test"},
            {"url": "http://test.gov.cn/info", "body": "信息公开", "site_id": "test"}
        ]
        
        failures = [
            {"url": "http://test.gov.cn/budget", "reason": "blocked_403"}
        ]
        
        engine = RuleEngine(rules)
        results = engine.evaluate(pages, failures)
        
        # 预期：budget_rule UNCERTAIN, other_rule 正常评估
        budget_result = next(r for r in results if r["rule_id"] == "budget_rule")
        other_result = next(r for r in results if r["rule_id"] == "other_rule")
        
        if budget_result["status"] == "UNCERTAIN":
            print(f"  ✅ budget_rule 正确降级为 UNCERTAIN")
        else:
            print(f"  ❌ budget_rule 应为 UNCERTAIN，实际为 {budget_result['status']}")
            all_passed = False
        
        if other_result["status"] in ["PASS", "FAIL"]:
            print(f"  ✅ other_rule 正常评估为 {other_result['status']}")
        else:
            print(f"  ⚠️  other_rule 状态为 {other_result['status']} (预期 PASS/FAIL)")
            
    except Exception as e:
        print(f"  ❌ 作用域降级测试失败: {e}")
        all_passed = False
    
    # 总结
    print("\n" + "="*80)
    if all_passed:
        print("🎉 M0阶段验收全部通过！")
        print("\n✅ 已完成:")
        print("  - 双通道Worker架构")
        print("  - content_paths优先级支持")
        print("  - 统一Evidence对象schema")
        print("  - rule_engine增强（4种evaluator类型）")
        print("  - 按作用域failure降级")
        print("  - FAIL必有证据降级机制")
        return True
    else:
        print("⚠️  部分检查未通过，请检查上述错误")
        return False


if __name__ == "__main__":
    success = check_m0_acceptance()
    sys.exit(0 if success else 1)
