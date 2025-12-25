#!/usr/bin/env python3
"""
AI Provider 连接测试
测试Gemini和DeepSeek API是否正常工作
"""
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))


def test_api_keys():
    """检查API密钥是否配置"""
    print("="*80)
    print("API密钥配置检查")
    print("="*80)
    
    gemini_key = os.environ.get("GEMINI_API_KEY")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    
    print(f"\n✅ GEMINI_API_KEY: {'已配置' if gemini_key else '❌ 未配置'}")
    if gemini_key:
        print(f"   密钥长度: {len(gemini_key)} 字符")
        print(f"   前缀: {gemini_key[:10]}...")
    
    print(f"\n✅ DEEPSEEK_API_KEY: {'已配置' if deepseek_key else '❌ 未配置'}")
    if deepseek_key:
        print(f"   密钥长度: {len(deepseek_key)} 字符")
        print(f"   前缀: {deepseek_key[:10]}...")
    
    return gemini_key or deepseek_key


def test_gemini_api():
    """测试Gemini API"""
    print("\n" + "="*80)
    print("测试 Gemini API")
    print("="*80)
    
    try:
        import google.generativeai as genai
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("❌ GEMINI_API_KEY未配置")
            return False
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-pro")
        
        print("\n发送测试请求...")
        response = model.generate_content("请用一句话介绍北京")
        
        print(f"✅ Gemini API响应成功!")
        print(f"\n响应内容: {response.text}")
        return True
        
    except Exception as e:
        print(f"❌ Gemini API测试失败: {e}")
        return False


def test_deepseek_api():
    """测试DeepSeek API"""
    print("\n" + "="*80)
    print("测试 DeepSeek API")
    print("="*80)
    
    try:
        from openai import OpenAI
        
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            print("❌ DEEPSEEK_API_KEY未配置")
            return False
        
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        
        print("\n发送测试请求...")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "user", "content": "请用一句话介绍上海"}
            ]
        )
        
        print(f"✅ DeepSeek API响应成功!")
        print(f"\n响应内容: {response.choices[0].message.content}")
        return True
        
    except Exception as e:
        print(f"❌ DeepSeek API测试失败: {e}")
        return False


def test_ai_extractor():
    """测试AIExtractor集成"""
    print("\n" + "="*80)
    print("测试 AIExtractor 集成")
    print("="*80)
    
    try:
        from autoaudit.ai_extractor import AIExtractor
        
        extractor = AIExtractor()
        
        # 测试HTML
        test_html = """
        <html>
        <body>
            <h1>联系我们</h1>
            <p>联系电话：025-12345678</p>
            <p>办公地址：江苏省南京市玄武区北京东路41号</p>
            <p>电子邮箱：contact@example.gov.cn</p>
        </body>
        </html>
        """
        
        print("\n提取字段: ['phone', 'address', 'email']")
        result = extractor.extract_fields(test_html, ["phone", "address", "email"])
        
        print("\n提取结果:")
        for field, value in result.items():
            print(f"  {field}: {value}")
        
        # 检查统计
        stats = extractor.get_invocation_stats()
        print(f"\n调用统计:")
        print(f"  总调用: {stats['total_invocations']}")
        print(f"  成功: {stats['successful_invocations']}")
        print(f"  成功率: {stats['success_rate']:.1%}")
        
        if stats['total_invocations'] > 0 and stats['success_rate'] > 0:
            print("\n✅ AIExtractor集成测试成功!")
            return True
        else:
            print("\n⚠️  AIExtractor未调用AI或失败")
            return False
            
    except Exception as e:
        print(f"❌ AIExtractor测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试流程"""
    print("\n" + "="*80)
    print("AI Provider 完整测试")
    print("="*80)
    
    # 1. 检查API密钥
    if not test_api_keys():
        print("\n❌ 未配置任何API密钥，测试中止")
        print("\n💡 请设置环境变量:")
        print("   $env:GEMINI_API_KEY = 'your-key'")
        print("   $env:DEEPSEEK_API_KEY = 'your-key'")
        return False
    
    results = []
    
    # 2. 测试Gemini
    if os.environ.get("GEMINI_API_KEY"):
        results.append(("Gemini", test_gemini_api()))
    
    # 3. 测试DeepSeek
    if os.environ.get("DEEPSEEK_API_KEY"):
        results.append(("DeepSeek", test_deepseek_api()))
    
    # 4. 测试AIExtractor集成
    results.append(("AIExtractor", test_ai_extractor()))
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n🎉 所有AI Provider测试通过!")
        print("\n系统已准备好使用AI辅助功能。")
        return True
    else:
        print("\n⚠️  部分测试失败，请检查API密钥和网络连接。")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
