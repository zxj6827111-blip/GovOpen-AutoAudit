# 执行策略：抽样、并发与风控（Execution Policy v0.2）

## 1. 抽样参数（默认建议）
- per_list_recent_n：3
- per_list_random_m：2
- max_lists_per_site：10
- max_content_pages_per_site：30
- max_depth：3（入口→栏目→列表→内容）
- trigger_deepen_on：发现异常（字段缺失/超期/栏目不可达）时，额外 +1~3 个样本

## 2. 并发与限速（默认建议）
- max_concurrency：3（先保守）
- per_domain_delay_sec：2~5（同域名访问间隔）
- backoff：指数退避（429/503）
- night_run_window：建议夜间批次优先

## 3. 风控降级（禁止对抗）
- 识别信号：403/429、验证码关键词、异常跳转、反爬提示
- 策略：停止加深 → 记录 failure_reason → 保留最后截图 → SiteRun=partial
- 输出：failures 表必须包含站点、原因、最后 URL、截图路径、尝试次数

## 4. 失败分类（标准化）
- blocked_403
- rate_limited_429
- captcha_detected
- timeout
- parse_error
- navigation_failed

## 5. 访问轨迹（必须）
- 每个 SiteRun 输出 trace：步骤序列、URL、耗时、状态码、截图/快照引用
- 轨迹用于：复盘、回放、回归、对外解释抽样范围
