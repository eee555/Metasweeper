<#
.SYNOPSIS
    Strip debugpy/pydevd build artifacts from the merged Nuitka package.

.DESCRIPTION
    debugpy ships PDB symbols and generated Cython C/C++ sources. Only the
    compiled .pyd/.dll/.exe files are loaded at runtime, so these files are
    dead weight (~40 MB uncompressed). The debugpy Python package itself and
    its compiled extension modules are kept, so remote debugging still works.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $PackageDir
)

$ErrorActionPreference = 'Stop'
$packageRoot = (Resolve-Path -LiteralPath $PackageDir).Path

$debugDirectories = @(
    'debugpy',
    '_pydev_bundle',
    '_pydev_runfiles',
    '_pydevd_bundle',
    '_pydevd_frame_eval',
    '_pydevd_sys_monitoring',
    'pydev_ipython',
    'pydev_sitecustomize',
    'pydevd_attach_to_process',
    'pydevd_plugins'
)
$artifactExtensions = @('.pdb', '.c', '.pyx', '.cpp', '.h', '.exp', '.lib', '.a')

$removedCount = 0
$removedBytes = 0L
foreach ($name in $debugDirectories) {
    $directory = Join-Path $packageRoot $name
    if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
        continue
    }
    $files = Get-ChildItem -LiteralPath $directory -Recurse -File -Force |
        Where-Object { $artifactExtensions -contains $_.Extension }
    foreach ($file in $files) {
        $removedBytes += $file.Length
        Remove-Item -LiteralPath $file.FullName -Force
        $removedCount++
    }
}

Write-Host ('Stripped {0} debug symbol/source files ({1:N1} MB)' -f `
    $removedCount, ($removedBytes / 1MB))
