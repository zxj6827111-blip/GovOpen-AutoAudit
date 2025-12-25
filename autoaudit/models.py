from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import hashlib


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


@dataclass
class Evidence:
    """统一证据对象schema"""
    evidence_id: str
    type: str  # "screenshot" | "text" | "file"
    rule_id: str
    site_id: str
    url: str
    timestamp: str  # ISO 8601
    locator: Optional[Dict] = None  # {"type": "selector", "value": "...", "text_quote": "..."}
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    content_hash: Optional[str] = None  # sha256:...
    metadata: Optional[Dict] = None  # {"highlight_applied": true}
    
    @staticmethod
    def create(rule_id: str, site_id: str, page: Dict, locator: Dict = None, rule: Dict = None, rule_hints: Dict = None) -> 'Evidence':
        """工厂方法：从页面创建Evidence对象"""
        # 生成唯一ID
        timestamp_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        url_hash = hashlib.md5(page['url'].encode()).hexdigest()[:8]
        evidence_id = f"evd_{timestamp_str}_{url_hash}"
        
        snapshot_path = page.get("snapshot")
        content_hash = None
        file_size = None
        
        # 计算文件哈希
        if snapshot_path:
            from pathlib import Path
            p = Path(snapshot_path)
            if p.exists():
                file_size = p.stat().st_size
                # 计算content_hash
                try:
                    content_hash = hashlib.sha256(p.read_bytes()).hexdigest()
                except Exception:
                    pass  # 文件读取失败，content_hash为None
        
        # 提取text_quote（如果有locator）
        text_quote = None
        if locator and "keywords" in locator:
            # 从页面body中提取匹配的关键词片段
            body = page.get("body", "")
            for kw in locator.get("keywords", []):
                if kw.lower() in body.lower():
                    # 提取关键词前后50字符作为quote
                    idx = body.lower().find(kw.lower())
                    start = max(0, idx - 50)
                    end = min(len(body), idx + len(kw) + 50)
                    text_quote = body[start:end]
                    break
        
        # 构建locator对象
        locator_obj = None
        if locator:
            locator_type = "selector" if "selector" in locator else "keywords"
            locator_value = locator.get("selector") or ", ".join(locator.get("keywords", []))
            locator_obj = {
                "type": locator_type,
                "value": locator_value,
                "text_quote": text_quote
            }
        
        # ✅ 检查是否应用了highlight
        highlight_applied = False
        if rule_hints and rule_hints.get("highlight"):
            highlight_applied = True
        
        # ✅ 保存AI提取结果
        ai_extracted = page.get("_ai_extracted")
        
        return Evidence(
            evidence_id=evidence_id,
            type="screenshot",  # 统一用screenshot
            rule_id=rule_id,
            site_id=site_id,
            url=page["url"],
            timestamp=datetime.utcnow().isoformat() + "Z",
            locator=locator_obj,
            file_path=snapshot_path,
            file_size_bytes=file_size,
            content_hash=f"sha256:{content_hash}" if content_hash else None,
            metadata={
                "highlight_applied": highlight_applied,
                "ai_extracted": ai_extracted
            }
        )


class EvidenceCache:
    """Evidence对象缓存，避免重复创建"""
    
    def __init__(self):
        self._cache = {}  # key: (rule_id, url) -> Evidence
        self._hits = 0
        self._misses = 0
    
    def get_or_create(
        self, 
        rule_id: str, 
        site_id: str, 
        page: Dict, 
        locator: Dict = None, 
        rule: Dict = None, 
        rule_hints: Dict = None
    ) -> 'Evidence':
        """获取或创建Evidence"""
        cache_key = (rule_id, page["url"])
        
        if cache_key in self._cache:
            self._hits += 1
            return self._cache[cache_key]
        
        # 缓存未命中，创建新Evidence
        self._misses += 1
        evidence = Evidence.create(rule_id, site_id, page, locator, rule, rule_hints)
        self._cache[cache_key] = evidence
        return evidence
    
    def get_stats(self) -> Dict:
        """获取缓存统计"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate": f"{hit_rate:.1f}%",
            "cache_size": len(self._cache)
        }
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
