# 指标编辑转化器（Rule Authoring & Converter）设计（v0.1）

## 1. 目标
将“原始指标（Excel/PDF提取文本/手工条款）”转换为平台可导入的 RulePack，并支持 AI 辅助归类：

- 拆分为“原子规则项”（按 1/2/3…）
- 生成 rules.json / rules.yaml / rules.csv + rulepack.json
- 内置校验器（validator），阻止坏规则进入库
- 引入 AI：对“归类/要素/关键词/页面类型”给出建议；**AI 不输出最终 PASS/FAIL**

## 2. 两层转化
### Layer A：确定性转换（必须，无需AI）
- 生成 rule_id、item_no、保留原文 text
- 解析 score / 扣分表达（解析失败则保留原文并标记需人工）
- 默认 schedule、evidence_required、automation_level
- 生成可导入的 rules.json（草案）

### Layer B：AI 建议（可选）
AI 的职责：
- suggested_class（1~4）+ confidence
- suggested_locator_keywords（便于定位页面）
- suggested_required_elements（仅 Class 3）
- suggested_not_assessable_reason（仅 Class 4）

**注意：**AI 建议写入 suggestions 字段，必须人工确认后再“固化”为正式字段（至少在早期）。

## 3. AI 调用与提示词（可直接实现）
### 3.1 强约束
- prompt_version 固定（如 authoring_v1）
- temperature=0
- 仅输出 JSON，必须通过 schema 校验
- 失败则降级为“无建议”（不阻塞转化）

### 3.2 用户提示（user）模板
```json
{
  "task": "classify_and_suggest_rule",
  "rule_text": "<原始指标条款原文>",
  "context": {
    "region": "<地区，如宿迁>",
    "scope": "<部门/区县/市级>",
    "known_page_types": ["公开指南","机构信息","政策文件","政策解读","依申请公开","预决算公开","政府信息公开年报"]
  },
  "constraints": {
    "classes": {
      "1":"有无/结构/字段",
      "2":"发现/定位/抽样/时效",
      "3":"质量/要素",
      "4":"网站端不可判断"
    },
    "output_must_be_json": true
  }
}
```

### 3.3 期望输出 JSON（schema）
```json
{
  "prompt_version": "authoring_v1",
  "suggested_class": 1,
  "confidence": 0.0,
  "suggested_check_type": "presence_or_timeliness",
  "suggested_locator_keywords": ["..."],
  "suggested_required_elements": [],
  "suggested_not_assessable_reason": ""
}
```

## 4. 最简导入方式（平台侧必须支持）
- 转化器输出目录包含：
  - rulepack.json
  - rules.json（主）
  - rules.csv（审阅）
- 平台提供导入命令（CLI 或 API）：
  - `import_rulepack --path rulepacks/<pack>/`
- 导入前强制运行校验器：
  - rule_id 唯一、必填字段齐全
  - class=4 时 evidence_required=false 且 automation_level=MANUAL
  - cap/mutex 字段合法

## 5. 校验器最低要求
- JSON Schema 校验
- 逻辑校验：rule_id 唯一、score 合法、schedule 合法、字段一致性、封顶/互斥配置合法
- 输出：错误列表（可定位到行/条目）

## 6. 实施节奏建议
- 先做 **CLI 转化器 + 校验器**（不拖慢主线）
- Web 编辑器二期再做（需要权限、表单、预览，容易拖进度）
