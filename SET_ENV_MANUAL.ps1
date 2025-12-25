# ========================================================================
# 快速设置AI环境变量
# ========================================================================
#
# 请复制以下命令到PowerShell执行：

# 1. 设置DeepSeek API密钥（从.env文件复制您的密钥）
$env:DEEPSEEK_API_KEY = "替换为您的DeepSeek密钥"

# 2. 设置Gemini API密钥（可选）
# $env:GEMINI_API_KEY = "替换为您的Gemini密钥"

# 3. 验证设置
Write-Host "DeepSeek密钥: $env:DEEPSEEK_API_KEY"

# 4. 运行测试
# python scripts\test_ai_simple.py

# ========================================================================
# 或者使用这个一键命令（需要手动编辑密钥）：
# ========================================================================
# Get-Content .env | Select-String "^DEEPSEEK_API_KEY=" | ForEach-Object { 
#     $kv = $_ -split '=', 2
#     $env:DEEPSEEK_API_KEY = $kv[1]
# }
