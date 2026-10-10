param([ValidateSet('Desktop','Browser')][string]$Mode = 'Desktop')
$ErrorActionPreference = 'Stop'
$pythonExe = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) { throw '需要 Python 3.10 或更新版本。请安装后重试。' }
    $pythonExe = $pythonCommand.Source
}
$baseUrl = 'http://127.0.0.1:8765'
function Get-MemoryHealth {
    try { return Invoke-RestMethod -Uri ($baseUrl + '/health') -TimeoutSec 2 } catch { return $null }
}
$health = Get-MemoryHealth
if (-not $health -or $health.app -ne 'personal-memory') {
    $cacheFolder = Join-Path $PSScriptRoot '.local-cache'
    New-Item -ItemType Directory -Path $cacheFolder -Force | Out-Null
    $appFile = Join-Path $PSScriptRoot 'app.py'
    $appMode = if ($Mode -eq 'Desktop') { '--desktop' } else { '--no-browser' }
    $process = Start-Process -FilePath $pythonExe -ArgumentList @('-X','utf8',('"' + $appFile + '"'),$appMode) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $cacheFolder 'app.log') -RedirectStandardError (Join-Path $cacheFolder 'app-error.log') -PassThru
    $process.Id | Set-Content -LiteralPath (Join-Path $cacheFolder 'app.pid') -Encoding ascii
    for ($attempt = 0; $attempt -lt 45; $attempt++) {
        Start-Sleep -Milliseconds 300
        $health = Get-MemoryHealth
        if ($health -and $health.app -eq 'personal-memory' -and ($Mode -eq 'Browser' -or $health.desktop)) { break }
        if ($process.HasExited) { throw '启动失败，请查看 .local-cache/app-error.log。桌面模式需要 Tk。' }
    }
}
if (-not $health -or $health.app -ne 'personal-memory') { throw '启动失败，可能是端口 8765 已被占用。请查看 .local-cache/app-error.log。' }
if ($Mode -ne 'Browser' -and $health.desktop) {
    $page = Invoke-WebRequest -Uri ($baseUrl + '/') -UseBasicParsing -TimeoutSec 3
    $token = [regex]::Match($page.Content, 'name="memory-csrf" content="([^"]+)"').Groups[1].Value
    Invoke-RestMethod -Uri ($baseUrl + '/api/window/show') -Method Post -ContentType 'application/json' -Headers @{'X-Memory-CSRF'=$token} -Body '{}' -TimeoutSec 5 | Out-Null
} else {
    Start-Process $baseUrl
}
