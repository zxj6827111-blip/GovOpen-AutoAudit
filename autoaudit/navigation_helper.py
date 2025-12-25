"""
导航辅助模块
提供自动发现导航菜单、提取栏目链接、构建层级树等功能
专门针对政务公开网站的栏目结构设计
"""
import logging
import asyncio
from typing import List, Dict, Set, Optional
from playwright.async_api import Page, Locator
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

# 常见政务公开栏目关键词（优先级从高到低）
CATEGORY_KEYWORDS = {
    "政府信息公开指南": ["政府信息公开指南", "公开指南", "信息公开指南"],
    "政府信息公开年度报告": ["政府信息公开年度报告", "年度报告", "信息公开年报", "年报"],
    "政府信息公开制度": ["政府信息公开制度", "公开制度", "信息公开规定"],
    "法定主动公开内容": ["法定主动公开内容", "主动公开", "公开内容"],
    "政策解读": ["政策解读", "解读回应", "政策文件解读"],
    "规划计划": ["规划计划", "发展规划", "工作计划"],
    "财政预算": ["财政预算", "预算公开", "部门预算", "财政信息"],
    "人事信息": ["人事信息", "人事任免", "人员招聘"],
    "重大决策": ["重大决策", "决策公开", "重大事项"],
    "行政执法": ["行政执法", "执法公示", "执法信息"],
}

# 导航菜单常见选择器（按优先级）
# ⚠️ 注意：只使用政务公开栏目内的子导航选择器，不要使用顶部主导航栏
NAV_SELECTORS = [
    # ✅ 政务公开栏目专用选择器（仅抓取二级子栏目）
    ".menu-cards a.item",          # 政务公开页面的图标导航（政府信息公开指南、制度等）
    ".menu-cards a",               # 备用：图标导航
    
    # ✅ 左侧边栏导航（关键！需要点击进入子页面）
    ".navLeft .subNav a",          # 左侧子菜单链接（如：机构职能、内设机构等）
    ".navLeft .sub-menu a",        # 子菜单备选
    ".navLeft li li a",            # 嵌套列表中的链接
    ".navLeft dd a",               # dd标签中的子链接
    ".navLeft a",                  # 左侧边栏导航（法规政策、机构概况等）
    
    # ✅ 机构信息专用选择器
    ".jgxx-nav a",                 # 机构信息导航
    ".org-nav a",                  # 组织导航
    "[class*='jg'] a",             # 包含"jg"的class
    
    ".gkadd-list a",               # 政务公开相关列表
    ".xxgkml-list a",              # 信息公开目录列表
    
    # ❌ 不使用：.header-mainnav a  会抓取"首页"、"走进宿迁"等无关链接
    
    # 通用选择器（优先级较低）
    ".nav-left a",
    ".sidebar-nav a",
    ".left-menu a",
    ".side-nav a",
    ".sub-nav a",
]


