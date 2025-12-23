from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class TraceStep:
    step: str
    url: str
    status_code: int
    elapsed: float
    screenshot: Optional[str] = None
    snapshot: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class SiteRunResult:
    site_id: str
    status: str
    failure_reason: Optional[str]
    trace_path: str
    rule_results: List[Dict]
    coverage_stats: Dict


@dataclass
class BatchRunResult:
    batch_id: str
    rule_pack_id: str
    rule_pack_version: str
    status: str
    site_results: List[SiteRunResult] = field(default_factory=list)
    summary_path: Optional[str] = None
    issues_path: Optional[str] = None
    failures_path: Optional[str] = None
    evidence_zip: Optional[str] = None
