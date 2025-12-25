#!/usr/bin/env python3
"""
M3 AI功能测试脚本
测试双Provider支持、Cost Control、AI审计报告
"""
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))


def test_dual_provider():
    """测试双Provider支持"""
    print("\n[测试1] 双Provider支持")
    
    from autoaudit.ai_extractor import AIExtractor
    
    extractor = AIExtractor(
        primary_provider="gemini",
        fallback_provider="deepseek",
        max_cost_per_batch=1000
    )
    
    print(f"  ✅ Primary: {extractor.primary_provider}")
    print(f"  ✅ Fallback: {extractor.fallback_provider}")
    print(f"  ℹ️  Gemini可用: {extractor.gemini_client is not None}")
    print(f"  ℹ️  DeepSeek可用: {extractor.deepseek_client is not None}")
    
    return True


def test_cost_control():
    """测试Cost Control"""
    print("\n[测试2] Cost Control")
    
    from autoaudit.ai_extractor import AIExtractor
    
    # 设置很低的limit
    extractor = AIExtractor(max_cost_per_batch=10)
    extractor.batch_tokens_used = 15  # 模拟超限
    
    result = extractor.extract_fields("<html>test</html>", ["phone"])
    
    if result == {"phone": None}:
        print("  ✅ Cost Control生效 - 超限后返回None")
        return True
    else:
        print("  ❌ Cost Control未生效")
        return False


def test_invocation_logging():
    """测试AI调用记录"""
    print("\n[测试3] AI调用记录")
    
    from autoaudit.ai_extractor import AIExtractor, AiInvocation
    
    extractor = AIExtractor()
    
    # 模拟一个调用记录
    inv = AiInvocation(
        invocation_id="test_123",
        provider="gemini",
        model="gemini-pro",
        latency_ms=500,
        total_tokens=100,
        success=True
    )
    extractor.invocations.append(inv)
    
    stats = extractor.get_invocation_stats()
    
    print(f"  ✅ 统计功能正常")
    print(f"  ℹ️  total_invocations: {stats['total_invocations']}")
    print(f"  ℹ️  success_rate: {stats['success_rate']:.1%}")
    print(f"  ℹ️  total_tokens_used: {stats['total_tokens_used']}")
    
    return True


def test_audit_report():
    """测试AI审计报告"""
    print("\n[测试4] AI审计报告生成")
    
    from autoaudit.ai_extractor import AIExtractor, AiInvocation
    
    extractor = AIExtractor()
    
    # 添加一些模拟记录
    extractor.invocations.append(AiInvocation(
        invocation_id="test_1",
        provider="gemini",
        model="gemini-pro",
        latency_ms=450,
        total_tokens=120,
        success=True
    ))
    extractor.invocations.append(AiInvocation(
        invocation_id="test_2",
        provider="deepseek",
        model="deepseek-chat",
        latency_ms=300,
        total_tokens=95,
        success=True
    ))
    
    report = extractor.generate_audit_report()
    
    if "AI调用审计报告" in report and "Provider统计" in report:
        print("  ✅ 审计报告生成成功")
        # 保存到文件
        report_path = ROOT_DIR / "runs" / "test_ai_audit.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        print(f"  ℹ️  报告已保存: {report_path}")
        return True
    else:
        print("  ❌ 审计报告格式不正确")
        return False


def test_api_keys():
    """测试API密钥配置"""
    print("\n[测试5] API密钥配置")
    
    gemini_key = os.environ.get("GEMINI_API_KEY")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    
    print(f"  {'✅' if gemini_key else '⚠️ '} GEMINI_API_KEY: {'已设置' if gemini_key else '未设置'}")
    print(f"  {'✅' if deepseek_key else '⚠️ '} DEEPSEEK_API_KEY: {'已设置' if deepseek_key else '未设置'}")
    
    if not gemini_key and not deepseek_key:
        print("\n  💡 提示：设置API密钥以启用AI功能")
        print("  export GEMINI_API_KEY=your-gemini-key")
        print("  export DEEPSEEK_API_KEY=your-deepseek-key")
    
    return True


def main():
    """运行所有M3测试"""
    print("="*80)
    print("M3 AI功能测试")
    print("="*80)
    
    all_passed = True
    
    # 测试1: 双Provider
    if not test_dual_provider():
        all_passed = False
    
    # 测试2: Cost Control
    if not test_cost_control():
        all_passed = False
    
    # 测试3: 调用记录
    if not test_invocation_logging():
        all_passed = False
    
    # 测试4: 审计报告
    if not test_audit_report():
        all_passed = False
    
    # 测试5: API密钥
    if not test_api_keys():
        all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("🎉 所有M3测试通过！")
        print("\n✅ M3新功能:")
        print("  - 双AI Provider（Gemini主 + DeepSeek副）")
        print("  - AI调用记录（AiInvocation）")
        print("  - Cost Control（token限制）")
        print("  - AI审计报告（Markdown）")
    else:
        print("⚠️  部分测试失败")
    print("="*80)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
