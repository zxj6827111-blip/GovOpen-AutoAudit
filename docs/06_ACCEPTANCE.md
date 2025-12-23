# 验收清单（Acceptance Checklist v0.2）

## A. 最小闭环（必须全通过）
- [ ] 能导入站点库（至少 1 个站点）
- [ ] 能导入 RulePack（至少 1 条规则）
- [ ] 能创建 BatchRun 并执行
- [ ] 任务能结束（done/partial/failed），不会卡死
- [ ] 生成导出包：summary/issues/failures + evidence.zip

## B. 证据与判定
- [ ] 每条 FAIL 在 issues 中有：URL + 截图路径（或快照路径）
- [ ] evidence.zip 解压后可按批次/站点/规则定位证据
- [ ] 无证据时不允许扣分（FAIL→UNCERTAIN）

## C. 风控
- [ ] 403/429/验证码触发后：SiteRun=partial，failures 记录原因与最后截图
- [ ] 并发与限速参数可配置且有效
- [ ] 输出访问轨迹 trace，可复盘抽样范围

## D. 可扩展性
- [ ] 可新增第二个 RulePack 并可被选择运行
- [ ] 运行结果绑定 rule_pack_version，可追溯
- [ ] RuleSpec 校验器能阻止坏规则进入库（rule_id重复、字段缺失、封顶配置非法等）
