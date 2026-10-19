$ErrorActionPreference = 'Stop'
$launchCalls = [System.Collections.Generic.List[object]]::new()
function Start-Process {
    param($FilePath, $ArgumentList, $WindowStyle, $RedirectStandardOutput, $RedirectStandardError)
    $launchCalls.Add(@{ FilePath = $FilePath; Arguments = $ArgumentList; WindowStyle = $WindowStyle })
}
& (Join-Path (Split-Path $PSScriptRoot -Parent) 'Launch.ps1')
if ($launchCalls.Count -lt 1 -or -not $launchCalls[0].FilePath.StartsWith('file:///')) {
    throw 'Launcher did not open the static page first'
}
if ($launchCalls.Count -eq 2 -and $launchCalls[1].WindowStyle -ne 'Hidden') {
    throw 'Bridge process is not hidden'
}
Write-Output 'PASS: launcher opens static page first; optional bridge uses a hidden process.'
