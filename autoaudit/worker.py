import base64
import random
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple

from .models import TraceStep
from .storage import RUNS_DIR, write_json

PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAL/57xvuwAAAABJRU5ErkJggg=="
)


class FetchResult:
    def __init__(self, url: str, status_code: int, body: str, elapsed: float, screenshot: str, snapshot: str):
        self.url = url
        self.status_code = status_code
        self.body = body
        self.elapsed = elapsed
        self.screenshot = screenshot
        self.snapshot = snapshot


class BrowserWorker:
    def __init__(self, batch_id: str, site_id: str):
        self.batch_id = batch_id
        self.site_id = site_id
        self.base_dir = RUNS_DIR / batch_id / f"site_{site_id}"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.traces: List[TraceStep] = []

    def _write_screenshot(self, name: str) -> str:
        path = self.base_dir / name
        with path.open("wb") as f:
            f.write(PLACEHOLDER_PNG)
        return str(path)

    def _write_snapshot(self, name: str, html: str) -> str:
        path = self.base_dir / name
        path.write_text(html, encoding="utf-8")
        return str(path)

    def fetch(self, url: str, step: str) -> FetchResult:
        start = time.time()
        body = ""
        status_code = 0
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                status_code = resp.getcode()
                body = resp.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            body = exc.read().decode("utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            status_code = 0
        elapsed = time.time() - start
        snapshot = self._write_snapshot(f"snapshot_{len(self.traces)}.html", body)
        screenshot = self._write_screenshot(f"screenshot_{len(self.traces)}.png")
        self.traces.append(TraceStep(step=step, url=url, status_code=status_code, elapsed=elapsed, screenshot=screenshot, snapshot=snapshot))
        return FetchResult(url, status_code, body, elapsed, screenshot, snapshot)

    def save_trace(self) -> str:
        trace_path = self.base_dir / "trace.json"
        trace_data = [trace.__dict__ for trace in self.traces]
        write_json(trace_path, trace_data)
        return str(trace_path)

    def sample_content_urls(self, site: Dict, per_list_recent_n: int, per_list_random_m: int, max_content_pages: int) -> List[str]:
        content_paths = site.get("content_paths", [])
        if not content_paths:
            return []
        ordered = content_paths[:per_list_recent_n]
        remaining = content_paths[per_list_recent_n:]
        random.shuffle(remaining)
        ordered.extend(remaining[:per_list_random_m])
        return ordered[:max_content_pages]

    def run_site(self, site: Dict, sampling: Dict, extra_depth: int = 0) -> Tuple[List[FetchResult], List[FetchResult]]:
        entry_results: List[FetchResult] = []
        content_results: List[FetchResult] = []
        for url in site.get("entry_points", []):
            entry_results.append(self.fetch(url, step="entry"))
        sampled_content = self.sample_content_urls(
            site,
            sampling.get("per_list_recent_n", 3),
            sampling.get("per_list_random_m", 2),
            sampling.get("max_content_pages_per_site", 30),
        )
        for url in sampled_content:
            content_results.append(self.fetch(url, step="content"))
        for _ in range(extra_depth):
            remaining = [u for u in site.get("content_paths", []) if u not in sampled_content]
            if not remaining:
                break
            url = remaining.pop(0)
            sampled_content.append(url)
            content_results.append(self.fetch(url, step="content_deepen"))
        return entry_results, content_results
