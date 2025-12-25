import asyncio
import json
import uuid
from pathlib import Path
from typing import Dict, List

from .models import BatchRunResult
from .rule_engine import RuleEngine
from .storage import RUNS_DIR
from .dual_channel_worker import run_site_dual_channel
from .reporting import summarize


DEFAULT_SAMPLING = {
    "per_list_recent_n": 3,
    "per_list_random_m": 2,
    "max_content_pages_per_site": 30,
}


class BatchRunner:
    def __init__(self, rulepack_path: Path, sites: List[Dict], sampling: Dict | None = None):
        self.rulepack_path = rulepack_path
        self.sites = sites
        self.sampling = sampling or DEFAULT_SAMPLING
        self.rules = json.loads((rulepack_path / "rules.json").read_text(encoding="utf-8"))
        self.rulepack_meta = json.loads((rulepack_path / "rulepack.json").read_text(encoding="utf-8"))
        self.batch_id = f"batch_{uuid.uuid4().hex[:8]}"
        (RUNS_DIR / self.batch_id).mkdir(parents=True, exist_ok=True)

    async def run(self) -> BatchRunResult:
        # 并发控制：最多2个并发worker
        semaphore = asyncio.Semaphore(2)
        
        async def process_site(site):
            async with semaphore:
                return await self._run_site(site)
        
        # 并发执行所有站点
        tasks = [process_site(site) for site in self.sites]
        site_results = await asyncio.gather(*tasks)
        
        # summarize保持同步（无IO操作）
        summary_paths = summarize(
            batch_id=self.batch_id,
            site_results=site_results,
            rule_pack_id=self.rulepack_meta["rule_pack_id"],
            version=self.rulepack_meta["version"],
        )
        status = "done" if all(sr["status"] in {"done"} for sr in site_results) else "partial"
        return BatchRunResult(
            batch_id=self.batch_id,
            rule_pack_id=self.rulepack_meta["rule_pack_id"],
            rule_pack_version=self.rulepack_meta["version"],
            status=status,
            site_results=site_results,
            summary_path=summary_paths["summary"],
            issues_path=summary_paths["issues"],
            failures_path=summary_paths["failures"],
            evidence_zip=summary_paths["evidence_zip"],
        )

    async def _run_site(self, site: Dict) -> Dict:
        # 使用双通道worker
        entry_results, content_results = await run_site_dual_channel(
            self.batch_id,
            site["site_id"],
            site,
            self.sampling,
            rules=self.rules  # ✅ 传递规则用于红框标注
        )
        failures = []
        failure_meta = None
        for res in entry_results + content_results:
            if res.status_code in {403, 429}:
                reason = "blocked_403" if res.status_code == 403 else "rate_limited_429"
                failure_meta = {"reason": reason, "url": res.url, "screenshot": res.screenshot}
                failures.append(failure_meta)
                break
            if "captcha" in (res.body or "").lower():
                failure_meta = {"reason": "captcha_detected", "url": res.url, "screenshot": res.screenshot}
                failures.append(failure_meta)
                break
        if failures:
            status = "partial"
        else:
            status = "done"
        pages_payload = [
            {
                "url": res.url,
                "body": res.body,
                "snapshot": res.snapshot,
                "screenshot": res.screenshot,
                "status_code": res.status_code,
                "site_id": site["site_id"],  # 添加site_id用于Evidence创建
            }
            for res in entry_results + content_results
        ]
        rule_engine = RuleEngine(self.rules)
        rule_results = rule_engine.evaluate(pages_payload, failures)
        # trace已由dual_channel_worker保存
        trace_path = RUNS_DIR / self.batch_id / f"site_{site['site_id']}" / "trace.json"
        coverage_stats = {
            "entry_pages": len(entry_results),
            "content_pages": len(content_results),
            "rules": len(rule_results),
        }
        return {
            "site_id": site["site_id"],
            "status": status,
            "failure_reason": failures[0]["reason"] if failures else None,
            "failure_url": failure_meta.get("url") if failure_meta else None,
            "failure_screenshot": failure_meta.get("screenshot") if failure_meta else None,
            "trace_path": trace_path,
            "rule_results": rule_results,
            "coverage_stats": coverage_stats,
        }
