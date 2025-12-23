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
- autoaudit/：平台服务端与 worker（任务/执行/规则引擎/导出）
- runs/：批次运行输出（trace/证据/报告）

## 平台 CLI 最小闭环
1. 启动沙箱靶场 + 跑最小回归脚本：
   ```bash
   python -m autoaudit.cli regression
   ```
   输出 summary/issues/failures 与 evidence.zip 会存放在 `runs/` 下。
2. 单独执行各步骤：
   ```bash
   # 规则包校验与导入（遵守 docs/10_INTERFACE_FREEZE.md 幂等要求）
   python -m autoaudit.cli validate_rulepack rulepacks/sandbox_mvp
   python -m autoaudit.cli import_rulepack rulepacks/sandbox_mvp

   # 导入站点库
   python -m autoaudit.cli import_sites sandbox/sites.json

   # 运行批次任务
   python -m autoaudit.cli run_batch rulepacks/sandbox_mvp
   ```
