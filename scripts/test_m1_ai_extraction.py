#!/usr/bin/env python3
"""
M1 Task 2 测试脚本 - AI字段提取验证
测试AIExtractor能否正确提取phone和address字段
"""
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))


def test_ai_extraction_basic():
    """基础AI提取测试"""
    print("\n[测试1] 基础AI字段提取")
    
    # 设置API密钥（如果环境变量中没有）
    if not os.environ.get("GEMINI_API_KEY"):
        print("  ⚠️  GEMINI_API_KEY未设置")
        print("  请设置环境变量: export GEMINI_API_KEY=your-api-key")
        print("  或在代码中设置: os.environ['GEMINI_API_KEY'] = 'your-key'")
        return False
    
    from autoaudit.ai_extractor import AIExtractor
    
    # 模拟政府网站HTML
    html = """
    <html>
    <head><title>机构信息</title></head>
    <body>
        <div class="content">
            <h1>XX市政府机构信息</h1>
            <div class="info">
                <p><strong>联系电话：</strong>025-83214567</p>
                <p><strong>办公地址：</strong>江苏省南京市玄武区北京东路41号</p>
                <p><strong>邮政编码：</strong>210008</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    extractor = AIExtractor()
    result = extractor.extract_fields(html, ["phone", "address"])
    
    print(f"  提取结果: {result}")
    
    # 验证
    success = True
    if result.get("phone"):
        if "025" in result["phone"]:
            print(f"  ✅ phone提取成功: {result['phone']}")
        else:
            print(f"  ⚠️  phone提取结果可能不准确: {result['phone']}")
            success = False
    else:
        print(f"  ❌ phone未提取到")
        success = False
    
    if result.get("address"):
        if "南京" in result["address"]:
            print(f"  ✅ address提取成功: {result['address']}")
        else:
            print(f"  ⚠️  address提取结果可能不准确: {result['address']}")
            success = False
    else:
        print(f"  ❌ address未提取到")
        success = False
    
    return success


def test_ai_extraction_missing_fields():
    """测试字段缺失情况"""
    print("\n[测试2] 字段缺失处理")
    
    if not os.environ.get("GEMINI_API_KEY"):
        print("  ⚠️  跳过（API密钥未设置）")
        return True
    
    from autoaudit.ai_extractor import AIExtractor
    
    # 只有phone，没有address
    html = """
    <html>
    <body>
        <p>联系电话：010-12345678</p>
    </body>
    </html>
    """
    
    extractor = AIExtractor()
    result = extractor.extract_fields(html, ["phone", "address"])
    
    print(f"  提取结果: {result}")
    
    if result.get("phone") and not result.get("address"):
        print(f"  ✅ 正确识别phone存在，address不存在")
        return True
    else:
        print(f"  ⚠️  结果异常")
        return False


def test_rule_engine_integration():
    """测试rule_engine集成"""
    print("\n[测试3] rule_engine集成测试")
    
    if not os.environ.get("GEMINI_API_KEY"):
        print("  ⚠️  跳过（API密钥未设置）")
        return True
    
    from autoaudit.rule_engine import RuleEngine
    
    # 创建presence_all规则
    rules = [{
        "rule_id": "test_institution_info",
        "class": 1,
        "locator": {"keywords": ["机构"]},
        "evaluator": {
            "type": "presence_all",
            "required_fields": ["phone", "address"]
        }
    }]
    
    # 模拟页面
    pages = [{
        "url": "http://test.gov.cn",
        "body": """
        <html><body>
        <h1>机构信息</h1>
        <p>联系电话：025-12345678</p>
        <p>办公地址：江苏省南京市玄武区XX路XX号</p>
        </body></html>
        """,
        "snapshot": "test.html",
        "site_id": "test"
    }]
    
    engine = RuleEngine(rules)
    results = engine.evaluate(pages, [])
    
    print(f"  规则评估结果: {results[0]['status']}")
    print(f"  原因: {results[0].get('reason')}")
    
    if results[0]["status"] == "PASS":
        print(f"  ✅ AI提取成功，规则PASS")
        # 检查是否有AI提取结果
        if "_evidence_objects" in results[0]:
            evidence = results[0]["_evidence_objects"][0]
            if evidence.get("metadata", {}).get("ai_extracted"):
                print(f"  ✅ AI提取结果已保存到Evidence")
                print(f"     {evidence['metadata']['ai_extracted']}")
        return True
    else:
        print(f"  ⚠️  规则状态为{results[0]['status']}，预期PASS")
        return False


def main():
    """运行所有测试"""
    print("="*80)
    print("M1 Task 2 - AI辅助字段提取功能测试")
    print("="*80)
    
    # 检查依赖
    try:
        import google.generativeai as genai
        print("✅ google-generativeai已安装")
    except ImportError:
        print("❌ google-generativeai未安装")
        print("请运行: pip install google-generativeai")
        return False
    
    try:
        from bs4 import BeautifulSoup
        print("✅ beautifulsoup4已安装")
    except ImportError:
        print("❌ beautifulsoup4未安装")
        print("请运行: pip install beautifulsoup4")
        return False
    
    all_passed = True
    
    # 测试1
    if not test_ai_extraction_basic():
        all_passed = False
    
    # 测试2
    if not test_ai_extraction_missing_fields():
        all_passed = False
    
    # 测试3
    if not test_rule_engine_integration():
        all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("🎉 所有测试通过！")
    else:
        print("⚠️  部分测试失败")
    print("="*80)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
