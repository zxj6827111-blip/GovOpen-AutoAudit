# GovOpen-AutoAudit

政务公开自动评估平台（Platform MVP）：规则驱动 + 证据导向 + AI 辅助。

## 快速开始（Pilot-ready 一键启动）
```bash
# 1. 配置环境
cp .env.example .env

# 2. 启动服务 (API + UI)
docker-compose up -d

# 3. 跑一次试点 (Import -> Run -> Report)
python scripts/run_pilot.py --rulepack rulepacks/region_demo_1 --sites sandbox/sites.json
```

## 文档索引
- docs/00_PROJECT_CHARTER.md（项目边界与目标）
- docs/01_ARCHITECTURE.md（平台最小骨架）
- docs/03_RULE_SPEC.md（规则表达规范）
- docs/08_RULE_AUTHORING.md（指标编辑转化器）
- docs/09_HANDOFF_PROMPTS.md（交接提示词）
- [walkthrough.md](./walkthrough.md)（功能演示与验收）

## 仓库结构
- docs/：项目约束文档
- rulepacks/：各地指标库
- authoring/：指标编辑转化器
- sandbox/：可控测试靶场
- platform/：平台服务端
- scripts/：运维与测试脚本

## 开发者指南
- 运行验收测试：`python scripts/contract_acceptance_test.py`
- 运行 UI Smoke Test：`python scripts/ui_smoke_test.py`
