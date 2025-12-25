# 自动从.env文件加载环境变量
# 使用方法: .\load_env.ps1

Write-Host "="*80 -ForegroundColor Cyan
Write-Host "自动加载.env环境变量" -ForegroundColor Cyan
Write-Host "="*80 -ForegroundColor Cyan

$envFile = ".env"

if (-not (Test-Path $envFile)) {
    Write-Host "`n❌ .env文件不存在!" -ForegroundColor Red
    Write-Host "   请先创建.env文件（复制.env.example并填入密钥）" -ForegroundColor Yellow
    exit 1
}

Write-Host "`n✅ 找到.env文件，开始读取..." -ForegroundColor Green

$count = 0
Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    
    # 跳过注释和空行
    if ($line -match '^#' -or $line -eq '') {
        return
    }
    
    # 匹配 KEY=VALUE 格式
    if ($line -match '^([A-Z_]+)=(.*)$') {
        $name = $matches[1]
        $value = $matches[2]
        
        # 移除可能的引号
        $value = $value.Trim('"').Trim("'")
        
        # 设置环境变量
        Set-Item -Path "env:$name" -Value $value
        
        # 显示前几个字符
        $preview = if ($value.Length -gt 20) { $value.Substring(0, 20) + "..." } else { $value }
        Write-Host "   ✅ $name = $preview" -ForegroundColor Green
        $count++
    }
}

Write-Host "`n✅ 成功加载 $count 个环境变量" -ForegroundColor Green

# 验证关键变量
Write-Host "`n验证关键变量:" -ForegroundColor Yellow
$geminiSet = Test-Path env:GEMINI_API_KEY
$deepseekSet = Test-Path env:DEEPSEEK_API_KEY

if ($geminiSet) {
    Write-Host "   ✅ GEMINI_API_KEY: 已设置" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  GEMINI_API_KEY: 未设置" -ForegroundColor Yellow
}

if ($deepseekSet) {
    Write-Host "   ✅ DEEPSEEK_API_KEY: 已设置" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  DEEPSEEK_API_KEY: 未设置" -ForegroundColor Yellow
}

Write-Host "`n" + "="*80 -ForegroundColor Cyan
Write-Host "环境变量已加载到当前PowerShell会话" -ForegroundColor Cyan
Write-Host "可以运行测试了: python scripts\test_ai_simple.py" -ForegroundColor Cyan
Write-Host "="*80 -ForegroundColor Cyan
