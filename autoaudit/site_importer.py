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
        
        # 处理content_paths优先级
        if "content_paths" in site:
            normalized_paths = []
            for cp_idx, cp in enumerate(site["content_paths"]):
                # 如果是字符串，转为对象格式
                if isinstance(cp, str):
                    normalized_paths.append({"url": cp, "priority": 5, "tags": []})
                elif isinstance(cp, dict):
                    # 确保有url字段
                    if "url" not in cp:
                        raise SiteImportError(f"site {sid} content_path at index {cp_idx} missing url")
                    # 补充默认priority
                    if "priority" not in cp:
                        cp["priority"] = 5
                    # 校验priority范围
                    if not isinstance(cp["priority"], (int, float)) or not (0 <= cp["priority"] <= 10):
                        raise SiteImportError(f"site {sid} content_path priority must be 0-10, got {cp['priority']}")
                    # 补充默认tags
                    if "tags" not in cp:
                        cp["tags"] = []
                    normalized_paths.append(cp)
                else:
                    raise SiteImportError(f"site {sid} content_path at index {cp_idx} must be string or object")
            site["content_paths"] = normalized_paths

    target = SITE_DIR / "sites.json"
    record = {"imported_at": datetime.utcnow().isoformat(), "count": len(sites), "sites": sites}
    write_json(target, record)
    return {"status": "imported", **record}


def load_sites() -> List[Dict]:
    path = SITE_DIR / "sites.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("sites", [])
