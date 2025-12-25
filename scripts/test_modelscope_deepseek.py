#!/usr/bin/env python3
"""
魔搭DeepSeek API测试
使用正确的ModelScope配置
"""
import os

#添加dotenv加载
from dotenv import load_dotenv
load_dotenv()

# ✅ 从环境变量读取API Key（不再硬编码）
# 请在.env文件中配置: DEEPSEEK_API_KEY=your_key_here
api_key = os.environ.get('DEEPSEEK_API_KEY')
if not api_key:
    raise ValueError("未找到DEEPSEEK_API_KEY环境变量，请在.env文件中配置")

# 2. 测试调用
from openai import OpenAI

client = OpenAI(
    base_url='https://api-inference.modelscope.cn/v1',
    api_key=api_key  # ✅ 使用从环境变量读取的key
)

print("="*80)
print("魔搭DeepSeek API 测试")
print("="*80)

try:
    print("\n发送测试请求...")
    response = client.chat.completions.create(
        model='deepseek-ai/DeepSeek-V3.2',  # ModelScope Model-Id
        messages=[
            {'role': 'user', 'content': '1+1等于几？请简短回答'}
        ],
        stream=False,
        max_tokens=50
    )
    
    print(f"\n✅ 调用成功!")
    print(f"\n响应: {response.choices[0].message.content}")
    print(f"\nToken使用:")
    print(f"  输入: {response.usage.prompt_tokens}")
    print(f"  输出: {response.usage.completion_tokens}")
    print(f"  总计: {response.usage.total_tokens}")
    
except Exception as e:
    print(f"\n❌ 调用失败")
    print(f"错误: {e}")

print("\n" + "="*80)
