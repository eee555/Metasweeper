param(
    [string]$OutputPath,
    [string]$PythonPath,
    [switch]$Offline
)

$ErrorActionPreference = 'Stop'
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$msbuild = $null
if (Test-Path -LiteralPath $vswhere) {
    $msbuild = & $vswhere -latest -products '*' -requires Microsoft.Component.MSBuild -find 'MSBuild\**\Bin\MSBuild.exe' | Select-Object -First 1
}
if (-not $msbuild) {
    $msbuild = (Get-Command MSBuild.exe -ErrorAction SilentlyContinue).Source
}
if (-not $msbuild) {
    throw 'Visual Studio MSBuild was not found.'
}

$project = Join-Path $PSScriptRoot 'MetaSweeper-Mini.sln'
$arguments = @($project, '/nologo', '/m', '/t:Build', '/p:Configuration=Release', '/p:Platform=x64')
if ($PythonPath) { $arguments += "/p:PythonPath=$PythonPath" }
if ($Offline) { $arguments += '/p:ResourceOffline=true' }
& $msbuild @arguments
if ($LASTEXITCODE) {
    throw "MSBuild exited with code $LASTEXITCODE."
}

if (-not $OutputPath) {
    $OutputPath = Join-Path $PSScriptRoot '../dist/winforms-prototype/MetaSweeper-Mini.exe'
}
$OutputPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputPath)
New-Item -ItemType Directory -Path (Split-Path -Parent $OutputPath) -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'bin/x64/Release/MetaSweeper-Mini.exe') -Destination $OutputPath -Force
Get-Item -LiteralPath $OutputPath
