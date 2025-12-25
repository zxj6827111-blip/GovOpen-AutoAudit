#!/usr/bin/env python3
"""
检查当前网络位置
"""
import urllib.request
import json

print("="*80)
print("检查网络地理位置")
print("="*80)

# 方法1: 使用ipinfo.io
print("\n[方法1] 使用ipinfo.io服务")
try:
    response = urllib.request.urlopen('https://ipinfo.io/json', timeout=5)
    data = json.loads(response.read().decode('utf-8'))
    
    print(f"\n  ✅ 连接成功")
    print(f"\n  IP地址: {data.get('ip', 'N/A')}")
    print(f"  城市: {data.get('city', 'N/A')}")
    print(f"  地区: {data.get('region', 'N/A')}")
    print(f"  国家: {data.get('country', 'N/A')}")
    print(f"  位置: {data.get('loc', 'N/A')}")
    print(f"  组织: {data.get('org', 'N/A')}")
    
    country = data.get('country', '')
    if country == 'CN':
        print(f"\n  ⚠️  您当前在中国大陆（{country}）")
        print(f"  ❌ Google Gemini API在此地区不可用")
    else:
        print(f"\n  ✅ 您当前不在中国大陆（{country}）")
        print(f"  ✅ Google Gemini API应该可用")
        
except Exception as e:
    print(f"  ❌ 获取失败: {e}")

# 方法2: 使用ip-api.com
print("\n[方法2] 使用ip-api.com服务")
try:
    response = urllib.request.urlopen('http://ip-api.com/json/', timeout=5)
    data = json.loads(response.read().decode('utf-8'))
    
    if data.get('status') == 'success':
        print(f"\n  ✅ 连接成功")
        print(f"\n  IP地址: {data.get('query', 'N/A')}")
        print(f"  国家: {data.get('country', 'N/A')}")
        print(f"  国家代码: {data.get('countryCode', 'N/A')}")
        print(f"  地区: {data.get('regionName', 'N/A')}")
        print(f"  城市: {data.get('city', 'N/A')}")
        print(f"  ISP: {data.get('isp', 'N/A')}")
    else:
        print(f"  ❌ 查询失败")
        
except Exception as e:
    print(f"  ❌ 获取失败: {e}")

print("\n" + "="*80)
print("💡 结论")
print("="*80)
print("\n如果显示国家代码为 'CN'，说明您在中国大陆：")
print("  - ❌ Google Gemini API 不可用")
print("  - ✅ DeepSeek（魔搭）API 可用")
print("\n如果需要使用Gemini，需要：")
print("  1. 使用VPN/代理切换到支持的地区")
print("  2. 或者继续使用DeepSeek作为AI Provider")
print("="*80)
