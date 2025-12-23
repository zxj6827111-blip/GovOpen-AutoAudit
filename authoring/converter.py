import csv
import importlib
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List

from . import SCHEMA_VERSION


DEFAULT_SCHEDULE = "ANNUAL"
DEFAULT_SEVERITY = "penalty"
DEFAULT_AUTOMATION_LEVEL = "FULL"
DEFAULT_CHECK_TYPE_BY_CLASS = {
    1: "presence_or_timeliness",
    2: "discovery",
    3: "quality_elements",
    4: "not_assessable",
}


class ConversionError(Exception):
    """Raised when conversion cannot proceed."""


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", text.strip())
    return slug.strip("-").lower() or "rule"


def _parse_number(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _row_to_rule(row: Dict[str, Any], rule_pack_id: str) -> Dict[str, Any]:
    section = row.get("section") or row.get("Section") or ""
    indicator = row.get("indicator") or row.get("Indicator") or ""
    item_no = row.get("item_no") or row.get("Item") or row.get("item") or row.get("item number") or ""
    text = row.get("text") or row.get("Text") or ""
    score_value = row.get("score") or row.get("Score")
    class_value = row.get("class") or row.get("Class") or 1
    schedule_value = row.get("schedule") or row.get("Schedule") or DEFAULT_SCHEDULE
    severity_value = row.get("severity") or row.get("Severity") or DEFAULT_SEVERITY
    check_type_value = row.get("check_type") or row.get("CheckType")

    try:
        class_int = int(class_value)
    except (ValueError, TypeError):
        class_int = 1

    check_type = check_type_value or DEFAULT_CHECK_TYPE_BY_CLASS.get(class_int, "presence_or_timeliness")
    score = _parse_number(score_value, 0.0)
    evidence_required = class_int != 4
    automation_level = "MANUAL" if class_int == 4 else DEFAULT_AUTOMATION_LEVEL

    base_rule_id = f"{rule_pack_id}-{indicator}-{item_no}" if indicator and item_no else f"{rule_pack_id}-{item_no or _slugify(text[:12])}"
    rule_id = _slugify(base_rule_id)

    return {
        "rule_id": rule_id,
        "section": str(section),
        "indicator": str(indicator),
        "item_no": str(item_no),
        "text": str(text),
        "class": class_int,
        "check_type": check_type,
        "schedule": str(schedule_value or DEFAULT_SCHEDULE),
        "score": score,
        "evidence_required": evidence_required,
        "allow_ai_assist": False,
        "automation_level": automation_level,
        "severity": str(severity_value or DEFAULT_SEVERITY),
        "locator": {},
        "extractor": {},
        "evaluator": {},
        "mutex_group": None,
        "cap_group": None,
        "max_penalty_in_group": None,
        "output_hints": None,
        "suggestions": None,
    }


def _load_rows_from_text(path: str) -> Iterable[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        sample = f.read().splitlines()
    if not sample:
        return []
    reader = csv.DictReader(sample)
    if reader.fieldnames and len(reader.fieldnames) > 1:
        return list(reader)
    return [{"text": line, "item_no": idx + 1} for idx, line in enumerate(sample) if line.strip()]


def _load_rows_from_excel(path: str) -> Iterable[Dict[str, Any]]:
    spec = importlib.util.find_spec("pandas")
    if spec is None:
        raise ConversionError("pandas is required to read Excel files. Please install pandas>=1.5.")
    pd = importlib.import_module("pandas")  # type: ignore

    try:
        df = pd.read_excel(path)
    except Exception as exc:  # pragma: no cover
        raise ConversionError(f"Failed to read Excel file: {exc}") from exc
    return df.to_dict(orient="records")


def load_rows(path: str) -> Iterable[Dict[str, Any]]:
    if not os.path.exists(path):
        raise ConversionError(f"Input file not found: {path}")
    lower = path.lower()
    if lower.endswith((".xlsx", ".xls")):
        return _load_rows_from_excel(path)
    return _load_rows_from_text(path)


def convert(input_path: str, output_dir: str, rule_pack_id: str, name: str, region_tag: str, scope: str, version: str, generated_from: str, allow_empty: bool = False) -> Dict[str, Any]:
    rows = list(load_rows(input_path))
    if not rows and not allow_empty:
        raise ConversionError("No rows parsed from input. Pass --allow-empty to proceed with an empty rule set.")

    os.makedirs(output_dir, exist_ok=True)
    rules: List[Dict[str, Any]] = [_row_to_rule(row, rule_pack_id) for row in rows]

    rulepack = {
        "rule_pack_id": rule_pack_id,
        "name": name,
        "region_tag": region_tag,
        "scope": scope,
        "version": version,
        "schema_version": SCHEMA_VERSION,
        "generated_from": generated_from,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
    }

    with open(os.path.join(output_dir, "rulepack.json"), "w", encoding="utf-8") as f:
        json.dump(rulepack, f, ensure_ascii=False, indent=2)

    with open(os.path.join(output_dir, "rules.json"), "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    return {"rulepack": rulepack, "rules": rules}
