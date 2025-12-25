# Retroactive PR: M6 Cross-region Verify & False Positive Governance

**Branch**: `release/v0.3.0-m6` -> `main`
**Tag**: `v0.3.0-m6`

## 变更摘要

### 1. 核心修复
- **Fix Converter**: 修复 `authoring/converter.py` 中 `locator` 字段丢失导致全量误报的问题。
- **Fix Encoding**: `autoaudit/worker.py` 启用 `apparent_encoding` 解决 GBK/UTF-8 混合站点的乱码问题。
- **Fix Reporting**: `autoaudit/reporting.py` 补全 `rule_results` 导出，支持细粒度测试断言。

### 2. 新增特性
- **Pilot Suite**: 新增 `scripts/pilot_suite_test.py` 回归测试套件，通过率阈值自动化卡点。
- **Shuyang RulePack**: 新增 `jiangsu_shuyang_v1`，包含针对性的同义词扩充（Rule 1B, 16B 等）。

### 3. 数据变更
- **Sites**: 更新 `pilot_sites.json`，新增沭阳政府网及负例对照组（新闻、403站点）。

## 验收结果
- **Acceptance Gate**: Passed
- **Pilot Pass Rate**: Suqian (41.7%), Shuyang (20.8%)
- **False Positive Rate**: 4.2% (≤ 5% target met)
