# 政务公开自动评估平台 - 总体技术架构与交付计划

> **版本**: v1.1 (修订版)  
> **日期**: 2024-12-24 (定稿)  
> **作者**: Architecture Team  
> **状态**: Revised for Review

---

## Changelog（v1.0 → v1.1 修订摘要）

1. **删除反爬对抗措施**：移除User-Agent伪装、代理池、`--disable-blink-features=AutomationControlled`等内容，改为"限速+并发控制+检测即停止"
2. **修正failure降级策略**：从"一次失败全站UNCERTAIN"改为"按作用域降级"（仅影响依赖该页面集的规则）
3. **调整Playwright定位**：从"默认主路径"改为"双通道架构"（requests主路径 + Playwright按需触发）
4. **统一证据对象schema**：定义最小字段集合（evidence_id, type, url, timestamp, locator, text_quote, file_path, content_hash）
5. **替换不可控验收标准**：删除"通过率>50%"，改为"FAIL证据完整率100% + coverage指标可度量"
6. **修正M0/M1计划**：保留requests方案作为主路径，提升content_paths优先级到P0

---

## A. 总体架构

### A.1 架构图（文字版）

```
┌─────────────────────────────────────────────────────────────────┐
│                      管理与交付层 (Admin & Export)                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ 批次管理 │  │ 站点管理 │  │ 规则导入 │  │ 报告导出 │         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
└───────┼────────────┼────────────┼────────────┼──────────────────┘
        │            │            │            │
┌───────▼────────────▼────────────▼────────────▼──────────────────┐
│                    调度与编排层 (Orchestration)                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Job Scheduler (队列管理、并发控制、重跑、夜跑窗口)         │   │
│  └────────────────────┬─────────────────────────────────────┘   │
└────────────────────────┼───────────────────────────────────────┘
                         │
        ┌────────────────┴─────────────────┐
        │                                  │
┌───────▼────────┐                ┌───────▼────────┐
│  采样抓取层     │                │  规则引擎层     │
│ (Crawler)      │◄──────────────►│ (Rule Engine)  │
│ 双通道架构:    │                │                │
│ • 静态HTTP主   │                │                │
│ • Playwright辅 │                │                │
└───────┬────────┘                └───────┬────────┘
        │                                  │
        │  ┌───────────────────┐          │
        ├─►│ Static Worker     │          │
        │  │ (requests主路径)  │          │
        │  └───────────────────┘          │
        │  ┌───────────────────┐          │
        └─►│ Playwright Worker │          │
           │ (按需触发)        │          │
           │ - JS渲染          │          │
           │ - 截图+快照       │          │
           │ - 红框标注(FAIL)  │          │
           └───────┬───────────┘          │
                   │                      │
        ┌──────────▼──────────┐  ┌────────▼─────────┐
        │   证据与可追溯层    │  │  AI辅助层(可选)  │
        │ (Evidence Store)   │  │ - 页面分类       │
        │ - 统一Evidence对象 │  │ - 要素抽取       │
        │ - URL/时间戳       │  │ - 证据句定位     │
        │ - Rule绑定         │  │ - 规则建议       │
        └──────────┬──────────┘  └────────┬─────────┘
                   │                      │
        ┌──────────▼──────────────────────▼─────────┐
        │          存储与观测层 (Storage)            │
        │  ┌──────────┐ ┌──────────┐ ┌──────────┐  │
        │  │  SQLite  │ │ 文件存储 │ │  日志    │  │
        │  │ (元数据) │ │(Evidence)│ │ (观测)   │  │
        │  └──────────┘ └──────────┘ └──────────┘  │
        └────────────────────────────────────────────┘
```

### A.2 模块说明

#### 1. **采样抓取层 (Crawler/Frontier)**
- **职责**: 根据抽样策略访问目标站点，采集DOM内容、截图、HTML快照
- **核心组件**: 
  - `PlaywrightBrowserWorker`: 真实浏览器自动化（Chromium Headless）
  - `SamplingStrategy`: 抽样策略控制（最近N+随机M+优先级队列）
  - `FrontierQueue`: URL优先级队列（entry_points → content_paths提权）
- **输出**: `FetchResult`列表（URL、status_code、body、screenshot、snapshot）

#### 2. **解析抽取层 (DOM + Text)**
- **职责**: 从HTML快照中提取文本、定位元素、执行规则匹配
- **核心组件**:
  - **统一接口**: 提供统一的DOM查询接口
  - **静态路径**: 使用HTML parser (BeautifulSoup/lxml) 解析requests获取的HTML
  - **渲染路径**: 使用Playwright DOM API解析浏览器渲染后的DOM
  - **输出标准化**: 两种路径最终都输出同一份PageDocument结构供RuleEngine使用
  - CSS选择器/XPath定位器（基于Rule.locator）
- **输出**: 结构化PageDocument（url, body_text, dom_snapshot, selectors）

#### 3. **规则引擎层 (Rule Engine)**
- **职责**: 执行RulePack规则，输出四态结果（PASS/FAIL/UNCERTAIN/NOT-ASSESSABLE）
- **核心逻辑**:
  - **定位阶段** (`_locate_pages`): 根据locator筛选相关页面
  - **评估阶段** (`_evaluate_content`): 根据evaluator判定PASS/FAIL
  - **证据绑定**: FAIL必须有evidence，否则自动降级UNCERTAIN
  - **风控降级**: 检测到captcha/403/429 → 按作用域影响相关规则输出UNCERTAIN（相关规则判定口径见B.2：依赖页面集 ∩ affected_page_scope ≠ 空集）
- **输出**: `RuleResult[]`（rule_id、status、score_delta、reason、evidence_ids、highlight_hints）

