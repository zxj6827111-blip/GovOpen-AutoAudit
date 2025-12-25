# AI测试脚本使用指南

## 🔑 步骤1: 从.env文件加载API密钥

由于我们的系统暂未集成python-dotenv，需要手动设置环境变量。

### 方法A: 手动复制粘贴（推荐）

打开您的`.env`文件，复制API密钥，然后：

```powershell
# 设置Gemini API密钥（替换为您的实际密钥）
$env:GEMINI_API_KEY = "您的Gemini密钥"

# 设置DeepSeek API密钥（替换为您的实际密钥）
$env:DEEPSEEK_API_KEY = "您的DeepSeek密钥"
```

### 方法B: 使用PowerShell脚本自动加载

创建一个临时的`load_env.ps1`文件：

```powershell
# 读取.env文件并设置环境变量
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.+)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        if ($name -notmatch '^#') {
            Set-Item -Path "env:$name" -Value $value
            Write-Host "Set $name"
        }
    }
}
```

然后运行：
```powershell
.\load_env.ps1
```

---

## 🧪 步骤2: 运行AI测试

```powershell
python scripts/test_ai_providers.py
```

---

## 📊 预期输出

成功时应该看到：

```
================================================================================
测试 Gemini API
================================================================================

发送测试请求...
✅ Gemini API响应成功!

响应内容: 北京是中华人民共和国的首都...

================================================================================
测试 DeepSeek API
================================================================================

发送测试请求...
✅ DeepSeek API响应成功!

响应内容: 上海是中国的经济中心...

================================================================================
测试总结
================================================================================
Gemini: ✅ 通过
DeepSeek: ✅ 通过
AIExtractor: ✅ 通过

🎉 所有AI Provider测试通过!
```

---

## ❌ 常见错误

### 错误1: API Key未配置
```
❌ GEMINI_API_KEY未配置
```
**解决**: 确保设置了环境变量

### 错误2: 网络连接失败
```
Error: getaddrinfo ENOTFOUND
```
**解决**: 检查网络连接，可能需要代理

### 错误3: API Key无效
```
Invalid API key
```
**解决**: 检查API密钥是否正确复制

---

## 💡 提示

- 环境变量仅在当前PowerShell会话有效
- 关闭PowerShell后需重新设置
- 可以将`load_env.ps1`放在项目根目录方便使用
