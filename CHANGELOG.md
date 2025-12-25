# CHANGELOG

## [v0.3.0-m6] - 2025-12-24

### Added
- **Shuyang Region**: Added `jiangsu_shuyang_v1` RulePack with 24 rules (including synonyms).
- **Pilot Suite**: Added `scripts/pilot_suite_test.py` for automated pass-rate regression testing.
- **Negative Testing**: Added `neg_simple_news` and `neg_weather` sites to `pilot_sites.json` for False Positive governance.

### Fixed
- **Rule Converter**: Fixed `authoring/converter.py` dropping `locator` fields (Critical).
- **Encoding**: Fixed `autoaudit/worker.py` Mojibake issue with `apparent_encoding`.
- **Reporting**: Fixed `autoaudit/reporting.py` to include full `rule_results` in `summary.json`.