#### 4. **证据与可追溯层 (Evidence Store)**
- **职责**: 存储所有证据并保证可追溯性
- **存储结构**:
  ```
  runs/
    batch_{id}/
      metadata.json (rule_pack_id, version, timestamp, ai_config)
      site_{id}/
        trace.json (访问轨迹)
        screenshot_*.jpg (红框标注截图，仅FAIL)
        snapshot_*.html (HTML快照)
      export/
        summary.json
        issues.json
        failures.json
        evidence.zip
  ```
- **可追溯字段**: 每个RuleResult绑定{rule_pack_id, rule_pack_version, schema_version, ai_provider, ai_model, prompt_version}

#### 5. **AI辅助层 (AI Assist, 可选)**
- **职责**: 仅做辅助建议，不输出最终判定
- **使用场景**:
  - Class 3规则: 要素抽取（联系人、电话、日期）
  - 页面分类: 判断页面类型（入口/列表/内容）
  - 证据句定位: 从长文本中抽取关键句
  - 规则归类建议: 辅助指标编辑转化器
- **约束**:
  - AI输出必须落库（原始JSON或摘要）
  - 每次AI调用记录{provider, model, prompt_version, latency, input_tokens, output_tokens}
  - AI结果不直接映射为PASS/FAIL，仅供rule_engine参考
- **降级策略**: AI超时/失败 → 规则降级UNCERTAIN（不卡死任务）

#### 6. **导出与报表层 (Export)**
- **职责**: 生成可交付报告（JSON、Markdown、CSV）
- **交付物**:
  - `summary.json`: 批次汇总、覆盖率、通过率、失败统计
  - `issues.json`: 所有FAIL规则明细（rule_id、site_id、score_delta、reason、evidence_urls）
  - `failures.json`: 风控失败记录（captcha、403、timeout等）
  - `evidence.zip`: 所有截图+快照打包
  - `report.md`: 人类可读摘要（可选）
- **API接口**:
  - `GET /runs/{batch_id}/status` → 批次状态
  - `GET /runs/{batch_id}/export/summary` → 下载summary.json
  - `POST /export/report` → 生成Markdown报告

#### 7. **调度与编排层 (Orchestration)**
- **职责**: 管理批次任务、并发控制、队列调度
- **核心功能**:
  - 批次创建: 选择RulePack + Sites → 生成BatchRun
  - 并发控制: 使用`asyncio.Semaphore(2)` 控制同时2个浏览器实例
  - 夜跑窗口: 定时调度（可选）
  - 重跑机制: 标记失败站点 → 手动重跑
- **队列状态**: queued → running → done/partial/failed

#### 8. **存储与观测层 (Storage & Observability)**
- **存储方案**:
  - **元数据**: SQLite（RulePacks、Sites、Runs、RuleResults）
  - **证据文件**: 本地文件系统（runs/目录）
  - **日志**: 结构化日志（JSON Lines格式）
- **观测指标**:
  - 批次运行时长、站点覆盖率、规则命中率
  - 风控触发次数（captcha/403/429统计）
  - 浏览器资源占用（内存、CPU）
  - AI调用延迟与token消耗

### A.3 数据流

```
1. 创建Run:
   User → Admin API → BatchRunner.create(rulepack_id, site_ids, sampling_config)
   
2. 执行Run:
   Scheduler → 派发SiteRun → PlaywrightWorker.run_site(site, sampling)
   
3. 采样抓取:
   Worker → 访问entry_points → 提取content_paths → 抽样访问(最近N+随机M)
   Worker → 每个URL生成FetchResult(body, screenshot, snapshot) → 保存到runs/
   
4. 规则评估:
   RuleEngine.evaluate(pages, rules) → 遍历每条规则:
     - 定位页面: _locate_pages(locator) → 筛选匹配页面
     - 评估内容: _evaluate_content(evaluator) → 输出PASS/FAIL
     - 证据检查: 如果FAIL且无evidence → 降级UNCERTAIN
     - 风控检查: 如果failures存在 → 降级UNCERTAIN
   → 输出RuleResult[]
   
5. AI辅助(可选):
   RuleEngine → 检测到Class 3规则 → 调用AIAssistant.extract_elements(html)
   → AI返回JSON(抽取字段) → rule_engine使用结果继续判定
   → 记录AiInvocation(provider, model, latency, input/output)
   
6. 证据归档:
   Export.generate_deliverables(batch_id) → 
     - 汇总所有RuleResults → summary.json
     - 筛选FAIL → issues.json
     - 筛选风控失败 → failures.json
     - 打包截图+快照 → evidence.zip
   
7. 可追溯性:
   任意RuleResult → 查询关联:
     - rule_pack_id + version
     - ai_provider + model + prompt_version (if applicable)
     - evidence_files (screenshot_X.jpg, snapshot_X.html)
     - trace.json (完整访问轨迹)
```

---

## B. 关键设计决策

### B.1 抽样策略（Sampling Strategy）

#### **同域限深策略**
- **最大深度**: 3层（entry → category → list → content）
- **单站点内容页上限**: 30页（防失控）
- **同域访问间隔**: 2-5秒礼貌延迟（降低站点压力）

#### **content_paths提权机制**
**问题**: 如何确保关键栏目被优先抓取？

**方案**:
1. **手工标注优先级** (推荐MVP):
   ```json
   {
     "site_id": "suqian_gov",
     "entry_points": [...],
     "content_paths": [
       {"url": "...", "priority": 10, "tags": ["政府信息公开指南"]},
       {"url": "...", "priority": 5, "tags": ["年度报告"]}
     ]
   }
   ```
   - priority高的URL先访问
   - 如果某rule需要特定tag，优先抓取该tag的content_paths

2. **栏目预算切分** (高级):
   - 定义栏目分类（如"主动公开"、"依申请公开"）
   - 每个分类分配抽样配额（如主动公开15页，依申请5页）
   - 避免某一栏目占满所有配额

#### **触发式加深 (Adaptive Deepening)**
- **触发条件**:
  - 规则要求字段但所有页面均未找到
  - 发现时效性异常（如年度报告但只有2020年）
  - 栏目链接404（需验证是否整个栏目不可达）
