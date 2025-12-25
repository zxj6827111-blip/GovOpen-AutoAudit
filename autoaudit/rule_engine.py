from typing import Dict, List
import logging

from .models import Evidence, EvidenceCache

logger = logging.getLogger(__name__)

FAIL = "FAIL"
PASS = "PASS"
UNCERTAIN = "UNCERTAIN"
NOT_ASSESSABLE = "NOT-ASSESSABLE"


class RuleEngine:
    def __init__(self, rules: List[Dict]):
        self.rules = rules
        self.evidence_cache = EvidenceCache()  # ✅ 新增缓存

    def evaluate(self, pages: List[Dict], failures: List[Dict]) -> List[Dict]:
        results: List[Dict] = []
        blocked = any(f["reason"] in {"blocked_403", "rate_limited_429", "captcha_detected"} for f in failures)
        for rule in self.rules:
            if rule.get("class") == 4:
                results.append(self._not_assessable(rule))
                continue
            if blocked:
                results.append(self._uncertain(rule, reason="access_control"))
                continue
            result = self._evaluate_rule(rule, pages)
            results.append(result)
        return results
    
    def _extract_page_title(self, page: Dict) -> str:
        """从页面提取标题作为栏目名称"""
        # 优先使用页面元数据中的title
        if page.get("title"):
            return page["title"]
        
        # 从HTML中提取<title>
        body = page.get("body", "")
        if "<title>" in body.lower():
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(body, 'html.parser')
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.get_text().strip()
                    # 清理常见后缀
                    for suffix in ["-宿迁市人民政府", "宿迁市人民政府", "-政务公开"]:
                        title = title.replace(suffix, "").strip()
                    return title if title else "未知页面"
            except:
                pass
        
        # 从URL提取页面名称
        url = page.get("url", "")
        if url:
            path = url.split("/")[-1].replace(".shtml", "").replace(".html", "")
            return path if path else "首页"
        
        return "未知页面"
    
    def _locate_pages(self, locator: Dict, all_pages: List[Dict], rule: Dict = None) -> List[Dict]:
        """根据locator或targets筛选匹配的页面"""
        
        # ✅ 新增：处理targets字段（新规则格式）
        if rule and rule.get("targets"):
            return self._locate_by_targets(rule.get("targets"), all_pages)
        
        if not locator:
            return all_pages
        
        matched_pages = []
        
        # 处理keywords定位 (OR逻辑)
        if "keywords" in locator:
            keywords = locator["keywords"]
            for page in all_pages:
                body = page.get("body", "").lower()
                # ✅ 修正Bug: all() → any()
                if any(kw.lower() in body for kw in keywords):
                    matched_pages.append(page)
            return matched_pages
        
        # 处理selector定位
        elif "selector" in locator:
            from bs4 import BeautifulSoup
            selector = locator["selector"]
            for page in all_pages:
                soup = BeautifulSoup(page.get("body", ""), 'html.parser')
                if soup.select(selector):
                    matched_pages.append(page)
            return matched_pages
        
        else:
            # 无locator时返回所有页面
            return all_pages
    
    def _locate_by_targets(self, targets: List[Dict], all_pages: List[Dict]) -> List[Dict]:
        """
        根据targets字段定位页面
        targets包含anchors_any：在页面中查找包含对应文本的链接，返回链接指向的页面
        """
        from bs4 import BeautifulSoup
        
        matched_pages = []
        
        for target in targets:
            anchors_any = target.get("anchors_any", [])
            
            if not anchors_any:
                continue
            
            # 遍历所有页面，找到包含匹配链接的页面
            for page in all_pages:
                body = page.get("body", "")
                page_url = page.get("url", "")
                
                # 方法1：检查页面URL或标题是否包含anchor关键词
                page_title = self._extract_page_title(page)
                for anchor in anchors_any:
                    if anchor.lower() in page_title.lower() or anchor.lower() in page_url.lower():
                        if page not in matched_pages:
                            matched_pages.append(page)
                            logger.info(f"targets匹配: '{anchor}' → {page_url}")
                        break
                
                # 方法2：检查页面body中是否有这些关键词的链接
                try:
                    soup = BeautifulSoup(body, 'html.parser')
                    for anchor in anchors_any:
                        # 查找链接文本包含anchor的<a>标签
                        links = soup.find_all('a', string=lambda text: text and anchor in text)
                        if links:
                            # 这个页面有匹配的导航链接，说明它是入口页面
                            # 我们需要的是链接指向的目标页面，但当前可能还没有访问到
                            # 先标记这个页面为候选
                            pass
                except Exception as e:
                    logger.warning(f"解析页面失败: {e}")
        
        # 如果没有匹配到targets，返回所有包含anchors关键词的页面
        if not matched_pages:
            for page in all_pages:
                body = page.get("body", "").lower()
                for target in targets:
                    for anchor in target.get("anchors_any", []):
                        if anchor.lower() in body:
                            if page not in matched_pages:
                                matched_pages.append(page)
                            break
        
        return matched_pages if matched_pages else all_pages
    
    def _evaluate_content(self, evaluator: Dict, matched_pages: List[Dict], rule: Dict) -> Dict:
        """评估匹配页面的内容，支持4种evaluator类型"""
        if not matched_pages:
            return self._uncertain(rule, reason="no_pages_matched")
        
        eval_type = evaluator.get("type")
        
        # Type 1: presence_selector
        if eval_type == "presence_selector":
            from bs4 import BeautifulSoup
            locator_selector = rule.get("locator", {}).get("selector")
            for page in matched_pages:
                soup = BeautifulSoup(page.get("body", ""), 'html.parser')
                if soup.select(locator_selector):
                    return self._pass(rule, page)
            return self._fail(rule, matched_pages[0])
        
        # Type 2: presence_keywords
        elif eval_type == "presence_keywords":
            eval_keywords = evaluator.get("keywords", [])
            for page in matched_pages:
                body = page.get("body", "").lower()
                if any(kw.lower() in body for kw in eval_keywords):
                    return self._pass(rule, page)
            return self._fail(rule, matched_pages[0])
        
        # Type 3: presence_all (需要extractor)
        elif eval_type == "presence_all":
            required_fields = evaluator.get("required_fields", [])
            
            # M1完整实现: 调用AI提取
            from .ai_extractor import AIExtractor
            
            extractor = AIExtractor()
            for page in matched_pages:
                body = page.get("body", "")
                
                # 调用AI提取字段
                extracted = extractor.extract_fields(body, required_fields)
                
                # 验证所有required_fields都有值
                all_present = all(
                    extracted.get(field) is not None and extracted.get(field) != ""
                    for field in required_fields
                )
                
                if all_present:
                    # 将提取结果附加到page metadata
                    page["_ai_extracted"] = extracted
                    logger.info(f"AI extracted all required fields: {extracted}")
                    return self._pass(rule, page)
                else:
                    logger.warning(f"AI extraction incomplete: {extracted}")
            
            # 所有页面都未能提取完整字段
            return self._fail(rule, matched_pages[0])
        
        # Type 4: presence_regex
        elif eval_type == "presence_regex":
            import re
            pattern = evaluator.get("pattern")
            for page in matched_pages:
                body = page.get("body", "")
                if re.search(pattern, body):
                    return self._pass(rule, page)
            return self._fail(rule, matched_pages[0])
        
        # ✅ 新增：支持新规则格式 - 当evaluator为空时，从rule直接读取
        elif eval_type is None:
            # 检查rule本身是否有新格式的检查类型
            rule_type = rule.get("type")
            
            if rule_type in ["presence_any", "content_presence"]:
                # 使用pass_if_regex_any匹配
                patterns = rule.get("pass_if_regex_any", [])
                import re
                
                for page in matched_pages:
                    body = page.get("body", "")
                    matched_keywords = []
                    
                    for pattern in patterns:
                        if re.search(pattern, body, re.IGNORECASE):
                            matched_keywords.append(pattern)
                    
                    if matched_keywords:
                        return self._pass(rule, page, matched_keywords=matched_keywords)
                
                return self._fail(rule, matched_pages[0])
            
            elif rule_type == "existence":
                # 检查页面中是否存在locate.keywords_any中的关键词
                locate = rule.get("locate", {})
                keywords = locate.get("keywords_any", [])
                
                for page in matched_pages:
                    body = page.get("body", "").lower()
                    for kw in keywords:
                        if kw.lower() in body:
                            return self._pass(rule, page, matched_keywords=[kw])
                
                return self._fail(rule, matched_pages[0])
            
            elif rule_type == "link_health":
                # 检查链接是否有效（依赖depends_on_rule）
                # 简化实现：只要页面能加载就算通过
                if matched_pages:
                    return self._pass(rule, matched_pages[0])
                return self._fail(rule, matched_pages[0] if matched_pages else {"url": "unknown"})
            
            elif rule_type in ["freshness", "deadline"]:
                # 时效性检查需要日期字段，暂时返回UNCERTAIN
                return self._uncertain(rule, reason="date_check_not_implemented", pages=matched_pages)
            
            else:
                return self._uncertain(rule, reason=f"unknown_rule_type_{rule_type}")
        
        else:
            return self._uncertain(rule, reason=f"unknown_evaluator_{eval_type}")

    def _evaluate_rule(self, rule: Dict, pages: List[Dict]) -> Dict:
        """评估单条规则 - 重构版"""
        # Class 4: 手工评估
        if rule.get("class") == 4:
            return self._not_assessable(rule)
        
        # 1. 定位阶段 - ✅ 传递rule参数以支持targets
        locator = rule.get("locator", {})
        matched_pages = self._locate_pages(locator, pages, rule=rule)
        
        if not matched_pages:
            # ✅ 传递pages给_uncertain用于AI复核
            return self._uncertain(rule, reason="no_pages_matched", pages=pages)
        
        # 2. 评估阶段
        evaluator = rule.get("evaluator", {})
        return self._evaluate_content(evaluator, matched_pages, rule)

    def _pass(self, rule: Dict, page: Dict, matched_keywords: List[str] = None) -> Dict:
        """返回PASS结果，包含详细匹配信息"""
        # 创建Evidence对象（使用缓存）
        evidence = self.evidence_cache.get_or_create(
            rule_id=rule["rule_id"],
            site_id=page.get("site_id", "unknown"),
            page=page,
            locator=rule.get("locator"),
            rule=rule
        )
        
        # ✅ 增强：提取页面标题作为栏目名称
        page_title = self._extract_page_title(page)
        
        return {
            "rule_id": rule["rule_id"],
            "status": PASS,
            "score_delta": 0,
            "reason": "keywords_found",
            "evidence_ids": [evidence.evidence_id],
            # ✅ 新增详细信息字段
            "matched_url": page.get("url", ""),
            "matched_column": page_title,  # 栏目名称
            "element": rule.get("element", rule.get("description", "")),  # 检查要素
            "matched_keywords": matched_keywords or [],  # 命中的关键词
            "screenshot": page.get("screenshot", ""),
            "detail": f"在'{page_title}'页面找到匹配内容"
        }

    def _fail(self, rule: Dict, page: Dict) -> Dict:
        evidence_path = page.get("snapshot")
        if not evidence_path:
            return self._uncertain(rule, reason="no_evidence")
        
        # ✅ 构建rule_hints，告诉Playwright要高亮显示问题
        rule_hints = {
            "highlight": True,  # 启用红框标注
            "locator": rule.get("locator", {}),  # 传递定位器信息
            "problem_description": f"规则失败: {rule.get('description', 'N/A')}"
        }
        
        # 创建Evidence对象（使用缓存）
        evidence = self.evidence_cache.get_or_create(
            rule_id=rule["rule_id"],
            site_id=page.get("site_id", "unknown"),
            page=page,
            locator=rule.get("locator"),
            rule=rule,
            rule_hints=rule_hints  # ✅ 传递rule_hints
        )
        
        # 二次校验：Evidence对象有效性（content_hash存在表示文件可读）
        if not evidence.content_hash:
            logger.warning(
                f"Rule {rule['rule_id']} FAIL but evidence file missing/corrupt, "
                f"downgrading to UNCERTAIN"
            )
            return self._uncertain(rule, reason="no_evidence_file")
        
        # ✅ 获取扣分值（优先使用新格式deduct_if_fail）
        deduction = rule.get("deduct_if_fail", rule.get("score", 0))
        page_title = self._extract_page_title(page)
        
        return {
            "rule_id": rule["rule_id"],
            "status": FAIL,
            "score_delta": deduction,
            "reason": "keywords_missing",
            "evidence_ids": [evidence.evidence_id],
            # ✅ 新增详细信息字段
            "matched_url": page.get("url", ""),
            "matched_column": page_title,
            "element": rule.get("element", rule.get("description", "")),
            "deduct_if_fail": deduction,
            "screenshot": page.get("screenshot", ""),
            "detail": f"在'{page_title}'页面未找到所需内容",
            "notes": rule.get("notes", "")
        }

    def _uncertain(self, rule: Dict, reason: str, pages: List[Dict] = None) -> Dict:
        """
        返回UNCERTAIN结果，可选AI复核
        
        Args:
            rule: 规则定义
            reason: UNCERTAIN原因
            pages: 所有页面内容（用于AI复核，可选）
        """
        # ✅ 新增: AI复核UNCERTAIN规则（环境变量控制）
        import os
        enable_ai_review = os.environ.get("ENABLE_AI_REVIEW", "false").lower() == "true"
        
        if enable_ai_review and pages:
            try:
                from .ai_extractor import AIExtractor
                
                # 创建AI提取器实例（共享实例以控制token消耗）
                if not hasattr(self, '_ai_extractor'):
                    self._ai_extractor = AIExtractor(
                        primary_provider="deepseek",
                        fallback_provider="qwen",
                        max_cost_per_batch=2000  # 2000 tokens限制
                    )
                
                logger.info(f"对规则 {rule['rule_id']} 进行AI复核（原因: {reason}）")
                ai_result = self._ai_extractor.review_uncertain_rule(rule, pages, reason)
                
                # 高置信度（>0.8）才采纳AI判断
                if ai_result["confidence"] > 0.8:
                    logger.info(
                        f"AI复核高置信度结果: {ai_result['status']} "
                        f"(confidence: {ai_result['confidence']:.2f})"
                    )
                    
                    # 根据AI判断返回适当的状态
                    if ai_result["status"] == "FAIL":
                        # AI判定为FAIL，但需要有evidence才能标记FAIL
                        # 这里我们返回带AI reasoning的FAIL
                        return {
                            "rule_id": rule["rule_id"],
                            "status": FAIL,
                            "score_delta": rule.get("score", 0),
                            "reason": f"ai_reviewed_{reason}",
                            "ai_confidence": ai_result["confidence"],
                            "ai_reasoning": ai_result["reasoning"],
                            "evidence": [],  # AI判定的FAIL可能没有screenshot evidence
                        }
                    elif ai_result["status"] == "PASS":
                        return {
                            "rule_id": rule["rule_id"],
                            "status": PASS,
                            "score_delta": 0,
                            "reason": f"ai_reviewed_{reason}",
                            "ai_confidence": ai_result["confidence"],
                            "ai_reasoning": ai_result["reasoning"],
                            "evidence": [],
                        }
                    # else: ai_result["status"] == "UNCERTAIN" → 继续使用原UNCERTAIN逻辑
                else:
                    logger.info(
                        f"AI复核置信度不足({ai_result['confidence']:.2f})，"
                        f"保持UNCERTAIN状态"
                    )
                    # 附加AI建议到reason中
                    return {
                        "rule_id": rule["rule_id"],
                        "status": UNCERTAIN,
                        "score_delta": 0,
                        "reason": reason,
                        "ai_reviewed": True,
                        "ai_confidence": ai_result["confidence"],
                        "ai_suggestion": ai_result["suggested_action"],
                        "evidence": [],
                    }
                    
            except Exception as e:
                logger.error(f"AI复核失败: {e}")
                # AI复核失败，返回原UNCERTAIN
        
        # 原有UNCERTAIN返回（未启用AI或AI复核失败）
        return {
            "rule_id": rule["rule_id"],
            "status": UNCERTAIN,
            "score_delta": 0,
            "reason": reason,
            "evidence": [],
        }

    def _not_assessable(self, rule: Dict) -> Dict:
        return {
            "rule_id": rule["rule_id"],
            "status": NOT_ASSESSABLE,
            "score_delta": 0,
            "reason": "manual_only",
            "evidence": [],
        }
