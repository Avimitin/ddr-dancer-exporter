$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pagePath = Join-Path $projectRoot 'web\index.html'
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'web\app.bundle.js'))) {
    Write-Host 'The webpage bundle is missing. Extract a release ZIP, or build the frontend from source.'
    exit 1
}
$tokenPath = Join-Path $projectRoot '.bridge-token'
if (-not (Test-Path -LiteralPath $tokenPath)) {
    $randomBytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($randomBytes)
    $rng.Dispose()
    $sessionSecret = -join ($randomBytes | ForEach-Object { $_.ToString('x2') })
    [IO.File]::WriteAllText($tokenPath, $sessionSecret)
} else {
    $sessionSecret = [IO.File]::ReadAllText($tokenPath).Trim()
}
if ($sessionSecret -notmatch '^[0-9a-f]{64}$') { throw 'Invalid local bridge token. Remove .bridge-token and retry.' }
# The same static page always opens. It discovers backend capabilities itself.
$pageUrl = ([Uri]$pagePath).AbsoluteUri + '#session=' + $sessionSecret
Start-Process $pageUrl

# Starting an optional backend does not select or host the frontend.
$candidates = @()
if ($env:DDR_BLENDER) { $candidates += $env:DDR_BLENDER }
$command = Get-Command blender.exe -ErrorAction SilentlyContinue
if ($command) { $candidates += $command.Source }
$candidates += (Join-Path $projectRoot 'blender\blender.exe')
foreach ($searchRoot in @((Join-Path $env:ProgramFiles 'Blender Foundation'), (Join-Path $env:LOCALAPPDATA 'Programs\Blender Foundation'), (Join-Path $projectRoot 'tools'))) {
    if (Test-Path -LiteralPath $searchRoot) {
        $candidates += Get-ChildItem -LiteralPath $searchRoot -Filter blender.exe -Recurse -File -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName
    }
}
$blenderPath = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if ($blenderPath) {
    $connection = New-Object Net.Sockets.TcpClient
    try { $connection.Connect('127.0.0.1', 8765); $alreadyListening = $true } catch { $alreadyListening = $false } finally { $connection.Dispose() }
    if (-not $alreadyListening) {
        $logDirectory = Join-Path $projectRoot 'analysis'
        New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
        $bridgeScript = Join-Path $projectRoot 'service\blender_bridge.py'
        Start-Process -FilePath $blenderPath -WindowStyle Hidden -ArgumentList @('--background', '--disable-autoexec', '--factory-startup', '--python-exit-code', '1', '--python', ('"' + $bridgeScript + '"'), '--', '--token-file', ('"' + $tokenPath + '"')) -RedirectStandardOutput (Join-Path $logDirectory 'bridge.stdout.log') -RedirectStandardError (Join-Path $logDirectory 'bridge.stderr.log')
    }
}
