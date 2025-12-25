import asyncio
import logging
from typing import Dict, List, Tuple
from .worker import BrowserWorker, FetchResult
from .playwright_worker import PlaywrightBrowserWorker

logger = logging.getLogger(__name__)


def should_use_playwright(static_result: FetchResult) -> bool:
    """判断是否需要Playwright"""
    # 条件1: body为空或过短
    if len(static_result.body) < 500:
        return True
    
    # 条件2: 检测JS渲染标记
    js_indicators = [
        '<div id="app"></div>',  # Vue/React
        '<div id="root"></div>',  # React
        'document.write',
        'window.__INITIAL_STATE__'
    ]
    if any(indicator in static_result.body for indicator in js_indicators):
        return True
    
    return False


async def run_site_dual_channel(
    batch_id: str,
    site_id: str,
    site: Dict,
    sampling: Dict,
    extra_depth: int = 0,
    rules: List[Dict] = None  # ✅ 新增：传递规则信息用于红框标注
) -> Tuple[List[FetchResult], List[FetchResult]]:
    """双通道抓取：Playwright优先（规避反爬虫），静态兜底"""
    
    # ✅ 修改策略：政务网站优先使用Playwright规避反爬虫
    logger.info(f"Site {site_id}: 使用Playwright浏览器模式（规避反爬虫）")
    
    try:
        # 1. 优先使用Playwright（真实浏览器）
        pw_worker = PlaywrightBrowserWorker(batch_id, site_id)
        entry_pw, content_pw = await pw_worker.run_site(site, sampling, extra_depth)
        logger.info(f"Site {site_id}: Playwright执行成功，获取{len(entry_pw)}个入口页，{len(content_pw)}个内容页")
        return entry_pw, content_pw
        
    except Exception as e:
        # 2. Playwright失败才降级到静态worker
        logger.warning(
            f"Site {site_id}: Playwright失败({e})，降级到requests静态模式"
        )
        try:
            static_worker = BrowserWorker(batch_id, site_id)
            entry_results, content_results = static_worker.run_site(site, sampling, extra_depth)
            static_worker.save_trace()
            logger.info(f"Site {site_id}: 静态模式成功，获取{len(entry_results)}个入口页，{len(content_results)}个内容页")
            return entry_results, content_results
        except Exception as e2:
            # 3. 两种方式都失败，返回空结果
            logger.error(f"Site {site_id}: 静态模式也失败({e2})，返回空结果")
            return [], []
