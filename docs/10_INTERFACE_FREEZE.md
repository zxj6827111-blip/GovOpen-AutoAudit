# 接口冻结清单（Interface Freeze）v0.1

> 目的：让 **Platform MVP** 与 **Authoring CLI + Validator** 能并行开发、互不冲突。  
> 规则：本文件列出的“冻结项”在 M1/M2 阶段不得随意变更；如需变更，必须走 **变更流程**（见第 9 节），并同步两条研发线。

---

## 1. 冻结范围
冻结对象仅包含两条研发线的“契约层”：
- RulePack 文件结构与目录约定
- Rule JSON 的最小字段集合与语义
- Validator 的强制检查项与错误输出格式
- Platform 的导入接口（import）与幂等语义
- AI 建议（suggestions）的写入规则与兼容性
- 版本号策略与向后兼容策略

不冻结（允许各自演进）：
- Platform 内部数据库表结构（只要不破坏 import 行为）
- Worker 的采集实现细节（浏览器自动化策略、等待逻辑等）
- 报告导出格式的“附加字段”（只要保留核心字段）

---

## 2. RulePack 目录与文件结构（冻结）
一个 RulePack 必须是一个目录，最小包含：

```
rulepacks/<rule_pack_id>/
  rulepack.json
  rules.json
```

推荐附带（可选，不得作为导入必需）：
```
  rules.csv
  rules.yaml
  summary_by_indicator.csv
```

### 2.1 编码与文件格式（冻结）
- 文本编码：UTF-8（无 BOM）
- JSON：标准 JSON（不允许 JSON5 注释）
- CSV：UTF-8，逗号分隔，首行表头

### 2.2 rulepack.json（冻结字段）
必须字段：
- rule_pack_id（string，目录名必须与之相同）
- name（string）
- region_tag（string）
- scope（string：部门/区县/市级等）
- version（string：如 v1.0）
- schema_version（string：如 rule_spec_v0_2）
- generated_from（string：来源描述）
- generated_at（ISO datetime string）

可选字段：
- notes（string）
- owner（string）
- tags（array）

---

## 3. rules.json（冻结：最小字段集合）
rules.json 是数组，每个元素为一个 Rule（原子规则项）。

### 3.1 Rule 最小字段（必须）
以下字段缺失即 Validator 报错，Platform 不得导入：

- rule_id（string，RulePack 内唯一）
- section（string）
- indicator（string）
- item_no（string 或 number）
- text（string，原文条款）
- class（number：1/2/3/4）
- check_type（string：presence_or_timeliness | discovery | quality_elements | not_assessable）
- schedule（string：ANNUAL | QUARTERLY | MONTHLY | WEEKLY）
- score（number：扣分/得分，允许 0）
- evidence_required（boolean）
- allow_ai_assist（boolean）
- automation_level（string：FULL | PARTIAL | MANUAL）
- severity（string：info | warn | penalty | critical）
- locator（object，允许为空对象 `{}`）
- extractor（object，允许为空对象 `{}`）
- evaluator（object，允许为空对象 `{}`)

> 说明：locator/extractor/evaluator 允许先空，保证 M1 能跑通“导入→执行→导出”闭环；但 **class=1/2** 的规则在进入规模化前必须逐步补齐 evaluator。

### 3.2 治理字段（可选但保留字段名，冻结命名）
以下字段允许缺失或为空，但字段名与语义冻结，后续扩展不得改名：
- mutex_group（string|null）
- cap_group（string|null）
- max_penalty_in_group（number|null）
- output_hints（object|null）
- suggestions（object|null）  ← AI 建议只允许写在这里（见第 6 节）

---

## 4. 字段语义冻结（最易冲突的点）
### 4.1 class 与 evidence_required 的强一致性
- class ∈ {1,2,3} → evidence_required **必须为 true**
- class = 4 → evidence_required **必须为 false**，automation_level **必须为 MANUAL**

### 4.2 AI 的角色冻结
- AI 永远不输出最终 PASS/FAIL
- AI 输出只能落到 `suggestions`，不得覆盖正式字段（除非走“人工确认固化流程”，见第 6.3）

### 4.3 保守判定冻结
- 无证据不得 FAIL（FAIL→UNCERTAIN）
- 不可访问/风控触发：相关规则输出 UNCERTAIN（带原因），不得推断 FAIL

---

## 5. Validator（冻结：强制校验项与输出格式）
### 5.1 强制校验项（冻结）
Validator 必须至少校验：
1) rule_pack_id 与目录名一致
2) schema_version 存在且合法
3) rules.json 为数组且非空（允许在“空包占位”场景下提供 `--allow-empty`）
4) rule_id 在 RulePack 内唯一
5) Rule 最小字段齐全（见第 3 节）
6) class、check_type、schedule 取值合法
7) class=4 一致性（evidence_required=false 且 automation_level=MANUAL）
8) score 为数字（允许 0），不得为 NaN/字符串
9) mutex/cap 逻辑合法（如 max_penalty_in_group 与 cap_group 的一致性）

### 5.2 Validator 输出格式（冻结）
Validator 输出必须是 JSON（便于 CI/平台消费）：
```json
{
  "ok": false,
  "schema_version": "rule_spec_v0_2",
  "errors": [
    {"code":"RULE_ID_DUPLICATE","path":"rules[12].rule_id","message":"..."},
    {"code":"MISSING_FIELD","path":"rules[3].schedule","message":"..."}
  ],
  "warnings": [
    {"code":"EVALUATOR_EMPTY","path":"rules[8].evaluator","message":"..."}
  ]
}
```
- errors：导入必须失败
- warnings：允许导入，但应在报告/日志中提示