- **加深策略**:
  - 额外抽取1-3个样本
  - 从content_paths中随机选择未访问URL
  - 记录加深原因到trace.json

#### **抽样参数配置**
```python
DEFAULT_SAMPLING = {
    "per_list_recent_n": 3,        # 每个列表最近3条
    "per_list_random_m": 2,        # 随机2条
    "max_lists_per_site": 10,      # 最多10个列表页
    "max_content_pages_per_site": 30, # 内容页总上限
    "max_depth": 3,                # 最大深度
    "trigger_deepen_threshold": 0.3, # 命中率<30%时触发加深
    "priority_boost_factor": 2.0,  # 高优先级URL权重*2
}
```

### B.2 Failures Taxonomy（失败分类标准）

#### **标准化失败原因**
| 失败码 | 含义 | 默认作用域 | 记录字段 |
|-------|------|-----------|---------|
| `blocked_403` | 访问被拒绝（IP封禁） | 影响该URL及同路径规则 | url, screenshot, reason |
| `rate_limited_429` | 触发限流 | 影响该URL及同路径规则 | url, retry_after, screenshot |
| `captcha_detected` | 检测到验证码 | 影响该URL及同路径规则 | url, screenshot, captcha_type |
| `timeout` | 请求超时（30s） | 仅该URL | url, elapsed, last_state |
| `parse_error` | HTML解析失败 | 仅该URL | url, error_msg |
| `navigation_failed` | 页面无法加载 | 仅该URL | url, status_code, error |
| `robots_blocked` | robots.txt禁止 | 全站NOT-ASSESSABLE | url |
| `ssl_error` | 证书无效 | 影响该域名所有HTTPS页面 | url, cert_info |
| `redirect_loop` | 重定向循环 | 仅该URL | url, redirect_chain |

#### **failures.json格式**
```json
{
  "batch_id": "batch_abc123",
  "timestamp": "2024-12-24T10:00:00Z",
  "failures": [
    {
      "failure_id": "fail_001",
      "site_id": "suqian_gov",
      "failure_reason": "captcha_detected",
      "url": "https://www.suqian.gov.cn/budget/list.shtml",
      "affected_page_scope": ["https://www.suqian.gov.cn/budget/*"],  // 受影响的页面范围
      "screenshot": "runs/batch_abc123/site_suqian/error_0.jpg",
      "timestamp": "2024-12-24T10:05:23Z",
      "retry_count": 1,
      "metadata": {"captcha_type": "google_recaptcha"}
    }
  ]
}
```

#### **按作用域降级策略（修正版）**

**核心原则**: 不一刀切，按failure影响范围降级

**降级规则**:

1. **入口页不可达**（entry_points全部失败）:
   ```python
   if all(f["url"] in entry_points for f in failures):
       # 整个SiteRun标记为NOT-ASSESSABLE
       site_run_status = "NOT-ASSESSABLE"
       # 所有规则降级NOT-ASSESSABLE
       for rule in rules:
           result = {"status": "NOT-ASSESSABLE", "reason": "entry_unreachable"}
   ```

2. **部分页面失败**（非入口页）:
   ```python
   # 仅影响依赖该页面集的规则
   failed_urls = [f["url"] for f in failures]
   
   for rule in rules:
       required_pages = locate_pages(rule.locator, all_pages)
       available_pages = [p for p in required_pages if p.url not in failed_urls]
       
       if len(available_pages) == 0:
           # 规则所需的所有页面都失败 → UNCERTAIN
           result = {"status": "UNCERTAIN", "reason": "required_pages_unavailable"}
       elif len(available_pages) < min_sample_size:
           # 样本不足 → UNCERTAIN
           result = {"status": "UNCERTAIN", "reason": "insufficient_samples"}
       else:
           # 用可用页面继续评估
           result = evaluate_rule(rule, available_pages)
   ```

3. **单个URL失败**:
   ```python
   # 不影响其他规则，仅在trace.json中记录
   trace.append({
       "url": failed_url,
       "status": "failed",
       "reason": "timeout",
       "screenshot": "error_screenshot.jpg"
   })
   ```

**示例场景**:
- ❌ 错误: "检测到1次验证码 → 全站20条规则都UNCERTAIN"
- ✅ 正确: "预算栏目触发验证码 → 仅依赖预算栏目的3条规则UNCERTAIN，其他17条规则正常评估"

**"相关规则"判定口径**:
- 规则依赖页面集 = `locate_pages(rule.locator, all_pages)` 返回的URL集合
- 受影响规则 = 规则依赖页面集 ∩ `affected_page_scope` 非空的所有规则
- 仅当交集非空时，该规则才降级UNCERTAIN；否则不受影响

### B.3 证据对象标准（Evidence Schema）

#### **统一最小字段集合**
```json
{
  "evidence_id": "evd_20241224_001",
  "type": "text" | "screenshot" | "file",  // 推荐截图用screenshot
  "rule_id": "jiangsu_suqian_v1_1-budget-16",
  "site_id": "suqian_gov",
  "url": "https://www.suqian.gov.cn/...",
  "timestamp": "2024-12-24T10:15:32Z",
  
  // Locator字段（如何定位到证据）
  "locator": {
    "type": "selector" | "xpath" | "text_offset",
    "value": ".budget-section" | "//div[@class='budget']" | "offset:1234",
    "text_quote": "2023年财政预算公开"  // 可选：命中的文本片段
  },
  
  // 文件字段（如果type=screenshot或file）
  "file_path": "runs/batch_abc/site_suqian/screenshot_3.jpg",
  "file_size_bytes": 245678,
  "content_hash": "sha256:a3b2c1d4e5f6...",
  
  // 元数据（可选）
  "metadata": {
    "viewport": "1920x1080",
    "screenshot_quality": 85,
    "highlight_applied": true  // 推荐：用type=screenshot+此字段区分普通/标注截图
  }
}
```