class NavigationHelper:
    """导航辅助类"""
    
    def __init__(self, max_depth: int = 5, max_links_per_level: int = 20):
        """
        Args:
            max_depth: 最大导航深度（1=仅主菜单，5=深入5层以找到深层指标项）
            max_links_per_level: 每层最多抓取的链接数（防止失控）
        """
        self.max_depth = max_depth
        self.max_links_per_level = max_links_per_level
        self.visited_urls: Set[str] = set()
    
    async def discover_navigation_links(self, page: Page, base_url: str) -> List[Dict]:
        """
        发现页面上的导航链接
        
        Returns:
            List of dicts: [{"url": str, "text": str, "category": str, "priority": int}, ...]
        """
        links = []
        
        for selector in NAV_SELECTORS:
            try:
                elements = await page.locator(selector).all()
                if elements:
                    logger.info(f"使用选择器发现导航: {selector}，找到{len(elements)}个链接")
                    
                    for elem in elements[:self.max_links_per_level]:
                        try:
                            href = await elem.get_attribute("href")
                            text = (await elem.inner_text()).strip()
                            
                            if not href or not text:
                                continue
                            
                            # 转换为绝对URL
                            abs_url = urljoin(base_url, href)
                            
                            # 过滤外部链接
                            if not self._is_same_domain(abs_url, base_url):
                                continue
                            
                            # 匹配栏目类别
                            category, priority = self._match_category(text)
                            
                            links.append({
                                "url": abs_url,
                                "text": text,
                                "category": category,
                                "priority": priority
                            })
                        except Exception as e:
                            logger.debug(f"解析链接失败: {e}")
                            continue
                    
                    # 找到有效选择器就停止
                    if links:
                        break
                        
            except Exception as e:
                logger.debug(f"选择器{selector}失败: {e}")
                continue
        
        # 按优先级排序
        links.sort(key=lambda x: x["priority"], reverse=True)
        
        if links:
            logger.info(f"发现{len(links)}个导航链接，优先级最高的5个: {[l['text'] for l in links[:5]]}")
        else:
            logger.warning(f"⚠️ 未发现任何导航链接！尝试了{len(NAV_SELECTORS)}个选择器")
        return links
    
    def _is_same_domain(self, url1: str, url2: str) -> bool:
        """检查两个URL是否同域"""
        return urlparse(url1).netloc == urlparse(url2).netloc
    
    def _match_category(self, link_text: str) -> tuple:
        """
        匹配链接文本到栏目类别
        
        Returns:
            (category_name, priority): 类别名称和优先级
        """
        link_lower = link_text.lower()
        
        for idx, (category, keywords) in enumerate(CATEGORY_KEYWORDS.items()):
            for keyword in keywords:
                if keyword in link_text or keyword.lower() in link_lower:
                    # 优先级：10 - idx（第一个栏目优先级10，第二个9...）
                    priority = 10 - idx
                    return category, priority
        
        # 未匹配到关键词，给默认优先级5
        return "其他栏目", 5
    
    async def navigate_and_discover_links(
        self, 
        page: Page, 
        url: str, 
        current_depth: int = 0
    ) -> List[str]:
        """
        导航到URL并发现该页面的所有子链接
        
        Args:
            page: Playwright页面对象
            url: 要访问的URL
            current_depth: 当前深度
        
        Returns:
            List[str]: 发现的子链接URL列表
        """
        if current_depth >= self.max_depth:
            logger.debug(f"达到最大深度{self.max_depth}，停止深入")
            return []
        
        if url in self.visited_urls:
            logger.debug(f"URL已访问，跳过: {url}")
            return []
        
        self.visited_urls.add(url)
        
        try:
            logger.info(f"[深度{current_depth}] 导航到: {url}")
            
            # 访问页面
            await page.goto(url, timeout=30000, wait_until='domcontentloaded')
            await page.wait_for_timeout(1500)  # 等待动态内容
            
            # 发现链接
            links = await self.discover_navigation_links(page, url)
            
            # 提取URL（去重）
            discovered_urls = list({link["url"] for link in links if link["url"] not in self.visited_urls})
            
            logger.info(f"[深度{current_depth}] 在 {url} 发现{len(discovered_urls)}个新链接")
            
            return discovered_urls[:self.max_links_per_level]
            
        except Exception as e:
            logger.error(f"导航到{url}失败: {e}")
            return []
    
    async def build_navigation_tree(
        self, 
        page: Page, 
        entry_url: str
    ) -> Dict:
        """
        从入口URL构建导航树
        
        Args:
            page: Playwright页面对象
            entry_url: 入口URL
        
        Returns:
            Dict: {
                "entry_url": str,
                "level_0": [url1, url2, ...],  # 入口页发现的链接
                "level_1": [url3, url4, ...],  # 二级页面发现的链接
                "all_urls": [all_unique_urls],
                "metadata": {...}
            }
        """
        tree = {
            "entry_url": entry_url,
            "level_0": [],
            "level_1": [],
            "all_urls": [],
            "metadata": {
                "max_depth": self.max_depth,
                "total_discovered": 0
            }
        }
        
        try:
            # Level 0: 从入口页发现的链接
            level_0_urls = await self.navigate_and_discover_links(page, entry_url, current_depth=0)
            tree["level_0"] = level_0_urls
            
            # Level 1: 从level_0链接发现的二级链接（如果max_depth >= 2）
            if self.max_depth >= 2:
                level_1_urls = []
                for url in level_0_urls[:5]:  # 只深入前5个高优先级链接
                    sub_urls = await self.navigate_and_discover_links(page, url, current_depth=1)
                    level_1_urls.extend(sub_urls)
                
                # 去重
                tree["level_1"] = list(set(level_1_urls))
            
            # 汇总所有URL
            all_urls = [entry_url] + tree["level_0"] + tree["level_1"]
            tree["all_urls"] = list(set(all_urls))
            tree["metadata"]["total_discovered"] = len(tree["all_urls"])
            
            logger.info(
                f"导航树构建完成: 入口1个 → Level0 {len(tree['level_0'])}个 → "
                f"Level1 {len(tree['level_1'])}个 | 总计{len(tree['all_urls'])}个URL"
            )
            
        except Exception as e:
            logger.error(f"构建导航树失败: {e}")
        
        return tree


