import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .storage import SITE_DIR, write_json


class SiteImportError(Exception):
    pass


def import_sites(path: Path) -> Dict:
    path = path.resolve()
    try:
        sites = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise SiteImportError(str(exc))

    if not isinstance(sites, list) or len(sites) == 0:
        raise SiteImportError("site list must be non-empty array")

    seen_ids = set()
    for idx, site in enumerate(sites):
        if not isinstance(site, dict):
            raise SiteImportError(f"site at index {idx} must be object")
        sid = site.get("site_id")
        if not sid:
            raise SiteImportError(f"site at index {idx} missing site_id")
        if sid in seen_ids:
            raise SiteImportError(f"duplicate site_id {sid}")
        seen_ids.add(sid)
        if "base_url" not in site:
            raise SiteImportError(f"site {sid} missing base_url")
        if "entry_points" not in site:
            site["entry_points"] = [site["base_url"]]

    target = SITE_DIR / "sites.json"
    record = {"imported_at": datetime.utcnow().isoformat(), "count": len(sites), "sites": sites}
    write_json(target, record)
    return {"status": "imported", **record}


def load_sites() -> List[Dict]:
    path = SITE_DIR / "sites.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("sites", [])
