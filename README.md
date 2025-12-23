# GovOpen-AutoAudit

政务公开自动评估平台（Platform MVP）：规则驱动 + 证据导向 + AI 辅助。

## 快速开始（先读文档）
- docs/00_PROJECT_CHARTER.md（项目边界与目标）
- docs/01_ARCHITECTURE.md（平台最小骨架）
- docs/03_RULE_SPEC.md（规则表达规范）
- docs/08_RULE_AUTHORING.md（指标编辑转化器：含AI建议提示词）
- docs/09_HANDOFF_PROMPTS.md（Codex/Antigravity 交接提示词）

## 仓库结构（建议）
- docs/：项目约束文档（本仓库的“北极星”）
- rulepacks/：各地指标库（每地一库）
- authoring/：指标编辑转化器（CLI优先）
- sandbox/：可控测试靶场（网页模拟器）
- platform/：平台服务端与 worker（任务/执行/规则引擎/导出）

## Authoring CLI（MVP）
在仓库根目录下执行，提供四个子命令：

- `python -m authoring.cli convert <input> <rule_pack_id> <name> <region_tag> <scope> <version> <generated_from> [output_root]`：从 Excel/文本拆分原子规则，生成 `rulepacks/<rule_pack_id>/rulepack.json` 与 `rules.json`。
- `python -m authoring.cli ai-suggest <rulepack_dir>`：为规则附加 AI 建议（仅写入 `suggestions` 字段，失败降级为空）。
- `python -m authoring.cli validate <rulepack_dir>`：按 docs/10_INTERFACE_FREEZE.md 冻结约束输出 JSON 校验结果。
- `python -m authoring.cli export <rulepack_dir> [--formats json csv yaml]`：导出多格式（YAML 需本地安装 pyyaml）。
- `python -m authoring.cli build <workdir> <final_output>`：将工作目录构建为最终可发布 RulePack（P1 新增）。

### P1 快速复现流程
```bash
# 1. 转换并构建示例
python -m authoring.cli convert authoring/examples/region_demo_1.json region_demo_1 "Region Demo 1" "North" "City" v1.0 "manual" sandbox
python -m authoring.cli build sandbox/region_demo_1 rulepacks/region_demo_1

# 2. 校验 (Validation)
python -m authoring.cli validate rulepacks/region_demo_1

# 3. 平台导入 (Import)
python -m autoaudit.cli import_rulepack rulepacks/region_demo_1
```