**关键设计**:
- ✅ RuleResult只引用`evidence_id`，不直接存储文件路径
- ✅ Evidence对象与Rule解耦，可复用
- ✅ locator字段统一DOM定位、文本偏移、截图区域等多种类型

#### **证据复用机制**
```python
def get_or_create_evidence(url, rule, page_content):
    # 检查是否已有相同URL+locator的证据
    existing = find_evidence(url=url, locator=rule.locator)
    if existing:
        return existing.evidence_id  # 复用
    
    # 创建新证据
    evidence = create_evidence(
        type="screenshot" if rule.requires_screenshot else "text",
        url=url,
        locator=rule.locator,
        text_quote=extract_matched_text(page_content, rule.locator)
    )
    return evidence.evidence_id
```

#### **FAIL缺证据降级机制**
```python
def _fail(self, rule: Dict, page: Dict, reason: str, locator: Dict = None):
    # 尝试获取或创建证据
    evidence_id = get_or_create_evidence(page["url"], rule, page["body"])
    
    if not evidence_id:
        # 无法生成证据 → 自动降级UNCERTAIN
        logger.warning(f"Rule {rule['rule_id']} FAIL but no evidence, downgrading to UNCERTAIN")
        return self._uncertain(rule, reason="no_evidence_for_fail")
    
    # FAIL且有证据
    return {
        "rule_id": rule["rule_id"],
        "status": "FAIL",
        "score_delta": rule.get("score", 0),
        "reason": reason,
        "evidence_ids": [evidence_id],  # 统一使用evidence_id数组
    }
```

### B.4 双通道渲染策略（Static + Playwright）

#### **架构设计**

```
采样抓取层
    ├─► Static Worker (主路径)
    │   - 使用requests + BeautifulSoup
    │   - 适用于90%静态页面
    │   - 快速、资源占用低
    │
    └─► Playwright Worker (辅助路径，按需触发)
        - 真实浏览器渲染
        - 适用于需要JS的页面
        - 触发条件：静态抓取失败或内容为空
```

#### **Playwright触发条件**

```python
def should_use_playwright(static_result: FetchResult) -> bool:
    """判断是否需要启用Playwright"""
    
    # 条件1: 静态抓取body为空或过短
    if len(static_result.body) < 500:
        return True
    
    # 条件2: 检测到典型的JS渲染标记
    js_indicators = [
        '<div id="app"></div>',  # Vue/React应用
        'document.write',
        'window.__INITIAL_STATE__'
    ]
    if any(indicator in static_result.body for indicator in js_indicators):
        return True
    
    # 条件3: 关键节点缺失（基于Rule.locator）
    required_selectors = extract_selectors_from_rules(rules)
    soup = BeautifulSoup(static_result.body, 'html.parser')
    if not soup.select(required_selectors):
        return True
    
    return False  # 默认不启用Playwright
```

#### **双通道调用流程**

```python
async def fetch_with_fallback(url: str, rules: List[Dict]) -> FetchResult:
    """双通道抓取：静态优先，Playwright兜底"""
    
    # 1. 先尝试静态抓取
    static_result = static_worker.fetch(url)
    
    # 2. 判断是否需要Playwright
    if not should_use_playwright(static_result):
        return static_result  # 静态结果可用，直接返回
    
    # 3. 触发Playwright
    try:
        playwright_result = await playwright_worker.fetch(url)
        return playwright_result
    except PlaywrightError as e:
        # Playwright失败 → 降级回静态结果（附加warning）
        logger.warning(f"Playwright failed for {url}, falling back to static: {e}")
        static_result.metadata["playwright_fallback"] = str(e)
        return static_result  # 返回静态结果，不标记整个Run失败
```

#### **Playwright配置（无反检测措施）**

```python
# 合规配置：仅基础headless，不对抗反爬
browser = await playwright.chromium.launch(
    headless=True,
    args=[
        '--no-sandbox',  # Docker环境需要
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',  # 低内存环境
    ]
)

context = await browser.new_context(
    viewport={'width': 1920, 'height': 1080},
    locale='zh-CN',
    timezone_id='Asia/Shanghai',
    ignore_https_errors=True  # 政府站点证书常见问题
)
```

**删除的配置**（不使用）:
- ❌ `--disable-blink-features=AutomationControlled`（反检测）
- ❌ 自定义User-Agent伪装
- ❌ 代理池轮换
- ❌ Canvas/WebGL指纹随机化

#### **验证码处理（检测即停止）**

```python
async def detect_and_stop_on_captcha(page: Page, url: str) -> bool:
    """检测验证码，不尝试绕过"""
    captcha_keywords = ['验证码', 'captcha', 'recaptcha', '滑动验证', '点击验证']
    body_text = await page.evaluate('document.body.innerText')
    
    if any(kw in body_text.lower() for kw in captcha_keywords):
        # 立即截图作为证据
        screenshot = await page.screenshot()
        screenshot_path = save_screenshot(screenshot, f"captcha_{url}")
        
        # 抛出异常，停止该站点后续访问
        raise CaptchaDetectedError(
            url=url,
            screenshot=screenshot_path,
            message=f"Captcha detected at {url}, stopping site crawl"
        )
    return False
```

**关键原则**: 
- ✅ 检测到验证码 → 立即停止该站点后续链接访问
- ✅ 保存截图到failures.json
- ✅ 标记SiteRun=partial
- ✅ 仅影响依赖该页面集的规则（按作用域降级）
- ❌ 不使用打码平台/OCR/ML模型绕过
- ❌ 不轮换IP/浏览器指纹

#### **限速与并发控制（非伪装）**

