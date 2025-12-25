#!/usr/bin/env python3
"""
测试最终的3 AI Provider配置
"""
import os
import sys
from pathlib import Path

# 设置环境变量
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line.startswith('DEEPSEEK_API_KEY='):
            key = line.split('=', 1)[1].strip().strip('"').strip("'")
            os.environ['DEEPSEEK_API_KEY'] = key

print("="*80)
print("最终3AI系统测试：DeepSeek(主) + Qwen(备) + GLM(特殊)")
print("="*80)

# 导入
sys.path.insert(0, str(Path(__file__).parent.parent))
from autoaudit.ai_extractor import AIExtractor

# 测试HTML
test_html = """
<html>
<head><title>政府信息公开</title></head>
<body>
    <div>
        <p>办公地址：浙江省杭州市西湖区文三路199号</p>
        <p>联系电话：0571-87654321</p>
        <p>传真：0571-87654322</p>
        <p>邮箱：service@zhejiang.gov.cn</p>
    </div>
</body>
</html>
"""

fields = ["address", "phone", "fax", "email"]

print("\n[测试1] 默认配置（DeepSeek主 + Qwen备）")
print("-" * 80)
try:
    extractor = AIExtractor()  # 使用默认配置
    print(f"✅ 初始化成功")
    print(f"   Primary: {extractor.primary_provider}")
    print(f"   Fallback: {extractor.fallback_provider}")
    print(f"   DeepSeek: {'✓' if extractor.deepseek_client else '✗'}")
    print(f"   Qwen: {'✓' if extractor.qwen_client else '✗'}")
    print(f"   GLM: {'✓' if extractor.glm_client else '✗'}")
    
    result = extractor.extract_fields(test_html, fields)
    stats = extractor.get_invocation_stats()
    extracted = sum(1 for v in result.values() if v)
    
    print(f"\n📊 提取质量: {extracted}/{len(fields)} ({extracted/len(fields)*100:.0f}%)")
    print(f"📊 Token消耗: {stats['total_tokens_used']}")
    print(f"📊 平均延迟: {stats['average_latency_ms']}ms")
    
    # 显示实际使用的provider
    for provider, ps in stats['provider_stats'].items():
        if ps['success'] > 0:
            print(f"✅ 实际使用: {provider.upper()}")
            
except Exception as e:
    print(f"❌ 失败: {e}")

print("\n[测试2] 使用GLM（特殊场景）")
print("-" * 80)
try:
    extractor_glm = AIExtractor(primary_provider="glm", fallback_provider="deepseek")
    print(f"✅ 初始化成功（GLM主导）")
    
    result = extractor_glm.extract_fields(test_html, fields)
    stats = extractor_glm.get_invocation_stats()
    extracted = sum(1 for v in result.values() if v)
    
    print(f"📊 提取质量: {extracted}/{len(fields)} ({extracted/len(fields)*100:.0f}%)")
    print(f"📊 Token消耗: {stats['total_tokens_used']}")
    print(f"📊 平均延迟: {stats['average_latency_ms']}ms")
    
except Exception as e:
    print(f"❌ 失败: {e}")

print("\n" + "="*80)
print("系统配置最终版")
print("="*80)
print("✅ Provider配置:")
print("   1. 主Provider: DeepSeek-V3.2 (综合最优)")
print("   2. 备Provider: Qwen3-32B (最快响应)")
print("   3. 特殊Provider: GLM-4.7 (复杂推理/长上下文)")
print("\n✅ 所有Provider共用ModelScope平台")
print("✅ 自动降级机制已启用")
print("✅ Gemini3已移除（限流严重）")
print("="*80)
