import json
import logging
from typing import Any, Dict, List, Optional

from . import SCHEMA_VERSION

logger = logging.getLogger(__name__)


SUGGESTION_SCHEMA_FIELDS = {
    "prompt_version": str,
    "suggested_class": int,
    "confidence": float,
    "suggested_check_type": str,
    "suggested_locator_keywords": list,
    "suggested_required_elements": list,
    "suggested_not_assessable_reason": str,
}


class SuggestionFailure(Exception):
    pass


def _basic_classifier(text: str) -> Dict[str, Any]:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ["无法", "不可访问", "评估不了", "网站打不开"]):
        suggested_class = 4
        suggested_check_type = "not_assessable"
        suggested_not_assessable_reason = "源文本包含无法评估提示"
        confidence = 0.4
    elif any(keyword in lowered for keyword in ["质量", "完整", "要素", "准确"]):
        suggested_class = 3
        suggested_check_type = "quality_elements"
        suggested_not_assessable_reason = ""
        confidence = 0.62
    elif any(keyword in lowered for keyword in ["抽查", "随机", "发现", "定位"]):
        suggested_class = 2
        suggested_check_type = "discovery"
        suggested_not_assessable_reason = ""
        confidence = 0.55
    else:
        suggested_class = 1
        suggested_check_type = "presence_or_timeliness"
        suggested_not_assessable_reason = ""
        confidence = 0.5

    keywords: List[str] = []
    for token in ["公开", "指南", "机构", "政策", "解读", "依申请", "预决算", "年报"]:
        if token in text:
            keywords.append(token)

    required_elements: List[str] = []
    if suggested_class == 3:
        for token in ["时间", "要素", "完整", "准确", "齐全"]:
            if token in text:
                required_elements.append(token)

    return {
        "prompt_version": "authoring_v1",
        "suggested_class": suggested_class,
        "confidence": float(confidence),
        "suggested_check_type": suggested_check_type,
        "suggested_locator_keywords": keywords,
        "suggested_required_elements": required_elements,
        "suggested_not_assessable_reason": suggested_not_assessable_reason,
    }


def _validate_suggestion(payload: Dict[str, Any]) -> Dict[str, Any]:
    for field, expected_type in SUGGESTION_SCHEMA_FIELDS.items():
        if field not in payload:
            raise SuggestionFailure(f"Missing suggestion field: {field}")
        value = payload[field]
        if expected_type is int and not isinstance(value, int):
            raise SuggestionFailure(f"Field {field} must be int")
        if expected_type is float and not isinstance(value, (float, int)):
            raise SuggestionFailure(f"Field {field} must be float")
        if expected_type is list and not isinstance(value, list):
            raise SuggestionFailure(f"Field {field} must be list")
        if expected_type is str and not isinstance(value, str):
            raise SuggestionFailure(f"Field {field} must be str")
    # normalize float type
    payload["confidence"] = float(payload["confidence"])
    return payload


def suggest_for_rule(rule: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        suggestion = _basic_classifier(rule.get("text", ""))
        validated = _validate_suggestion(suggestion)
        return validated
    except Exception as exc:
        logger.warning("Suggestion failed for rule %s: %s", rule.get("rule_id"), exc)
        return None


def apply_suggestions(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    updated: List[Dict[str, Any]] = []
    for rule in rules:
        suggestion = suggest_for_rule(rule)
        rule_copy = dict(rule)
        if suggestion:
            rule_copy["suggestions"] = suggestion
        else:
            rule_copy["suggestions"] = None
        updated.append(rule_copy)
    return updated
