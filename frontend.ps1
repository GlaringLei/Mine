param([ValidateSet('dev', 'build', 'preview', 'install')][string]$Action = 'dev')
$ErrorActionPreference = 'Stop'
$runtimeRoot = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies'
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$nodePath = if ($nodeCommand) { $nodeCommand.Source } else { Join-Path $runtimeRoot 'node/bin/node.exe' }
Push-Location (Join-Path $PSScriptRoot 'qianduan')
try {
    if ($Action -eq 'install') {
        $pnpmCommand = Get-Command pnpm -ErrorAction SilentlyContinue
        $pnpmPath = if ($pnpmCommand) { $pnpmCommand.Source } else { Join-Path $runtimeRoot 'bin/fallback/pnpm.cmd' }
        & $pnpmPath install --frozen-lockfile --store-dir (Join-Path $PSScriptRoot '.pnpm-store')
    } else {
        $vitePath = Join-Path (Get-Location) 'node_modules/vite/bin/vite.js'
        if (!(Test-Path $vitePath)) { throw 'Run ./frontend.ps1 install first.' }
        switch ($Action) {
            'dev' { & $nodePath $vitePath }
            'build' { & $nodePath $vitePath build }
            'preview' { & $nodePath $vitePath preview --host 127.0.0.1 --port 4173 --strictPort }
        }
    }
    if ($LASTEXITCODE -ne 0) { throw "Frontend command failed: $LASTEXITCODE" }
} finally { Pop-Location }