async def extract_category_links(page: Page, category_keywords: List[str]) -> List[str]:
    """
    根据关键词提取特定栏目的链接
    
    Args:
        page: Playwright页面对象
        category_keywords: 栏目关键词列表，如 ["政策解读", "解读回应"]
    
    Returns:
        List[str]: 匹配的链接URL列表
    """
    matched_urls = []
    
    try:
        # 获取所有链接
        all_links = await page.locator("a").all()
        
        for link in all_links:
            try:
                text = (await link.inner_text()).strip()
                href = await link.get_attribute("href")
                
                if not href:
                    continue
                
                # 检查是否匹配关键词
                if any(kw in text for kw in category_keywords):
                    matched_urls.append(href)
                    logger.debug(f"匹配到栏目链接: {text} -> {href}")
                    
            except Exception:
                continue
        
        logger.info(f"根据关键词{category_keywords}找到{len(matched_urls)}个链接")
        
    except Exception as e:
        logger.error(f"提取栏目链接失败: {e}")
    
    return matched_urls


async def click_link_by_anchor(page: Page, anchors: List[str], base_url: str) -> Optional[Dict]:
    """
    根据anchor文本查找并点击链接，返回目标页面的内容
    
    Args:
        page: Playwright Page对象
        anchors: 要匹配的链接文本列表，如 ["机构职能", "机构职责", "部门职能"]
        base_url: 基础URL，用于相对路径解析
        
    Returns:
        Dict with: url, body, title, screenshot_path
        None if no matching link found
    """
    logger.info(f"查找匹配链接: {anchors}")
    
    # 等待页面完全加载
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except:
        pass  # 超时也继续尝试
    
    # 方法1: 直接按文本查找链接（不依赖特定选择器）
    for anchor in anchors:
        try:
            # 使用XPath按文本查找链接（用.匹配所有后代文本，包括span子元素）
            link = page.locator(f"//a[contains(., '{anchor}')]").first
            
            if await link.count() > 0:
                href = await link.get_attribute("href")
                text = await link.inner_text()
                text = text.strip().replace('\n', '')
                
                if href:
                    # 构建完整URL
                    if not href.startswith("http"):
                        href = urljoin(base_url, href)
                    
                    logger.info(f"[XPath] 找到匹配链接: '{text}' -> {href}")
                    
                    # 尝试点击
                    try:
                        await link.click()
                        await page.wait_for_load_state("domcontentloaded", timeout=10000)
                        
                        return {
                            "url": page.url,
                            "body": await page.content(),
                            "title": await page.title(),
                            "matched_anchor": anchor,
                            "link_text": text
                        }
                    except Exception as e:
                        logger.debug(f"XPath点击失败: {e}")
                        # 尝试直接导航
                        try:
                            await page.goto(href, timeout=10000)
                            await page.wait_for_load_state("domcontentloaded")
                            
                            return {
                                "url": page.url,
                                "body": await page.content(),
                                "title": await page.title(),
                                "matched_anchor": anchor,
                                "link_text": text
                            }
                        except:
                            pass
        except Exception as e:
            logger.debug(f"XPath查找失败 {anchor}: {e}")
    
    # 方法2: 遍历所有选择器
    for selector in NAV_SELECTORS:
        try:
            links = await page.locator(selector).all()
            
            for link in links:
                try:
                    text = await link.inner_text()
                    text = text.strip().replace('\n', '')
                    
                    # 检查链接文本是否匹配任意anchor
                    for anchor in anchors:
                        if anchor in text:
                            href = await link.get_attribute("href")
                            if not href:
                                continue
                            
                            # 构建完整URL
                            if not href.startswith("http"):
                                href = urljoin(base_url, href)
                            
                            logger.info(f"[选择器] 找到匹配链接: '{text}' -> {href}")
                            
                            # 点击链接
                            try:
                                await link.click()
                                await page.wait_for_load_state("domcontentloaded", timeout=10000)
                                
                                return {
                                    "url": page.url,
                                    "body": await page.content(),
                                    "title": await page.title(),
                                    "matched_anchor": anchor,
                                    "link_text": text
                                }
                                
                            except Exception as click_err:
                                logger.warning(f"点击链接失败: {click_err}")
                                # 尝试直接导航
                                try:
                                    await page.goto(href, timeout=10000)
                                    await page.wait_for_load_state("domcontentloaded")
                                    
                                    return {
                                        "url": page.url,
                                        "body": await page.content(),
                                        "title": await page.title(),
                                        "matched_anchor": anchor,
                                        "link_text": text
                                    }
                                except Exception as nav_err:
                                    logger.error(f"导航失败: {nav_err}")
                                    continue
                                    
                except Exception as e:
                    logger.debug(f"处理链接失败: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"选择器{selector}失败: {e}")
            continue
    
    logger.warning(f"未找到匹配链接: {anchors}")
    return None

