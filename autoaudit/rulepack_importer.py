import json
from datetime import datetime
from pathlib import Path
from typing import Dict

from .rulepack_validator import validate_rulepack, compute_rulepack_hash
from .storage import RULEPACK_DIR, write_json


class RulepackImportError(Exception):
    pass


def import_rulepack(path: Path) -> Dict:
    path = path.resolve()
    result = validate_rulepack(path)
    if not result["ok"]:
        raise RulepackImportError(json.dumps(result, ensure_ascii=False, indent=2))

    rp_json = json.loads((path / "rulepack.json").read_text(encoding="utf-8"))
    rule_pack_id = rp_json["rule_pack_id"]
    version = rp_json["version"]
    schema_version = rp_json.get("schema_version")
    content_hash = compute_rulepack_hash(path)

    target = RULEPACK_DIR / f"{rule_pack_id}_{version}.json"
    if target.exists():
        existing = json.loads(target.read_text(encoding="utf-8"))
        if existing.get("content_hash") == content_hash:
            return {"status": "already_imported", "rule_pack_id": rule_pack_id, "version": version}
        raise RulepackImportError(
            "conflict: same rule_pack_id+version already exists with different content. please upgrade version"
        )

    record = {
        "rule_pack_id": rule_pack_id,
        "version": version,
        "schema_version": schema_version,
        "imported_at": datetime.utcnow().isoformat(),
        "content_hash": content_hash,
        "source_path": str(path),
    }
    write_json(target, record)
    return {"status": "imported", **record, "validator": result}
