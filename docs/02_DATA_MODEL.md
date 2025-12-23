# 数据模型（核心对象与关系 v0.2）

## 1. 对象清单
- Org/Region：组织与区域树
- Site：站点库（入口 URL、类型、归属）
- SiteProfile：站点画像（同义词、路径提示、分页策略、搜索兜底等；可空）
- RulePack：指标库（地区标签、版本）
- Rule：规则（原子规则项）
- BatchRun：批次任务
- SiteRun：站点任务
- RunTrace：访问轨迹（步骤、URL、耗时、失败点）
- RuleResult：规则结果（四态）
- Evidence：证据（URL/截图/快照/命中片段，可复用）
- AiInvocation（可选）：AI 调用记录（provider/model/prompt_version/schema_version/latency）

## 2. 必须字段（关键）
### RuleResult
- status：PASS / FAIL / UNCERTAIN / NOT-ASSESSABLE
- score_delta：扣/得分（或扣分项记录）
- reason：结构化原因（machine-readable）
- evidence_ids：证据引用（允许复用）
- automation_level：FULL / PARTIAL / MANUAL（用于交付与抽检策略）
- confidence：0~1（规则引擎置信度；不是AI置信度）

### SiteRun
- status：queued/running/done/partial/failed
- coverage_stats：访问页数、抽样页数、规则覆盖率、命中页数
- failure_reason：blocked_403 / rate_limited_429 / captcha_detected / timeout / parse_error / ...
- trace_id：关联 RunTrace

### Rule（治理字段）
- mutex_group：互斥组（同事实多规则冲突时）
- cap_group：封顶组（同组扣分上限）
- max_penalty_in_group：封顶值
- severity：info/warn/penalty/critical

## 3. 证据组织（推荐目录）
evidence/
  batch_<id>/
    site_<id>/
      rule_<rule_id>/
        screenshot_*.png
        snapshot_*.html
        extract_*.json
        trace_*.json

## 4. 可追溯性要求
- 任意 RuleResult 可追溯到：rule_pack_id + rule_pack_version +（若用AI）provider/model/prompt_version。
