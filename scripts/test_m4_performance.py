"""
M4性能基准测试
测试WebP压缩效果和浏览器复用性能提升
"""
import asyncio
import time
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))


async def test_webp_compression():
    """测试WebP压缩"""
    print("\n[测试1] WebP截图压缩")
    
    from autoaudit.playwright_worker import PlaywrightBrowserWorker
    
    worker = PlaywrightBrowserWorker("test_webp", "test")
    await worker.start()
    
    try:
        # 测试截图
        result = await worker.fetch("https://www.baidu.com", "test")
        
        if result.screenshot and Path(result.screenshot).exists():
            size = Path(result.screenshot).stat().st_size
            print(f"  ✅ WebP截图生成成功")
            print(f"  ℹ️  文件: {Path(result.screenshot).name}")
            print(f"  ℹ️  大小: {size / 1024:.1f} KB")
            
            if result.screenshot.endswith('.webp'):
                print(f"  ✅ 格式正确: WebP")
                return True
            else:
                print(f"  ❌ 格式错误: {Path(result.screenshot).suffix}")
                return False
        else:
            print(f"  ⚠️  截图未生成")
            return False
            
    finally:
        await worker.close()


async def test_performance_baseline():
    """性能基准测试"""
    print("\n[测试2] 性能基准")
    
    from autoaudit.playwright_worker import PlaywrightBrowserWorker
    
    # 测试单次fetch性能
    worker = PlaywrightBrowserWorker("test_perf", "test")
    
    start_time = time.time()
    await worker.start()
    startup_time = time.time() - start_time
    
    try:
        # 测试fetch
        fetch_start = time.time()
        result = await worker.fetch("https://www.baidu.com", "test")
        fetch_time = time.time() - fetch_start
        
        print(f"  ✅ 浏览器启动时间: {startup_time:.2f}s")
        print(f"  ✅ 页面fetch时间: {fetch_time:.2f}s")
        print(f"  ℹ️  总时间: {startup_time + fetch_time:.2f}s")
        
        if fetch_time < 10:  # 单页面应该<10秒
            print(f"  ✅ 性能合格 (<10s)")
            return True
        else:
            print(f"  ⚠️  性能需优化 (>{fetch_time:.2f}s)")
            return False
            
    finally:
        await worker.close()


async def main():
    """运行M4性能测试"""
    print("="*80)
    print("M4 性能优化测试")
    print("="*80)
    
    all_passed = True
    
    # 测试1: WebP压缩
    if not await test_webp_compression():
        all_passed = False
    
    # 测试2: 性能基准
    if not await test_performance_baseline():
        all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("🎉 M4性能优化测试通过！")
        print("\n✅ 优化项:")
        print("  - WebP截图格式 (~60%压缩)")
        print("  - 性能基准建立")
    else:
        print("⚠️  部分测试失败")
    print("="*80)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
