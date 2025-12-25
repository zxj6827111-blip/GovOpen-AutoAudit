# GovOpen-AutoAudit 快速测试清单

## ✅ 测试前准备

### 1. 确认环境
```powershell
# 检查Python版本
python --version  # 应该 >= 3.10

# 检查当前目录
pwd  # 应该在项目根目录
```

### 2. 安装依赖（首次）
```powershell
pip install playwright beautifulsoup4 lxml
playwright install chromium
```

---

## ✅ 测试步骤

### 测试1: 验收测试（3分钟）

```powershell
# M0验收
python scripts/m0_acceptance.py

# M1验收
python scripts/m1_acceptance.py

# M2验收  
python scripts/m2_acceptance.py
```

**预期结果**: 所有测试输出"🎉 XXX阶段验收全部通过！"

---

### 测试2: Sandbox批次测试（5分钟）

```powershell
python scripts/run_pilot.py
```

**预期结果**:
1. Console输出批次ID，如`batch_20241224_170500`
2. 创建目录`runs/batch_20241224_170500/`
3. 生成文件:
   - `export/summary.json`
   - `export/issues.json`
   - `export/failures.json`
   - `export/report.md`
   - `export/evidence.zip`

**查看报告**:
```powershell
# 找到最新批次
cd runs
ls | sort -Descending | select -First 1

# 查看报告（替换为实际批次ID）
notepad batch_20241224_170500/export/report.md
```

---

### 测试3: AI功能测试（可选，需API KEY）

```powershell
# 设置API密钥
$env:GEMINI_API_KEY = "your-gemini-key"

# 运行AI测试
python scripts/test_m3_ai.py
```

**预期结果**: 
- ✅ 双Provider支持
- ✅ Cost Control生效
- ✅ AI审计报告生成

---

## ✅ 验证结果

### 检查点1: summary.json

```powershell
# 查看统计（替换批次ID）
$json = Get-Content runs/batch_xxx/export/summary.json | ConvertFrom-Json
$json.statistics
```

**应包含**:
- `pass_rate`
- `fail_rate`  
- `total_rules`
- `total_sites`

### 检查点2: report.md

打开`export/report.md`，应该看到：
- ✅ 批次评估报告标题
- ✅ 评估概览（站点数、规则数）
- ✅ 站点结果概览表格
- ✅ 不符合项明细（如有）

### 检查点3: evidence.zip

```powershell
# 解压查看（替换批次ID）
Expand-Archive runs/batch_xxx/export/evidence.zip -DestinationPath temp_evidence
ls temp_evidence
```

**应包含**:
- `site_xxx/` 目录
- `.webp` 截图文件
- `.html` 快照文件

---

## ❌ 常见错误处理

### 错误1: "playwright._impl._api_types.Error"

**解决**:
```powershell
playwright install chromium
```

### 错误2: "No module named 'bs4'"

**解决**:
```powershell
pip install beautifulsoup4 lxml
```

### 错误3: "Permission denied"

**解决**: 使用管理员权限运行PowerShell

---

## 📊 测试报告模板

测试完成后，填写以下信息：

```
测试日期: ___________
测试人员: ___________

验收测试:
- [ ] M0: □ 通过 □ 失败
- [ ] M1: □ 通过 □ 失败  
- [ ] M2: □ 通过 □ 失败

Sandbox测试:
- [ ] 批次运行: □ 成功 □ 失败
- [ ] 报告生成: □ 正常 □ 异常
- [ ] 证据包: □ 完整 □ 缺失

问题记录:
_______________________________
_______________________________

总体评价: □ 系统正常 □ 存在问题
```

---

**测试完成后请反馈结果！** 🎯