---

## 6. AI 建议（suggestions）冻结
### 6.1 suggestions 的结构（冻结字段名）
```json
"suggestions": {
  "prompt_version": "authoring_v1",
  "suggested_class": 2,
  "confidence": 0.73,
  "suggested_check_type": "discovery",
  "suggested_locator_keywords": ["公开指南","政府信息公开指南"],
  "suggested_required_elements": [],
  "suggested_not_assessable_reason": ""
}
```

### 6.2 AI 调用约束（冻结）
- temperature = 0
- 输出必须严格 JSON，必须通过 schema 校验
- AI 失败：suggestions 置空或缺失，不得阻塞 convert/validate

### 6.3 “人工确认固化”流程（冻结原则）
只有在人工确认后，才允许把 suggestions 的某些字段写回正式字段：
- suggested_class → class
- suggested_locator_keywords → locator.keywords（示例）
任何自动固化必须：
- 记录 confirmed_by / confirmed_at（可写入 output_hints 或单独审计文件）
- 保存变更前后的 diff（建议在 Git 里完成）

---

## 7. Platform 导入接口（import_rulepack）冻结
### 7.1 最小导入能力（冻结）
Platform 必须提供导入入口（CLI 或 API 任选其一，建议两者最终都提供）：
- CLI：`platform import_rulepack --path rulepacks/<pack>/`
或
- API：`POST /api/rulepacks/import`（multipart 或 path 引用）

### 7.2 导入顺序冻结
- 导入前必须执行 Validator（Platform 内部调用或外部先跑均可）
- Validator errors ≠ 0 → 导入失败
- 导入成功后生成：rule_pack_id + version + schema_version 的入库记录

### 7.3 幂等语义冻结
同一个 RulePack（rule_pack_id + version）重复导入：
- 默认应 **幂等**：若内容 hash 相同 → 返回“已存在”
- 若内容 hash 不同 → 视为冲突，拒绝导入（提示应升级 version）

---

## 8. 版本策略与向后兼容（冻结）
### 8.1 schema_version
- 规则结构版本由 schema_version 标识，例如：rule_spec_v0_2
- 任何破坏字段语义/结构的变更必须升级 schema_version

### 8.2 version（RulePack 版本）
- 同 rule_pack_id 下，version 必须单调递增（v1.0 → v1.1 → v2.0）
- 不允许“同版本覆盖不同内容”（避免结果不可复现）

### 8.3 兼容原则
- Platform 至少支持当前 schema_version 与前一个 schema_version（N 与 N-1）
- 不兼容时明确报错：UNSUPPORTED_SCHEMA_VERSION

---

## 9. 变更流程（冻结）
任何冻结项变更必须：
1) 修改 docs/10_INTERFACE_FREEZE.md（本文件）并升小版本（v0.1→v0.2）
2) 同步修改 docs/03_RULE_SPEC.md 或 docs/08_RULE_AUTHORING.md（如涉及字段/AI）
3) 在同一 PR 中更新：
   - validator（适配新 schema）
   - platform import（兼容新 schema 或明确拒绝）
4) 增加至少 1 个 sandbox 用例或回放 fixture 覆盖该变更

---

## 10. 最小示例（冻结：用于对齐）
### 10.1 rulepack.json 示例
```json
{
  "rule_pack_id": "suqian_dept_v1",
  "name": "2026年宿迁市政务公开监测指标（部门）v1.0",
  "region_tag": "宿迁",
  "scope": "部门",
  "version": "v1.0",
  "schema_version": "rule_spec_v0_2",
  "generated_from": "2_2026年宿迁市政务公开监测指标（部门）v1.0(2).xls",
  "generated_at": "2025-12-23T00:00:00",
  "notes": "converted by authoring cli"
}
```

### 10.2 单条 rule 示例（rules.json 内元素）
```json
{
  "rule_id": "suqian-制度公开-1",
  "section": "一、主动公开",
  "indicator": "制度公开",
  "item_no": "1",
  "text": "全面公开部门权力配置情况，依法公开职责职能、机构设置、办公地址、办公时间、联系方式、负责人姓名等信息，未公开的，扣0.2分。",
  "class": 1,
  "check_type": "presence_or_timeliness",
  "schedule": "MONTHLY",
  "score": -0.2,
  "evidence_required": true,
  "allow_ai_assist": false,
  "automation_level": "FULL",
  "severity": "penalty",
  "locator": {"keywords":["机构设置","联系方式","负责人"]},
  "extractor": {"fields":["office_address","office_hours","phone","leader_name"]},
  "evaluator": {"type":"presence_all","required_fields":["phone","leader_name"]},
  "mutex_group": null,
  "cap_group": null,
  "max_penalty_in_group": null,
  "suggestions": null
}
```

---

## 11. 执行建议（非冻结，供操作）
- 两条 Codex 任务并行推进：
  - Platform 先实现 `validate→import→run→export` 最小闭环
  - Authoring 先实现 `convert→ai-suggest→validate→export` 并输出可导入目录
- Antigravity 作为验收与修正：专盯“冻结项是否被破坏”、以及 M1 闭环是否满足 docs/06 验收清单

