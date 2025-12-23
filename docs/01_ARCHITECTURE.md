# 架构设计（Platform MVP v0.2）

## 1. 模块总览
- **Admin Console（后台管理）**：站点库、指标库、任务创建、结果下载（可先 API + 简易页面）。
- **Job Scheduler（调度）**：并发控制、限速、夜跑窗口、重试与降级策略。
- **Browser Worker（执行器）**：浏览器自动化（抽样访问），采集 DOM/截图/快照/访问轨迹。
- **Rule Engine（规则引擎）**：执行规则、生成四态结果、计分与证据绑定、封顶/互斥（逐步实现）。
- **AI Assist（可插拔）**：仅做页面分类/要素抽取/证据句定位（不输出最终判定）。
- **Evidence Store（证据与快照）**：按批次/站点/规则组织证据，支持复用。
- **Report Export（交付导出）**：summary/issues/failures + evidence.zip。
- **Rule Authoring（指标编辑转化器）**：将原始指标条款转为可导入规则；可选 AI 辅助归类与建议；内置校验器。

## 2. 数据流（高层）
1) 导入站点库、导入 RulePack（或用转化器生成后导入）
2) 创建 BatchRun（选站点 + 选 RulePack + 参数）
3) Scheduler 派发 SiteRun
4) Worker 抽样访问并采集材料（DOM/截图/快照/轨迹）
5) Rule Engine 执行规则 → RuleResult（四态）+ Evidence（可复用）
6) Export 生成交付包（表格 + 证据压缩包）

## 3. 访问策略（MVP 默认）
- 每站点必访问：入口页
- 发现路径：栏目/列表页（最多 K 个）
- 内容页抽样：最近 N + 随机 M（可配置）
- 触发式加深：仅当规则需要更多证据时，增加少量样本
- 单站点内容页总上限 X（可配置），防止任务失控

## 4. 不确定性与保守输出
- 页面不可达/风控触发：SiteRun=partial；相关规则结果输出 UNCERTAIN（附失败原因与最后证据）。
- 证据不足：不得扣分，FAIL→UNCERTAIN。
