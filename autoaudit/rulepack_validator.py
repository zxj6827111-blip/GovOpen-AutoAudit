import json
from pathlib import Path
from typing import Dict, List, Any

from .storage import combined_hash


REQUIRED_RULE_FIELDS = {
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
}

ALLOWED_CLASSES = {1, 2, 3, 4}
ALLOWED_CHECK_TYPES = {
    "presence_or_timeliness",
    "discovery",
    "quality_elements",
    "not_assessable",
}
ALLOWED_SCHEDULES = {"ANNUAL", "QUARTERLY", "MONTHLY", "WEEKLY"}
ALLOWED_AUTOMATION = {"FULL", "PARTIAL", "MANUAL"}
ALLOWED_SEVERITY = {"info", "warn", "penalty", "critical"}


class RulepackValidator:
    def __init__(self, rulepack_dir: Path):
        self.rulepack_dir = rulepack_dir
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.rulepack: Dict[str, Any] = {}
        self.rules: List[Dict[str, Any]] = []

    def validate(self) -> Dict[str, Any]:
        self.errors = []
        self.warnings = []
        self._validate_rulepack_json()
        self._validate_rules_json()
        ok = len(self.errors) == 0
        schema_version = self.rulepack.get("schema_version") if isinstance(self.rulepack, dict) else None
        return {
            "ok": ok,
            "schema_version": schema_version,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def _validate_rulepack_json(self) -> None:
        path = self.rulepack_dir / "rulepack.json"
        if not path.exists():
            self.errors.append({"code": "MISSING_RULEPACK", "path": "rulepack.json", "message": "rulepack.json not found"})
            return
        try:
            with path.open("r", encoding="utf-8") as f:
                self.rulepack = json.load(f)
        except Exception as exc:  # noqa: BLE001
            self.errors.append({"code": "INVALID_JSON", "path": "rulepack.json", "message": str(exc)})
            return

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
            if field not in self.rulepack:
                self.errors.append({"code": "MISSING_FIELD", "path": f"rulepack.json.{field}", "message": "required"})
        dirname = self.rulepack_dir.name
        if self.rulepack.get("rule_pack_id") and dirname != self.rulepack.get("rule_pack_id"):
            self.errors.append({"code": "RULE_PACK_ID_MISMATCH", "path": "rulepack.json.rule_pack_id", "message": "must match directory name"})

    def _validate_rules_json(self) -> None:
        path = self.rulepack_dir / "rules.json"
        if not path.exists():
            self.errors.append({"code": "MISSING_RULES", "path": "rules.json", "message": "rules.json not found"})
            return
        try:
            with path.open("r", encoding="utf-8") as f:
                self.rules = json.load(f)
        except Exception as exc:  # noqa: BLE001
            self.errors.append({"code": "INVALID_JSON", "path": "rules.json", "message": str(exc)})
            return
        if not isinstance(self.rules, list):
            self.errors.append({"code": "INVALID_STRUCTURE", "path": "rules", "message": "rules.json must be an array"})
            return
        if len(self.rules) == 0:
            self.errors.append({"code": "EMPTY_RULES", "path": "rules", "message": "rules cannot be empty"})
        seen_rule_ids = set()
        for idx, rule in enumerate(self.rules):
            path_prefix = f"rules[{idx}]"
            if not isinstance(rule, dict):
                self.errors.append({"code": "INVALID_RULE", "path": path_prefix, "message": "rule must be object"})
                continue
            missing = REQUIRED_RULE_FIELDS - set(rule.keys())
            for field in sorted(missing):
                self.errors.append({"code": "MISSING_FIELD", "path": f"{path_prefix}.{field}", "message": "required"})
            rule_id = rule.get("rule_id")
            if rule_id in seen_rule_ids:
                self.errors.append({"code": "RULE_ID_DUPLICATE", "path": f"{path_prefix}.rule_id", "message": "duplicate rule_id"})
            else:
                seen_rule_ids.add(rule_id)
            self._validate_rule_fields(rule, path_prefix)

    def _validate_rule_fields(self, rule: Dict[str, Any], prefix: str) -> None:
        cls = rule.get("class")
        if cls not in ALLOWED_CLASSES:
            self.errors.append({"code": "INVALID_CLASS", "path": f"{prefix}.class", "message": "must be 1/2/3/4"})
        if rule.get("check_type") not in ALLOWED_CHECK_TYPES:
            self.errors.append({"code": "INVALID_CHECK_TYPE", "path": f"{prefix}.check_type", "message": "invalid check_type"})
        if rule.get("schedule") not in ALLOWED_SCHEDULES:
            self.errors.append({"code": "INVALID_SCHEDULE", "path": f"{prefix}.schedule", "message": "invalid schedule"})
        if rule.get("automation_level") not in ALLOWED_AUTOMATION:
            self.errors.append({"code": "INVALID_AUTOMATION", "path": f"{prefix}.automation_level", "message": "invalid automation_level"})
        if rule.get("severity") not in ALLOWED_SEVERITY:
            self.errors.append({"code": "INVALID_SEVERITY", "path": f"{prefix}.severity", "message": "invalid severity"})
        score = rule.get("score")
        if not isinstance(score, (int, float)):
            self.errors.append({"code": "INVALID_SCORE", "path": f"{prefix}.score", "message": "score must be number"})
        if cls == 4:
            if rule.get("evidence_required") is not False:
                self.errors.append({"code": "CLASS4_EVIDENCE_RULE", "path": f"{prefix}.evidence_required", "message": "class=4 requires evidence_required=false"})
            if rule.get("automation_level") != "MANUAL":
                self.errors.append({"code": "CLASS4_AUTOMATION_RULE", "path": f"{prefix}.automation_level", "message": "class=4 requires automation_level=MANUAL"})
        else:
            if rule.get("evidence_required") is not True:
                self.errors.append({"code": "EVIDENCE_REQUIRED", "path": f"{prefix}.evidence_required", "message": "class 1/2/3 require evidence"})
        mutex = rule.get("mutex_group")
        cap = rule.get("cap_group")
        max_penalty = rule.get("max_penalty_in_group")
        if max_penalty is not None and cap is None:
            self.errors.append({"code": "CAP_GROUP_REQUIRED", "path": f"{prefix}.max_penalty_in_group", "message": "max_penalty_in_group requires cap_group"})
        if mutex is not None and not isinstance(mutex, str):
            self.errors.append({"code": "INVALID_MUTEX", "path": f"{prefix}.mutex_group", "message": "mutex_group must be string or null"})
        if cap is not None and not isinstance(cap, str):
            self.errors.append({"code": "INVALID_CAP", "path": f"{prefix}.cap_group", "message": "cap_group must be string or null"})


def validate_rulepack(path: Path) -> Dict[str, Any]:
    validator = RulepackValidator(path)
    return validator.validate()


def compute_rulepack_hash(path: Path) -> str:
    return combined_hash([path / "rulepack.json", path / "rules.json"])