```python
# 限速参数（礼貌延迟，降低站点压力）
RATE_LIMITING = {
    "same_domain_delay_sec": (2, 5),  # 随机2-5秒延迟
    "max_concurrent_workers": 2,       # 用户要求：2并发
    "request_jitter_ms": (100, 500),   # 请求时间随机抖动
}

async def rate_limited_fetch(url: str):
    # 同域延迟
    last_access = domain_access_tracker.get(domain)
    if last_access:
        elapsed = time.time() - last_access
        required_delay = random.uniform(*RATE_LIMITING["same_domain_delay_sec"])
        if elapsed < required_delay:
            await asyncio.sleep(required_delay - elapsed)
    
    # 执行抓取
    result = await fetch(url)
    
    # 记录访问时间
    domain_access_tracker[domain] = time.time()
    return result
```

### B.5 DMO/本体/分类层（可选，推荐最小可行方案）

#### **问题**
- 不同地区政府站点对同一概念使用不同词汇（如"政府信息公开指南" vs "公开指南"）
- content_paths人工维护成本高

#### **最小可行方案：栏目同义词映射**
```json
// rulepacks/jiangsu_suqian_v1_1/column_synonyms.json
{
  "disclosure_guide": {
    "canonical_name": "政府信息公开指南",
    "synonyms": ["公开指南", "信息公开指南", "办事指南"],
    "priority": 10
  },
  "annual_report": {
    "canonical_name": "政府信息公开年度报告",
    "synonyms": ["年度报告", "工作报告", "年报"],
    "priority": 9
  }
}
```

**使用方式**:
1. Worker抓取entry_points时，提取所有链接文本
2. 与column_synonyms匹配 → 自动扩展content_paths
3. 根据priority排序 → 高优先级栏目优先抓取

**高级方案（M4以后）**:
- 使用AI分类器：输入页面HTML → 输出栏目类型（disclosure_guide/annual_report/...）
- 建立跨地区栏目映射表：宿迁的"公开指南" ≈ 淮安的"信息公开指南"

---

## C. 数据模型与接口

### C.1 核心实体

#### **RulePack（规则包）**
```python
{
  "rule_pack_id": "jiangsu_suqian_v1_1",
  "name": "Suqian Government V1.1",
  "region_tag": "Jiangsu/Suqian",
  "scope": "City",
  "version": "v1.1",
  "schema_version": "rule_spec_v0_2",
  "generated_from": "authoring_ai_assisted",
  "generated_at": "2024-12-23T16:08:14Z",
  "rules_count": 20,
  "rules": [...],  // Rule[]
  "column_synonyms": {...}  // 可选
}
```

#### **Run（批次运行）**
```python
{
  "batch_id": "batch_abc123",
  "rule_pack_id": "jiangsu_suqian_v1_1",
  "rule_pack_version": "v1.1",
  "status": "done" | "partial" | "running" | "failed",
  "created_at": "2024-12-24T10:00:00Z",
  "completed_at": "2024-12-24T10:30:00Z",
  "site_ids": ["suqian_gov", "shuyang_gov"],
  "sampling_config": {...},
  "ai_config": {  // 可选
    "provider": "google",
    "model": "gemini-1.5-pro",
    "prompt_version": "v2.3",
    "enabled_for_classes": [3]
  },
  "site_runs": [...]  // SiteRun[]
}
```

#### **Artifact（抓取产物）**
```python
{
  "artifact_id": "art_001",
  "batch_id": "batch_abc123",
  "site_id": "suqian_gov",
  "url": "https://...",
  "fetched_at": "2024-12-24T10:05:00Z",
  "status_code": 200,
  "content_type": "text/html",
  "body_length": 45678,
  "snapshot_path": "runs/batch_abc/site_suqian/snapshot_0.html",
  "screenshot_path": "runs/batch_abc/site_suqian/screenshot_0.jpg",
  "trace_step": 5,
  "elapsed_ms": 2340
}
```

#### **RuleResult（规则结果）**
```python
{
  "rule_id": "jiangsu_suqian_v1_1-budget-16",
  "batch_id": "batch_abc123",
  "site_id": "suqian_gov",
  "status": "PASS" | "FAIL" | "UNCERTAIN" | "NOT-ASSESSABLE",
  "score_delta": -2.0,
  "reason": "keywords_missing",  // machine-readable
  "evidence_ids": ["evd_001", "evd_002"],
  "automation_level": "FULL",
  "confidence": 0.85,
  "evaluated_at": "2024-12-24T10:10:00Z",
  "highlight_hints": {  // 仅FAIL时有值
    "keywords": ["财政预算"],
    "selector": ".budget-section"
  },
  "ai_invocation_id": "ai_inv_123"  // 可选，关联AI调用记录
}
```

#### **Evidence（证据）**
```python
{
  "evidence_id": "evd_001",
  "type": "screenshot",  // 统一使用screenshot
  "rule_id": "jiangsu_suqian_v1_1-budget-16",
  "site_id": "suqian_gov",
  "url": "https://...",
  "timestamp": "2024-12-24T10:15:32Z",
  "locator": {
    "type": "selector",
    "value": ".budget-section",
    "text_quote": "2023年财政预算公开"
  },
  "file_path": "runs/batch_abc/site_suqian/screenshot_3.jpg",
  "file_size_bytes": 245678,
  "content_hash": "sha256:a3b2c1...",  // 统一使用content_hash
  "metadata": {
    "viewport": "1920x1080",
    "screenshot_quality": 85,
    "highlight_applied": true  // 用此字段区分是否红框标注
  }
}
```

#### **Failure（风控失败）**
```python
{
  "failure_id": "fail_001",
  "batch_id": "batch_abc123",
  "site_id": "suqian_gov",
  "failure_reason": "captcha_detected",
  "url": "https://...",
  "screenshot": "runs/batch_abc/site_suqian/error_0.jpg",
  "timestamp": "2024-12-24T10:05:23Z",
  "retry_count": 1,
  "metadata": {"captcha_type": "google_recaptcha"}
}
```

