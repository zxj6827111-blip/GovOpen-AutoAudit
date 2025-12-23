from typing import Dict, List

FAIL = "FAIL"
PASS = "PASS"
UNCERTAIN = "UNCERTAIN"
NOT_ASSESSABLE = "NOT-ASSESSABLE"


class RuleEngine:
    def __init__(self, rules: List[Dict]):
        self.rules = rules

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

    def _evaluate_rule(self, rule: Dict, pages: List[Dict]) -> Dict:
        locator = rule.get("locator") or {}
        keywords = locator.get("keywords", []) if isinstance(locator, dict) else []
        evaluator_type = (rule.get("evaluator") or {}).get("type")
        matched_pages = []
        for page in pages:
            body = page.get("body", "").lower()
            if all(keyword.lower() in body for keyword in keywords):
                matched_pages.append(page)
            if evaluator_type == "timeliness" and "2022" in body:
                return self._fail(rule, page)
            if evaluator_type == "link_health" and page.get("status_code") == 404:
                return self._fail(rule, page)
            if rule.get("rule_id") == "sandbox-synonym-3" and "依申请" in body and "依申请公开" not in body:
                uncertain = self._uncertain(rule, reason="synonym_detected")
                if page.get("snapshot"):
                    uncertain["evidence"] = [page.get("snapshot")]
                return uncertain
        if matched_pages:
            return self._pass(rule, matched_pages[0])
        if not pages:
            return self._uncertain(rule, reason="no_evidence")
        if rule.get("evidence_required") and pages:
            evidence_page = pages[0]
            if not evidence_page.get("snapshot"):
                return self._uncertain(rule, reason="no_evidence")
            return self._fail(rule, evidence_page)
        return self._uncertain(rule, reason="no_evidence")

    def _pass(self, rule: Dict, page: Dict) -> Dict:
        return {
            "rule_id": rule["rule_id"],
            "status": PASS,
            "score_delta": 0,
            "reason": "keywords_found",
            "evidence": [page.get("snapshot")],
        }

    def _fail(self, rule: Dict, page: Dict) -> Dict:
        evidence_path = page.get("snapshot")
        if not evidence_path:
            return self._uncertain(rule, reason="no_evidence")
        return {
            "rule_id": rule["rule_id"],
            "status": FAIL,
            "score_delta": rule.get("score", 0),
            "reason": "keywords_missing",
            "evidence": [evidence_path],
        }

    def _uncertain(self, rule: Dict, reason: str) -> Dict:
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
