import json
import os
from typing import Any, Dict, List

from . import SCHEMA_VERSION


VALID_CLASSES = {1, 2, 3, 4}
VALID_CHECK_TYPES = {"presence_or_timeliness", "discovery", "quality_elements", "not_assessable"}
VALID_SCHEDULES = {"ANNUAL", "QUARTERLY", "MONTHLY", "WEEKLY"}
VALID_AUTOMATION_LEVELS = {"FULL", "PARTIAL", "MANUAL"}
VALID_SEVERITIES = {"info", "warn", "penalty", "critical"}


class ValidationIssue:
    def __init__(self, code: str, path: str, message: str):
        self.code = code
        self.path = path
        self.message = message

    def as_dict(self) -> Dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


class ValidationResult:
    def __init__(self, schema_version: str):
        self.schema_version = schema_version
        self.errors: List[ValidationIssue] = []
        self.warnings: List[ValidationIssue] = []

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, code: str, path: str, message: str):
        self.errors.append(ValidationIssue(code, path, message))

    def add_warning(self, code: str, path: str, message: str):
        self.warnings.append(ValidationIssue(code, path, message))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "schema_version": self.schema_version,
            "errors": [e.as_dict() for e in self.errors],
            "warnings": [w.as_dict() for w in self.warnings],
        }


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _validate_rulepack(rulepack: Dict[str, Any], directory: str, result: ValidationResult):
    required_fields = [
        "rule_pack_id",
        "name",
        "region_tag",
        "scope",
        "version",
        "schema_version",
        "generated_from",
        "generated_at",
    ]
    for field in required_fields:
        if field not in rulepack:
            result.add_error("MISSING_FIELD", f"rulepack.{field}", f"Missing required field {field}")
    if rulepack.get("schema_version") != SCHEMA_VERSION:
        result.add_error("UNSUPPORTED_SCHEMA_VERSION", "rulepack.schema_version", "schema_version must match frozen version")

    directory_name = os.path.basename(os.path.normpath(directory))
    if rulepack.get("rule_pack_id") and rulepack.get("rule_pack_id") != directory_name:
        result.add_error("RULEPACK_ID_MISMATCH", "rulepack.rule_pack_id", "rule_pack_id must match directory name")


