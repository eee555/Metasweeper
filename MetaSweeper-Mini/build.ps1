param(
    [string]$OutputPath,
    [string]$PythonPath = $env:MINI_PYTHON,
    [switch]$Offline
)

$ErrorActionPreference = 'Stop'
if (-not $PythonPath) { $PythonPath = (Get-Command python.exe).Source }
$env:MINI_PYTHON = $PythonPath
if ($OutputPath) { $OutputPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputPath) }

$offlineArg = @()
if ($Offline) { $offlineArg = @('--offline') }
& $PythonPath (Join-Path $PSScriptRoot 'prepare.py') @offlineArg
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare ms_toollib.' }

if ($env:VSCMD_ARG_TGT_ARCH -ne 'x64' -or -not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    $installation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $installation) { throw 'Visual Studio with the MSVC x64 toolchain is required.' }
    Import-Module (Join-Path $installation 'Common7\Tools\Microsoft.VisualStudio.DevShell.dll')
    Enter-VsDevShell -VsInstallPath $installation -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64'
}

$targetDir = Join-Path $PSScriptRoot 'obj\win-sdl3'
Push-Location -LiteralPath $PSScriptRoot
try {
    cargo build --locked --release --target-dir $targetDir @offlineArg
    if ($LASTEXITCODE -ne 0) { throw 'Could not build MetaSweeper-Mini.' }

    $exe = Get-Item -LiteralPath (Join-Path $targetDir 'release\MetaSweeper-Mini.exe')
    if ($OutputPath -and $OutputPath -ne $exe.FullName) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $OutputPath) -Force | Out-Null
        Copy-Item -LiteralPath $exe.FullName -Destination $OutputPath -Force
        $exe = Get-Item -LiteralPath $OutputPath
    }
    $exe.FullName
} finally {
    Pop-Location
}
