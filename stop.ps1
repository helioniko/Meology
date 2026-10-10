$ErrorActionPreference = 'Stop'
$pidFile = Join-Path $PSScriptRoot '.local-cache\app.pid'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Host '没有通过启动器运行的个人记忆进程。'; exit }
$memoryProcessId = [int](Get-Content -LiteralPath $pidFile -Raw).Trim()
$memoryProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$memoryProcessId"
$appFile = Join-Path $PSScriptRoot 'app.py'
if ($memoryProcess -and $memoryProcess.CommandLine -and $memoryProcess.CommandLine.Contains($appFile) -and $memoryProcess.Name -match '^pythonw?\.exe$') {
    try {
        $baseUrl = 'http://127.0.0.1:8765'
        $health = Invoke-RestMethod -Uri ($baseUrl + '/health') -TimeoutSec 2
        if ($health.app -eq 'personal-memory' -and $health.pid -eq $memoryProcessId) {
            $page = Invoke-WebRequest -Uri ($baseUrl + '/') -UseBasicParsing -TimeoutSec 2
            $token = [regex]::Match($page.Content, 'name="memory-csrf" content="([^"]+)"').Groups[1].Value
            Invoke-RestMethod -Uri ($baseUrl + '/api/window/quit') -Method Post -ContentType 'application/json' -Headers @{'X-Memory-CSRF'=$token} -Body '{}' -TimeoutSec 3 | Out-Null
            for ($attempt = 0; $attempt -lt 40; $attempt++) {
                if (-not (Get-Process -Id $memoryProcessId -ErrorAction SilentlyContinue)) { break }
                Start-Sleep -Milliseconds 100
            }
        }
    } catch { }
    if (Get-Process -Id $memoryProcessId -ErrorAction SilentlyContinue) { Stop-Process -Id $memoryProcessId }
    Write-Host '个人记忆已退出；个人数据和后台任务保留在本机。'
} elseif ($memoryProcess) { throw '进程身份与本项目不匹配，未关闭任何进程。' }
Remove-Item -LiteralPath $pidFile -ErrorAction SilentlyContinue