def _validate_rule(rule: Dict[str, Any], index: int, seen_ids: set, result: ValidationResult):
    path_prefix = f"rules[{index}]"
    required_fields = [
        "rule_id",
        "section",
        "indicator",
        "item_no",
        "text",
        "class",
        "check_type",
        "schedule",
        "score",
        "evidence_required",
        "allow_ai_assist",
        "automation_level",
        "severity",
        "locator",
        "extractor",
        "evaluator",
    ]
    for field in required_fields:
        if field not in rule:
            result.add_error("MISSING_FIELD", f"{path_prefix}.{field}", f"Missing required field {field}")

    rule_id = rule.get("rule_id")
    if rule_id in seen_ids:
        result.add_error("RULE_ID_DUPLICATE", f"{path_prefix}.rule_id", f"Duplicated rule_id {rule_id}")
    seen_ids.add(rule_id)

    if rule.get("class") not in VALID_CLASSES:
        result.add_error("INVALID_CLASS", f"{path_prefix}.class", "class must be 1/2/3/4")

    if rule.get("check_type") not in VALID_CHECK_TYPES:
        result.add_error("INVALID_CHECK_TYPE", f"{path_prefix}.check_type", "check_type value is not supported")

    if rule.get("schedule") not in VALID_SCHEDULES:
        result.add_error("INVALID_SCHEDULE", f"{path_prefix}.schedule", "schedule must be ANNUAL|QUARTERLY|MONTHLY|WEEKLY")

    score = rule.get("score")
    if not isinstance(score, (int, float)):
        result.add_error("INVALID_SCORE", f"{path_prefix}.score", "score must be a number")

    class_value = rule.get("class")
    evidence_required = rule.get("evidence_required")
    automation_level = rule.get("automation_level")
    if class_value in {1, 2, 3} and evidence_required is not True:
        result.add_error("EVIDENCE_REQUIRED_MISMATCH", f"{path_prefix}.evidence_required", "class 1/2/3 must require evidence")
    if class_value == 4:
        if evidence_required is not False:
            result.add_error("EVIDENCE_REQUIRED_MISMATCH", f"{path_prefix}.evidence_required", "class 4 must set evidence_required=false")
        if automation_level != "MANUAL":
            result.add_error("AUTOMATION_LEVEL_MISMATCH", f"{path_prefix}.automation_level", "class 4 must set automation_level=MANUAL")

    if automation_level not in VALID_AUTOMATION_LEVELS:
        result.add_error("INVALID_AUTOMATION_LEVEL", f"{path_prefix}.automation_level", "automation_level value is invalid")

    severity = rule.get("severity")
    if severity not in VALID_SEVERITIES:
        result.add_error("INVALID_SEVERITY", f"{path_prefix}.severity", "severity must be info|warn|penalty|critical")

    cap_group = rule.get("cap_group")
    max_penalty_in_group = rule.get("max_penalty_in_group")
    if max_penalty_in_group is not None and cap_group in (None, ""):
        result.add_error("CAP_GROUP_REQUIRED", f"{path_prefix}.max_penalty_in_group", "max_penalty_in_group requires cap_group")
    if max_penalty_in_group is not None and not isinstance(max_penalty_in_group, (int, float)):
        result.add_error("INVALID_CAP_VALUE", f"{path_prefix}.max_penalty_in_group", "max_penalty_in_group must be number or null")

    # governance fields types when present
    if rule.get("mutex_group") is not None and not isinstance(rule.get("mutex_group"), str):
        result.add_error("INVALID_MUTEX", f"{path_prefix}.mutex_group", "mutex_group must be string or null")

    for obj_field in ["locator", "extractor", "evaluator"]:
        if obj_field in rule and not isinstance(rule.get(obj_field), dict):
            result.add_error("INVALID_FIELD_TYPE", f"{path_prefix}.{obj_field}", f"{obj_field} must be object/dict")
        elif obj_field not in rule:
            result.add_error("MISSING_FIELD", f"{path_prefix}.{obj_field}", f"Missing required field {obj_field}")


def validate(rulepack_dir: str, allow_empty: bool = False) -> ValidationResult:
    result = ValidationResult(SCHEMA_VERSION)
    rulepack_path = os.path.join(rulepack_dir, "rulepack.json")
    rules_path = os.path.join(rulepack_dir, "rules.json")

    if not os.path.exists(rulepack_path):
        result.add_error("RULEPACK_NOT_FOUND", "rulepack.json", "rulepack.json not found")
        return result
    if not os.path.exists(rules_path):
        result.add_error("RULES_NOT_FOUND", "rules.json", "rules.json not found")
        return result

    try:
        rulepack = _load_json(rulepack_path)
    except Exception as exc:
        result.add_error("RULEPACK_PARSE_ERROR", "rulepack.json", f"Failed to parse rulepack.json: {exc}")
        return result

    _validate_rulepack(rulepack, rulepack_dir, result)

    try:
        rules = _load_json(rules_path)
    except Exception as exc:
        result.add_error("RULES_PARSE_ERROR", "rules.json", f"Failed to parse rules.json: {exc}")
        return result

    if not isinstance(rules, list):
        result.add_error("INVALID_RULES_TYPE", "rules", "rules.json must be an array")
        return result

    if not rules and not allow_empty:
        result.add_error("RULES_EMPTY", "rules", "rules.json cannot be empty unless --allow-empty is provided")
        return result

    seen_ids = set()
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            result.add_error("INVALID_RULE_TYPE", f"rules[{idx}]", "Each rule must be an object")
            continue
        _validate_rule(rule, idx, seen_ids, result)

    return result