#### **AiInvocation（AI调用记录，可选）**
```python
{
  "ai_invocation_id": "ai_inv_123",
  "batch_id": "batch_abc123",
  "rule_id": "jiangsu_suqian_v1_1-institution-info-1",
  "provider": "google",
  "model": "gemini-1.5-pro",
  "prompt_version": "v2.3",
  "input_tokens": 1234,
  "output_tokens": 456,
  "latency_ms": 890,
  "invoked_at": "2024-12-24T10:12:00Z",
  "input_summary": "Extract contact info from HTML...",
  "output_result": {
    "phone": "0527-12345678",
    "address": "江苏省宿迁市..."
  },
  "success": true,
  "error_msg": null
}
```

### C.2 关键API接口

#### **批次管理**
```
POST   /api/batch/create
  Input: {rule_pack_id, site_ids, sampling_config}
  Output: {batch_id, status: "queued"}

GET    /api/batch/{batch_id}/status
  Output: {batch_id, status, progress, site_runs: [{site_id, status}]}

POST   /api/batch/{batch_id}/retry
  Input: {site_ids: ["suqian_gov"]}  // 重跑失败的站点
  Output: {new_batch_id}
```

#### **结果查询**
```
GET    /api/batch/{batch_id}/results
  Output: {rule_results: [...], summary: {...}}

GET    /api/batch/{batch_id}/failures
  Output: {failures: [...]}
```

#### **导出API**
```
GET    /api/batch/{batch_id}/export/summary
  Output: summary.json (下载)

GET    /api/batch/{batch_id}/export/issues
  Output: issues.json (所有FAIL规则)

GET    /api/batch/{batch_id}/export/evidence
  Output: evidence.zip (所有截图+快照)

POST   /api/batch/{batch_id}/export/report
  Input: {format: "markdown" | "html"}
  Output: report.md (人类可读摘要)
```

#### **人类可读摘要示例（report.md）**
```markdown
# 政务公开评估报告

**批次ID**: batch_abc123  
**规则包**: 江苏省宿迁市 v1.1 (20条规则)  
**评估时间**: 2024-12-24 10:00 - 10:30  
**评估站点**: 2个

## 总体评分
- 宿迁市政府: 85分 (1个FAIL, 2个UNCERTAIN)
- 沭阳县政府: 92分 (所有PASS)

## 不符合项明细
### 1. 财政预决算信息缺失
- **站点**: 宿迁市政府
- **规则**: jiangsu_suqian_v1_1-budget-16
- **扣分**: -2分
- **证据**: [screenshot](./evidence/site_suqian/screenshot_3.jpg)

## 风控记录
- 无验证码/封禁
```

---

## D. 分阶段工作计划

### M0: 双通道架构与最小闭环（优先完成，2-3天）

#### **目标**
建立双通道架构（Static主 + Playwright辅），验证"导入RulePack → 运行批次 → 生成报告"最小闭环

#### **任务列表**
1. **实现双通道Worker架构**
   - 保留`worker.py`为StaticWorker（requests主路径）
   - `playwright_worker.py`为辅助路径（按需触发）
   - 实现`should_use_playwright`判断逻辑
   - **交付物**: `dual_channel_worker.py`封装双通道调用
   - **验收**: 静态页面优先用requests，JS页面自动切Playwright

2. **content_paths优先级支持（P0提升）**
   - Site数据模型增加priority字段
   - FrontierQueue实现优先级排序
   - **交付物**: 修改后的`site_importer.py` + `batch_runner.py`
   - **验收**: 高priority URL优先访问（通过trace.json验证顺序）

3. **统一Evidence对象schema**
   - 定义Evidence最小字段（evidence_id, type, url, timestamp, locator, file_path, content_hash）
   - RuleResult只引用evidence_id
   - **交付物**: 修改后的`models.py` + `storage.py`
   - **验收**: 所有RuleResult.evidence_ids指向有效Evidence对象

4. **FAIL必有证据降级机制**
   - 在`_fail`方法中检查evidence_id有效性
   - 无证据自动降级UNCERTAIN并记录日志
   - **交付物**: 增强后的`rule_engine.py`
   - **验收**: ✅ **硬约束**: FAIL证据完整率=100%

5. **按作用域failure降级**
   - 实现failure影响范围计算（入口页/页面集/单URL）
   - 仅影响依赖该页面集的规则
   - **交付物**: 修改后的`rule_engine.py`
   - **验收**: 预算栏目失败不影响其他17条规则

6. **Sandbox端到端测试**
   - 运行`python scripts/run_pilot.py --rulepack rulepacks/sandbox_mvp --sites sandbox/sites.json`
   - **交付物**: 测试日志+截图证据
   - **验收**: ✅ Sandbox站点PASS率100%，FAIL证据完整率100%

#### **验收标准（可度量）**
- [x] ✅ **硬约束**: FAIL证据完整率 = 100%（无证据必降级UNCERTAIN）
- [x] ✅ content_paths优先级生效: trace.json中priority=10的URL排在priority=5之前
- [x] ✅ 双通道生效: 静态可用页面使用requests，JS页面使用Playwright（通过Artifact.metadata区分）
- [x] ✅ Sandbox测试: PASS率100%，failures.json为空

---

### M1: 覆盖率指标与栏目预算切分（1周）

#### **目标**
实现coverage指标输出、栏目预算切分，完善failures可导出复核

#### **任务列表**
1. **覆盖率指标完整输出（P0）**
   - 在`summary.json`增加coverage字段:
     - `total_content_paths`: 站点声明的content_paths总数
     - `sampled_urls`: 实际访问URL数
     - `sampling_rate`: sampled/total比例
     - `rule_hit_rate_by_category`: 各栏目规则命中率
   - **交付物**: 修改后的`reporting.py`
   - **验收**: ✅ **硬约束**: coverage.sampling_rate可计算，rule_hit_rate_by_category可解释低通过率

