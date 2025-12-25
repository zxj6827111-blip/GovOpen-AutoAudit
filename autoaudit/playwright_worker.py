import asyncio
import base64
import logging
import json
import random
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Response

from .models import TraceStep
from .storage import RUNS_DIR, write_json

# Setup logging
logger = logging.getLogger(__name__)

class FetchResult:
    def __init__(self, url: str, status_code: int, body: str, elapsed: float = 0, 
                 screenshot: str = "", snapshot: str = "", title: str = "", 
                 step: str = "", anchor_name: str = "", **kwargs):
        self.url = url
        self.status_code = status_code
        self.body = body
        self.elapsed = elapsed
        self.screenshot = screenshot
        self.snapshot = snapshot
        self.title = title
        self.step = step
        self.anchor_name = anchor_name  # ✅ 新增：存储anchor名称用于规则匹配
        # 存储额外的字段
        for key, value in kwargs.items():
            setattr(self, key, value)


class PlaywrightBrowserWorker:
    def __init__(self, batch_id: str, site_id: str, headless: bool = True):
        self.batch_id = batch_id
        self.site_id = site_id
        self.base_dir = RUNS_DIR / batch_id / f"site_{site_id}"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.traces: List[TraceStep] = []
        self.headless = headless
        
        # Playwright objects
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def start(self):
        """Initialize Playwright and Browser"""
        self.playwright = await async_playwright().start()
        # Launch options
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        # Context with realistic User Agent and Locale
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 GovOpen-AutoAudit/1.0',
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
            ignore_https_errors=True # Government sites often have bad certs
        )

    async def close(self):
        """Clean up resources"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    def _write_screenshot(self, name: str, data: bytes) -> str:
        path = self.base_dir / name
        with path.open("wb") as f:
            f.write(data)
        return str(path)

    def _write_snapshot(self, name: str, html: str) -> str:
        path = self.base_dir / name
        path.write_text(html, encoding="utf-8")
        return str(path)
    
    async def _highlight_elements(self, page: Page, rule_hints: Dict):
        """在页面上标注匹配的元素"""
        locator = rule_hints.get("locator", {})
        
        # 注入红框CSS
        await page.add_style_tag(content="""
            .auto-audit-highlight {
                outline: 3px solid red !important;
                outline-offset: 2px !important;
                background-color: rgba(255, 0, 0, 0.1) !important;
            }
        """)
        
        # Case 1: CSS selector标注
        if "selector" in locator:
            selector = locator["selector"]
            try:
                elements = await page.query_selector_all(selector)
                for elem in elements:
                    await elem.evaluate("el => el.classList.add('auto-audit-highlight')")
                logger.info(f"Highlighted {len(elements)} elements with selector: {selector}")
            except Exception as e:
                logger.warning(f"Selector highlight failed for {selector}: {e}")
        
        # Case 2: keywords文本标注
        elif "keywords" in locator:
            keywords = locator["keywords"]
            # 使用JavaScript高亮文本
            highlight_script = f"""
            const keywords = {json.dumps(keywords)};
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            let highlighted = 0;
            while (walker.nextNode()) {{
                const node = walker.currentNode;
                keywords.forEach(kw => {{
                    if (node.textContent.includes(kw)) {{
                        const parent = node.parentElement;
                        if (parent && !parent.classList.contains('auto-audit-highlight')) {{
                            parent.classList.add('auto-audit-highlight');
                            highlighted++;
                        }}
                    }}
                }});
            }}
            return highlighted;
            """
            try:
                count = await page.evaluate(highlight_script)
                logger.info(f"Highlighted {count} elements with keywords: {keywords}")
            except Exception as e:
                logger.warning(f"Keywords highlight failed: {e}")

    async def fetch(self, url: str, step: str, rule_hints: Optional[Dict] = None) -> FetchResult:
        """
        Navigate to a URL, capture evidence, and return result.
        rule_hints: Optional dictionary with 'locator' or text to highlight.
        """
        start = time.time()
        status_code = 0
        body = ""
        screenshot_path = ""
        snapshot_path = ""
        
        page = await self.context.new_page()
        
        try:
            # Navigate
            # Use 'domcontentloaded' for speed, 'networkidle' for completeness. 
            # Gov sites can be slow, so we set a generous timeout.
            response: Optional[Response] = await page.goto(url, timeout=30000, wait_until='domcontentloaded')
            
            # Wait a bit for dynamic content
            await page.wait_for_timeout(2000)
            
            # Scroll to bottom to trigger lazy loading
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
            
            if response:
                status_code = response.status
            
            body = await page.content()
            
            # ✅ 启用红框标注：只要有rule_hints就标注（不需要highlight标志）
            if rule_hints:
                try:
                    await self._highlight_elements(page, rule_hints)
                    # 等待CSS生效
                    await page.wait_for_timeout(500)
                    logger.info(f"为{url}启用红框标注")
                except Exception as e:
                    logger.error(f"Highlighting failed for {url}: {e}")
            
            screenshot_bytes = await page.screenshot(full_page=True, type='jpeg', quality=80) 
            # Using JPEG to save space, full_page for complete evidence
            
            step_idx = len(self.traces)
            screenshot_path = self._write_screenshot(f"screenshot_{step_idx}.jpg", screenshot_bytes)
            snapshot_path = self._write_snapshot(f"snapshot_{step_idx}.html", body)
            
        except Exception as e:
            logger.error(f"Playwright fetch failed for {url}: {e}")
            # Capture error state if possible
            try:
                screenshot_bytes = await page.screenshot(full_page=False)
                screenshot_path = self._write_screenshot(f"error_{len(self.traces)}.jpg", screenshot_bytes)
            except:
                pass
        finally:
            elapsed = time.time() - start
            self.traces.append(TraceStep(
                step=step, 
                url=url, 
                status_code=status_code, 
                elapsed=elapsed, 
                screenshot=screenshot_path, 
                snapshot=snapshot_path,
                notes=str(rule_hints) if rule_hints else None
            ))
            await page.close()

        return FetchResult(url, status_code, body, elapsed, screenshot_path, snapshot_path)

    def save_trace(self) -> str:
        trace_path = self.base_dir / "trace.json"
        trace_data = [trace.__dict__ for trace in self.traces]
        write_json(trace_path, trace_data)
        return str(trace_path)

    def sample_content_urls(self, site: Dict, per_list_recent_n: int, per_list_random_m: int, max_content_pages: int) -> List[str]:
        # 与worker.py保持一致的逻辑
        content_paths = site.get("content_paths", [])
        if not content_paths:
            return []
        
        # 支持新格式（对象数组 + 优先级）
        if isinstance(content_paths[0], dict):
            # 按priority降序排序
            sorted_paths = sorted(content_paths, key=lambda x: x.get("priority", 5), reverse=True)
            urls = [cp["url"] for cp in sorted_paths]
        else:
            # 兼容旧格式（字符串数组）
            urls = content_paths
        
        # 原有抽样逻辑
        ordered = urls[:per_list_recent_n]
        remaining = urls[per_list_recent_n:]
        random.shuffle(remaining)
        ordered.extend(remaining[:per_list_random_m])
        return ordered[:max_content_pages]

    async def run_site(self, site: Dict, sampling: Dict, extra_depth: int = 0, enable_deep_nav: bool = True) -> Tuple[List[FetchResult], List[FetchResult]]:
        await self.start()
        entry_results: List[FetchResult] = []
        content_results: List[FetchResult] = []
        
        try:
            # 1. Visit Entry Points
            for url in site.get("entry_points", []):
                res = await self.fetch(url, step="entry")
                entry_results.append(res)
            
            # ✅ 新增: 深度导航 - 自动发现栏目链接
            if enable_deep_nav:
                from .navigation_helper import NavigationHelper, click_link_by_anchor
                import os
                
                # ✅ 从环境变量读取配置
                max_depth = int(os.environ.get("MAX_NAVIGATION_DEPTH", "5"))
                max_links = int(os.environ.get("MAX_LINKS_PER_LEVEL", "15"))
                
                logger.info(f"启用深度导航模式（深度{max_depth}层，每层最多{max_links}链接），从入口页发现政务栏目...")
                nav_helper = NavigationHelper(max_depth=max_depth, max_links_per_level=max_links)
                
                # 对每个入口页构建导航树
                for entry_url in site.get("entry_points", []):
                    page = await self.context.new_page()
                    try:
                        nav_tree = await nav_helper.build_navigation_tree(page, entry_url)
                        
                        # 访问发现的深层链接（优先高优先级栏目）
                        discovered_urls = nav_tree.get("level_0", [])[:10]  # 最多10个level_0链接
                        discovered_urls += nav_tree.get("level_1", [])[:5]   # 最多5个level_1链接
                        
                        logger.info(f"从{entry_url}发现{len(discovered_urls)}个深层链接，开始访问...")
                        
                        for nav_url in discovered_urls:
                            res = await self.fetch(nav_url, step="deep_nav")
                            entry_results.append(res)  # 深度导航的链接算作entry扩展
                        
                        # ✅ 新增：主动点击进入左侧导航子页面
                        # 这些是机构信息等规则需要的子页面
                        anchor_patterns = [
                            # 机构信息相关
                            ["机构职能", "机构职责", "部门职能"],
                            ["机构设置", "内设机构", "组织机构"],
                            ["机构领导", "领导分工", "领导信息"],
                            ["办公地址", "联系方式", "联系我们"],
                            ["办公时间", "工作时间"],
                            # ✅ 新增：年报相关
                            ["政府信息公开年报", "年报", "年度报告"],
                            # 政府信息公开指南相关
                            ["政府信息公开指南", "公开指南", "信息公开指南"],
                            ["政府信息公开制度", "公开制度"],
                        ]
                        
                        for anchors in anchor_patterns:
                            try:
                                # 先导航到入口页
                                await page.goto(entry_url, timeout=10000)
                                await page.wait_for_load_state("domcontentloaded")
                                
                                # 尝试点击匹配的链接
                                result = await click_link_by_anchor(page, anchors, entry_url)
                                
                                if result:
                                    # 截图并保存页面内容
                                    screenshot_path = self.runs_dir / self.batch_id / f"site_{site['site_id']}" / f"anchor_{anchors[0]}.jpg"
                                    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                                    await page.screenshot(path=str(screenshot_path), type="jpeg", quality=80)
                                    
                                    # 构建FetchResult
                                    fetch_res = FetchResult(
                                        url=result["url"],
                                        status_code=200,
                                        body=result["body"],
                                        title=result.get("title", ""),
                                        screenshot=str(screenshot_path),
                                        step="anchor_nav",
                                        # ✅ 新增：存储anchor名称，规则引擎可按此匹配
                                        anchor_name=anchors[0]
                                    )
                                    entry_results.append(fetch_res)
                                    logger.info(f"✅ 成功访问子页面: {anchors[0]} -> {result['url']}")
                                    
                            except Exception as anchor_err:
                                logger.debug(f"点击anchor失败 {anchors[0]}: {anchor_err}")
                                continue
                        
                    except Exception as e:
                        logger.error(f"深度导航失败: {e}", exc_info=True)
                    finally:
                        await page.close()
            
            # 2. Sample Content Pages
            sampled_content = self.sample_content_urls(
                site,
                sampling.get("per_list_recent_n", 3),
                sampling.get("per_list_random_m", 2),
                sampling.get("max_content_pages_per_site", 30),
            )
            
            for url in sampled_content:
                res = await self.fetch(url, step="content")
                content_results.append(res)
                
            # 3. Extra Depth (if needed)
            for _ in range(extra_depth):
                remaining = [u for u in site.get("content_paths", []) if u not in sampled_content]
                if not remaining:
                    break
                url = remaining.pop(0)
                sampled_content.append(url)
                res = await self.fetch(url, step="content_deepen")
                content_results.append(res)
                
        finally:
            await self.close()
            self.save_trace()
            
        return entry_results, content_results
