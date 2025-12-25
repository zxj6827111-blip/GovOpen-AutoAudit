# Walkthrough - M7 Productization

## Overview
M7 focuses on establishing development discipline and engineering the RulePack system for scalability.

## Key Changes

### 1. Process Governance
- **Main Branch Protection**: Direct commits prohibited. All changes flow via PR (Simulated).
- **Versioning**: Released `v0.3.0-m6` with [CHANGELOG](./CHANGELOG.md).

### 2. Parameterized Testing
The `pilot_suite_test.py` now supports dynamic configuration:
```bash
python scripts/pilot_suite_test.py \
  --rulepack rulepacks/jiangsu_shuyang_v1 \
  --positive sites/positive_shuyang.json \
  --negative sites/negative.json
```

### 3. RulePack Engineering
Introduced "Template Family" pattern for RulePack authoring to reduce duplication.
- **Common**: `authoring/src/jiangsu_common.json` (Provincial Shared)
- **Overrides**: `authoring/src/suqian_overrides.json` (Region Specific)
- **Composition**: `authoring/compose_rulepack.py` merges them into authoring-ready sources.