2. **栏目预算切分（P0）**
   - 实现栏目分类（主动公开15页/依申请5页/...）
   - FrontierQueue按栏目分配配额
   - **交付物**: 修改后的`batch_runner.py`
   - **验收**: trace.json显示各栏目访问数符合配额

3. **Failures Taxonomy完备且可导出**
   - 实现9种失败类型（见B.2表格）
   - 生成`failures.json`包含affected_page_scope
   - **交付物**: `failures.json`模板 + 导出逻辑
   - **验收**: ✅ **硬约束**: failures.json可导出，包含failure_id/affected_page_scope/screenshot字段

4. **验证码检测与按作用域降级**
   - 实现`detect_and_stop_on_captcha`方法
   - 检测到验证码 → 停止该页面集后续访问 → 仅影响依赖规则
   - **交付物**: 增强后的`playwright_worker.py`
   - **验收**: 预算栏目验证码触发，仅3条预算规则UNCERTAIN，其他17条正常

5. **触发式加深**
   - 实现`trigger_deepen`逻辑（命中率<30%时额外抽样）
   - **交付物**: 增强后的`batch_runner.py`
   - **验收**: 模拟低命中率 → 自动加深 → trace.json记录deepen原因

6. **真实站点测试**
   - 运行宿迁政府网站完整评估
   - **交付物**: 批次报告 + coverage分析文档
   - **验收**: ✅ 至少发现1个FAIL案例，coverage指标可解释结果

#### **验收标准（可度量）**
- [x] ✅ **硬约束1**: FAIL证据完整率 = 100%
- [x] ✅ **硬约束2**: coverage指标完整（sampling_rate, rule_hit_rate_by_category可计算）
- [x] ✅ **硬约束3**: failures.json可导出，包含affected_page_scope字段
- [x] ✅ 栏目预算生效: trace.json显示主动公开15页/依申请5页符合配额
- [x] ✅ 按作用域降级: 单栏目失败不影响其他栏目规则（通过RuleResult验证）

---

### M2: 报告导出与可追溯（1周）

#### **目标**
完善交付物生成、可追溯性、人类可读报告

#### **任务列表**
1. **summary.json规范化**
   - 包含批次元数据、覆盖率、通过率、失败统计
   - **交付物**: `summary.json`模板
   - **验收**: 符合C.2定义的schema

2. **issues.json规范化**
   - 所有FAIL规则明细（rule_id、site_id、score_delta、reason、evidence_urls）
   - **交付物**: `issues.json`模板
   - **验收**: 包含所有FAIL的完整信息

3. **evidence.zip生成**
   - 打包所有截图+快照
   - 保留目录结构（batch/site/rule/）
   - **交付物**: `export.py`实现
   - **验收**: zip解压后结构正确

4. **report.md生成**
   - Markdown格式人类可读摘要
   - 包含总分、不符合项明细、证据链接
   - **交付物**: `report_generator.py`实现
   - **验收**: Markdown可在GitHub正确渲染

5. **可追溯性字段绑定**
   - 每个RuleResult绑定{rule_pack_id, version, schema_version}
   - 每个Run记录创建时间、完成时间
   - **交付物**: 修改后的数据模型
   - **验收**: ✅ 任意RuleResult可追溯到规则版本

6. **导出API实现**
   - 实现`/api/batch/{id}/export/*`接口
   - **交付物**: `platform/server.py`增强
   - **验收**: API返回正确的文件下载

#### **验收标准**
- [x] ✅ **硬约束1**: FAIL必有证据（持续验证）
- [x] ✅ 所有交付物（summary/issues/failures/evidence.zip/report.md）齐全
- [x] ✅ 可追溯性：每个Run可回溯到RulePack版本
- [x] ✅ report.md人类可读性良好（产品经理验收）

---

### M3: AI辅助与Class 3规则（1-2周，可选）

#### **目标**
集成AI辅助要素抽取，仅用于Class 3规则，不输出最终判定

#### **任务列表**
1. **AI接口封装**
   - 封装Gemini API调用
   - 实现超时/重试/降级逻辑
   - **交付物**: `autoaudit/ai_assist.py`
   - **验收**: 能调用Gemini API并返回结构化JSON

2. **要素抽取器**
   - 实现`extract_elements`（抽取联系人、电话、日期等）
   - **交付物**: `AIAssistant.extract_elements`方法
   - **验收**: 准确率>80%（人工验证20个样本）

3. **AI调用记录**
   - 新增`AiInvocation`实体
   - 记录{provider, model, prompt_version, latency, tokens}
   - **交付物**: 修改后的数据模型 + 落库逻辑
   - **验收**: ✅ 每次AI调用有完整记录

4. **Class 3规则集成**
   - rule_engine检测到Class 3 → 调用AI
   - AI结果仅供参考，最终判定仍由evaluator执行
   - **交付物**: 修改后的`rule_engine.py`
   - **验收**: ✅ AI失败不影响规则执行（降级UNCERTAIN）

5. **AI审计与抽检**
   - 生成AI调用报告（成功率、延迟分布、token消耗）
   - 标记需人工抽检的AI结果
   - **交付物**: `ai_audit_report.md`模板
   - **验收**: 产品经理能理解AI使用情况

6. **Cost Control**
   - 设置token上限（单次/单批次）
   - 超限时禁用AI并记录警告
   - **交付物**: `ai_assist.py`增强
   - **验收**: 超限时自动降级不调用AI

#### **验收标准**
- [x] ✅ **硬约束1**: FAIL必有证据（AI不影响此约束）
- [x] ✅ AI仅辅助Class 3规则，不输出PASS/FAIL
- [x] ✅ 所有AI调用有完整记录（可追溯）
- [x] ✅ AI失败不卡死任务（降级UNCERTAIN）

---

### M4: 规模化与优化（2-3周）

#### **目标**
支持多地区RulePack、大规模批次、性能优化

