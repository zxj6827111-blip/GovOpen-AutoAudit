#!/usr/bin/env python3
"""
快速测试脚本 - 验证三大增强功能
1. 深度导航
2. 截图标注
3. AI复核
"""
import sys
import os
from pathlib import Path

# Add root to path
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

def test_navigation_helper():
    """测试导航辅助模块"""
    print("\n" + "="*60)
    print("测试1: 导航辅助模块")
    print("="*60)
    
    try:
        from autoaudit.navigation_helper import NavigationHelper, CATEGORY_KEYWORDS
        
        print(f"✅ 导航辅助模块导入成功")
        print(f"✅ 预定义栏目关键词数量: {len(CATEGORY_KEYWORDS)}")
        print(f"✅ 栏目列表: {list(CATEGORY_KEYWORDS.keys())[:5]}...")
        
        # 测试实例化
        nav_helper = NavigationHelper(max_depth=2, max_links_per_level=10)
        print(f"✅ NavigationHelper实例创建成功 (max_depth={nav_helper.max_depth})")
        
        return True
    except Exception as e:
        print(f"❌ 导航辅助模块测试失败: {e}")
        return False

def test_playwright_integration():
    """测试Playwright集成"""
    print("\n" + "="*60)
    print("测试2: Playwright深度导航集成")
    print("="*60)
    
    try:
        from autoaudit.playwright_worker import PlaywrightBrowserWorker
        
        print(f"✅ PlaywrightBrowserWorker导入成功")
        
        # 检查run_site方法签名
        import inspect
        sig = inspect.signature(PlaywrightBrowserWorker.run_site)
        params = list(sig.parameters.keys())
        
        if 'enable_deep_nav' in params:
            print(f"✅ run_site方法已包含enable_deep_nav参数")
        else:
            print(f"❌ run_site方法缺少enable_deep_nav参数")
            return False
        
        print(f"✅ 方法参数: {params}")
        return True
    except Exception as e:
        print(f"❌ Playwright集成测试失败: {e}")
        return False

def test_ai_review():
    """测试AI复核功能"""
    print("\n" + "="*60)
    print("测试3: AI复核功能")
    print("="*60)
    
    try:
        from autoaudit.ai_extractor import AIExtractor
        
        print(f"✅ AIExtractor导入成功")
        
        # 检查review_uncertain_rule方法
        if hasattr(AIExtractor, 'review_uncertain_rule'):
            print(f"✅ review_uncertain_rule方法存在")
        else:
            print(f"❌ review_uncertain_rule方法不存在")
            return False
        
        # 测试实例化
        extractor = AIExtractor()
        print(f"✅ AIExtractor实例创建成功")
        print(f"   主Provider: {extractor.primary_provider}")
        print(f"   备用Provider: {extractor.fallback_provider}")
        
        return True
    except Exception as e:
        print(f"❌ AI复核功能测试失败: {e}")
        return False

def test_rule_engine_integration():
    """测试规则引擎AI集成"""
    print("\n" + "="*60)
    print("测试4: 规则引擎AI集成")
    print("="*60)
    
    try:
        from autoaudit.rule_engine import RuleEngine
        import inspect
        
        print(f"✅ RuleEngine导入成功")
        
        # 检查_uncertain方法签名
        sig = inspect.signature(RuleEngine._uncertain)
        params = list(sig.parameters.keys())
        
        if 'pages' in params:
            print(f"✅ _uncertain方法已包含pages参数（用于AI复核）")
        else:
            print(f"❌ _uncertain方法缺少pages参数")
            return False
        
        print(f"✅ 方法参数: {params}")
        return True
    except Exception as e:
        print(f"❌ 规则引擎集成测试失败: {e}")
        return False

def test_dual_channel_priority():
    """测试双通道优先级"""
    print("\n" + "="*60)
    print("测试5: 双通道Playwright优先")
    print("="*60)
    
    try:
        from autoaudit.dual_channel_worker import run_site_dual_channel
        import inspect
        
        # 读取源代码
        source = inspect.getsource(run_site_dual_channel)
        
        if "Playwright优先" in source or "规避反爬虫" in source:
            print(f"✅ 双通道策略已修改为Playwright优先")
        else:
            print(f"⚠️  双通道策略可能未修改")
        
        if "PlaywrightBrowserWorker" in source[:500]:
            print(f"✅ Playwright在函数开头部分被调用（优先）")
        else:
            print(f"❌ Playwright不在优先位置")
            return False
        
        return True
    except Exception as e:
        print(f"❌ 双通道优先级测试失败: {e}")
        return False

def check_environment_variables():
    """检查环境变量配置"""
    print("\n" + "="*60)
    print("环境变量检查")
    print("="*60)
    
    # 检查.env文件
    env_file = ROOT_DIR / ".env"
    if env_file.exists():
        print(f"✅ .env文件存在")
        
        # 读取.env
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键配置
        configs = {
            "DEEPSEEK_API_KEY": "AI API密钥",
            "ENABLE_DEEP_NAVIGATION": "深度导航",
            "ENABLE_AI_REVIEW": "AI复核",
        }
        
        for key, desc in configs.items():
            if key in content:
                value = os.environ.get(key, "未设置")
                print(f"✅ {desc} ({key}): {value[:20]}...")
            else:
                print(f"⚠️  {desc} ({key}): 未在.env中配置")
    else:
        print(f"⚠️  .env文件不存在，请从.env.example复制")

def main():
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "功能增强验证测试" + " "*23 + "║")
    print("╚" + "="*58 + "╝")
    
    results = {}
    
    # 运行所有测试
    results["navigation"] = test_navigation_helper()
    results["playwright"] = test_playwright_integration()
    results["ai_review"] = test_ai_review()
    results["rule_engine"] = test_rule_engine_integration()
    results["dual_channel"] = test_dual_channel_priority()
    
    # 环境变量检查
    check_environment_variables()
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！系统已准备就绪。")
        print("\n下一步:")
        print("1. 确保.env文件中配置了DEEPSEEK_API_KEY")
        print("2. 设置 ENABLE_DEEP_NAVIGATION=true")
        print("3. 设置 ENABLE_AI_REVIEW=true")
        print("4. 运行: python scripts/run_pilot.py --rulepack rulepacks/jiangsu_suqian_v1_1 --sites rulepacks/jiangsu_suqian_v1_1/sites.json")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(main())
