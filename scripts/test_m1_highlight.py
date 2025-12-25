#!/usr/bin/env python3
"""
M1 Task 1 测试脚本 - Playwright红框标注验证
"""
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from autoaudit.playwright_worker import PlaywrightBrowserWorker


async def test_highlight_selector():
    """测试CSS selector红框标注"""
    print("\n[测试1] CSS Selector红框标注")
    
    worker = PlaywrightBrowserWorker("test_m1", "test_highlight_selector")
    await worker.start()
    
    try:
        rule_hints = {
            "highlight": True,
            "locator": {"selector": "form"}  # 标注所有form元素
        }
        
        # 使用本地sandbox或真实站点
        test_url = "http://localhost:8000/pass"  # 需要先启动sandbox
        
        result = await worker.fetch(test_url, "test", rule_hints)
        
        print(f"  ✅ 截图已保存: {result.screenshot}")
        print(f"  ℹ️  文件大小: {Path(result.screenshot).stat().st_size} bytes")
        print(f"  👉 请手动检查截图中是否有红框标注form元素")
        
        return result.screenshot
        
    finally:
        await worker.close()


async def test_highlight_keywords():
    """测试keywords红框标注"""
    print("\n[测试2] Keywords文本红框标注")
    
    worker = PlaywrightBrowserWorker("test_m1", "test_highlight_keywords")
    await worker.start()
    
    try:
        rule_hints = {
            "highlight": True,
            "locator": {"keywords": ["机构", "信息"]}  # 标注包含这些关键词的元素
        }
        
        test_url = "http://localhost:8000/pass"
        
        result = await worker.fetch(test_url, "test", rule_hints)
        
        print(f"  ✅ 截图已保存: {result.screenshot}")
        print(f"  ℹ️  文件大小: {Path(result.screenshot).stat().st_size} bytes")
        print(f"  👉 请手动检查截图中是否有红框标注包含关键词的元素")
        
        return result.screenshot
        
    finally:
        await worker.close()


async def test_no_highlight():
    """测试无红框标注（对照组）"""
    print("\n[测试3] 无红框标注（对照组）")
    
    worker = PlaywrightBrowserWorker("test_m1", "test_no_highlight")
    await worker.start()
    
    try:
        # 不传递rule_hints
        test_url = "http://localhost:8000/pass"
        
        result = await worker.fetch(test_url, "test", None)
        
        print(f"  ✅ 截图已保存: {result.screenshot}")
        print(f"  👉 此截图应该没有红框（对照组）")
        
        return result.screenshot
        
    finally:
        await worker.close()


async def main():
    """运行所有测试"""
    print("="*80)
    print("M1 Task 1 - Playwright红框标注功能测试")
    print("="*80)
    
    print("\n⚠️  注意: 需要先启动sandbox服务器")
    print("运行命令: python scripts/start_sandbox.py")
    print("\n按Enter继续...")
    input()
    
    try:
        # 测试1: Selector红框
        screenshot1 = await test_highlight_selector()
        
        # 测试2: Keywords红框
        screenshot2 = await test_highlight_keywords()
        
        # 测试3: 无红框对照
        screenshot3 = await test_no_highlight()
        
        print("\n" + "="*80)
        print("测试完成！")
        print("="*80)
        print("\n生成的截图:")
        print(f"  1. Selector红框: {screenshot1}")
        print(f"  2. Keywords红框: {screenshot2}")
        print(f"  3. 无红框对照: {screenshot3}")
        
        print("\n请手动检查这些截图验证红框标注是否正确。")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