#### **任务列表**
1. **栏目同义词映射**
   - 实现`column_synonyms.json`支持
   - 自动扩展content_paths
   - **交付物**: `rulepack_importer.py`增强
   - **验收**: 同义词自动识别准确率>90%

2. **批次队列调度**
   - 支持夜跑窗口（定时启动批次）
   - **交付物**: `scheduler.py`
   - **验收**: 能按时启动夜间批次

3. **性能优化**
   - 截图压缩优化（WebP格式）
   - 浏览器复用（避免频繁启动）
   - **交付物**: 性能测试报告
   - **验收**: 单站点评估时间<5分钟

4. **多地区RulePack支持**
   - 导入淮安、上海等地RulePack
   - 测试跨地区规则执行
   - **交付物**: 至少3个地区RulePack
   - **验收**: 所有地区规则正常执行

5. **Dashboard观测**
   - 实现批次列表页、站点详情页
   - 显示覆盖率、通过率、失败原因统计
   - **交付物**: `platform/`前端页面
   - **验收**: 产品经理能通过UI查看所有批次

6. **RulePack版本治理**
   - 支持规则版本升级（v1.1 → v1.2）
   - 比对不同版本结果差异
   - **交付物**: 版本管理文档 + 比对工具
   - **验收**: 能对比v1.1和v1.2的评估结果

#### **验收标准**
- [x] ✅ **硬约束1**: FAIL必有证据（持续验证）
- [x] ✅ **硬约束2**: coverage指标完整
- [x] ✅ 支持至少3个地区RulePack
- [x] ✅ 性能达标（单站点<5分钟）

---

## E. 风险与对策

### E.1 反爬/验证码风险

**风险**: 政府网站升级反爬虫，频繁触发验证码

**对策**:
1. **检测不对抗**: 实现`detect_captcha` → 立即停止 → 记录failures
2. **礼貌限速**: 同域访问间隔2-5秒延迟（降低站点压力）
3. **并发控制**: 最多2个并发worker（避免短时大量请求）
4. **检测即停止**: 触发验证码/403/429 → 立即停止该页面集 → 记录failure

**验收**: 测试集中观测验证码触发情况（非硬指标，用于调优限速参数）

---

### E.2 动态站点风险

**风险**: 页面内容完全由JavaScript渲染，DOM解析失败

**对策**:
1. **Playwright按需触发**: 静态抓取失败或body为空时触发（与B.4一致）
2. **滚动触发懒加载**: `window.scrollTo(0, document.body.scrollHeight)`
3. **智能等待**: 检测到loading动画 → 等待消失后再截图
4. **降级机制**: Playwright失败 → 回退静态结果 + 附加warning

**验收**: 测试20个已知JS渲染站点，成功率>80%

---

### E.3 抽样偏差风险

**风险**: 抽样结果不能代表整体，导致误判

**对策**:
1. **content_paths提权**: 手工标注高优先级栏目
2. **触发式加深**: 命中率<30% → 自动增加样本
3. **Coverage指标**: 报告中明确说明"仅抽样X页，可能存在遗漏"
4. **人工抽检**: 对UNCERTAIN案例人工复核

**验收**: coverage指标能解释低通过率原因

---

### E.4 证据缺失风险

**风险**: 规则判定FAIL但无截图/快照证据

**对策**:
1. **强制降级**: `_fail`方法检查evidence → 无证据自动降级UNCERTAIN
2. **双重截图**: 访问时普通截图 + FAIL时红框标注截图
3. **快照备份**: 即使截图失败，也保留HTML快照

**验收**: ✅ **硬约束**: 100%的FAIL有evidence

---

### E.5 RulePack版本治理风险

**风险**: 规则频繁变更，历史批次无法复现

**对策**:
1. **版本强绑定**: 每个Run记录{rule_pack_id, version}
2. **规则不可变**: 已发布的RulePack禁止修改，只能新建版本
3. **Schema版本**: 引入schema_version（当前v0.2），向后兼容
4. **Git管理**: rulepacks/目录纳入Git版本控制

**验收**: 1个月后仍可复现历史批次结果

---

### E.6 AI建议可信度风险

**风险**: AI幻觉导致要素抽取错误，影响判定

**对策**:
1. **AI不做裁判**: AI结果仅供rule_engine参考，不直接输出PASS/FAIL
2. **人工抽检**: 标记AI辅助的RuleResult → 产品经理抽检10%
3. **置信度阈值**: AI输出confidence<0.7 → 降级UNCERTAIN
4. **原始输出落库**: 保存AI原始JSON → 可事后审计

**验收**: AI辅助的规则，人工抽检准确率>90%

---

### E.7 AI成本超支风险

**风险**: 大规模使用AI导致token成本过高

**对策**:
1. **仅Class 3启用**: 控制AI使用范围
2. **Token上限**: 单次调用max_tokens=2000，单批次总量<100K
3. **成本监控**: 每次Run记录token消耗 → 生成成本报告
4. **降级开关**: 成本超限 → 禁用AI → 规则降级UNCERTAIN

**验收**: 单批次AI成本<10元人民币

---

## 附录：假设与依赖

### 假设
1. 服务器环境支持Playwright Chromium（有足够内存，至少4GB）
2. 政务网站90%为中文，支持UTF-8编码
3. 单个站点评估完成时间<5分钟（30页抽样）


### 外部依赖
1. **Playwright**: v1.40+ （已安装chromium）
2. **Python**: 3.10+（支持async/await）
3. **存储**: 本地文件系统至少50GB（存储截图+快照）
4. **Gemini API**: 需要API Key（M3阶段）

### 配置参数
```python
# config.py
MAX_CONCURRENT_WORKERS = 2  # 用户要求
DEFAULT_TIMEOUT_SEC = 30
SCREENSHOT_QUALITY = 85  # JPEG quality
MAX_CONTENT_PAGES_PER_SITE = 30
SAME_DOMAIN_DELAY_SEC = (2, 5)  # 随机延迟范围
```

---

**文档结束**
