# 规则表达规范（Rule Spec v0.2）

> 各地业务指标不复用，但“规则如何被平台表达”的结构应统一，便于导入、校验、执行与报告。

## 1. 四大类（Class）定义
- **Class 1：EXISTENCE_STRUCTURE**（有无/结构/字段）→ 纯规则判定，不用 AI
- **Class 2：DISCOVERY_TIMELINESS**（发现/定位/抽样/时效）→ 纯规则为主，可用站点画像兜底
- **Class 3：QUALITY_ELEMENTS**（质量/要素）→ 允许 AI 辅助抽取要素与证据句，但不输出最终结论
- **Class 4：NOT_ASSESSABLE**（网站端不可判断）→ 输出 NOT-ASSESSABLE，生成“材料清单”提示

## 2. Rule 最小字段（导入级）
- rule_id：唯一
- rule_pack_id + version
- section：指标大章
- indicator：二级指标名称
- item_no：原文条款序号（1/2/3…）
- text：原文条款（保留）
- class：1/2/3/4
- check_type：presence_or_timeliness / discovery / quality_elements / not_assessable
- schedule：ANNUAL / QUARTERLY / MONTHLY / WEEKLY（可配置）
- score：扣/得分（或扣分幅度）
- evidence_required：Class 1/2/3 必须 true
- allow_ai_assist：仅 Class 3 默认 true
- automation_level：FULL / PARTIAL / MANUAL
- severity：info/warn/penalty/critical
- mutex_group / cap_group / max_penalty_in_group（可空）
- locator：定位策略（关键词/路径提示/锚点/页面类型）
- extractor：抽取字段（日期/负责人/联系方式/附件可达性/要素列表等）
- evaluator：判定逻辑（存在性/阈值/要素计数/时效窗口等）
- output_hints：报告展示提示（可空）

## 3. 证据与保守规则
- 任何 FAIL 必须 evidence_required=true 且 Evidence 可用；否则降级 UNCERTAIN
- 风控/不可达：SiteRun partial，对相关 RuleResult 输出 UNCERTAIN（附 failure_reason 与最后截图）
- NOT-ASSESSABLE：不扣分，但在报告中输出“需材料/台账”清单与建议

## 4. RulePack 导入最简形式（推荐）
- rulepack.json（元信息：名称/版本/适用范围/生成来源）
- rules.json（规则数组）
- 可选：rules.csv / rules.yaml（便于人工编辑）
