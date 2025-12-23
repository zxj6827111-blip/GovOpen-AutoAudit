# 开发交接提示词（Codex → Antigravity）

## 1) 给 Codex（新任务：搭平台骨架 + 预留转化器接口）
建议：开新任务（独立上下文）  
目标：实现 M1 最小闭环（1站点+1规则→跑批次→导出证据包）

### Codex 提示词（可复制）
你现在是全栈工程负责人。请在一个新任务中为“政务公开自动评估平台 GovOpen-AutoAudit（Platform MVP）”搭建最小骨架：
- 多 RulePack（每地一库）、站点库、批次任务、worker（浏览器抽样访问）、规则引擎（四态输出）、证据存储、导出（summary/issues/failures + evidence.zip）
- 不做全量点击，仅抽样，触发式加深，单站点上限
- 风控触发（403/429/验证码）必须降级并输出 failures，不得卡死
- FAIL 必须有证据，否则降级 UNCERTAIN
- 预留 AI Assist 接口（不启用），AI 仅输出结构化证据，不输出结论
- 增加访问轨迹 trace（用于回放与解释抽样范围）
- 同仓库内预留 authoring/ 转化器目录与导入接口（import_rulepack）

产出：
A) 目录结构与启动命令
B) SQLite 数据模型与迁移
C) 任务队列（MVP可进程内）
D) 可控测试靶场 sandbox（至少8场景）
E) 最小验收脚本：导入→执行→导出

## 2) 给 Antigravity（继续同任务：本地化测试+加固+文档对齐）
建议：继续 Codex 任务上下文（避免重复）  
目标：本地可跑 + 测试加固 + 规则导入与校验器完善

### Antigravity 提示词（可复制）
请在已有代码基础上继续（不要新开项目）：
1) 稳定化 sandbox：覆盖 PASS/FAIL/UNCERTAIN/NOT-ASSESSABLE/403/429/分页
2) 补齐 validator：阻止坏规则进入库；导入前强制校验
3) 强化导出包结构：issues 中每条 FAIL 可追溯到 evidence.zip
4) 风控触发后任务应 partial 并输出 failures，不得卡死
5) 抽样/并发/限速参数化并提供默认值
6) 文档对齐：实现不得违背 docs 约束

交付标准：
- 本地一键跑通 M1 闭环
- 回归测试可重复
