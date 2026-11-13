<#
.SYNOPSIS
    Create the Nuitka release zip from the merged package directory.

.DESCRIPTION
    Windows PowerShell 5.1's Compress-Archive has a 2 GB limit and skips
    hidden files. ZipFile.CreateFromDirectory avoids the size limit, but opens
    files without FileShare.ReadWrite|Delete. A running metasweeper.exe or
    plugin_manager.exe holds its log files open, which makes a rebuild of the
    zip fail with an IOException.

    This script enumerates the files itself and opens each one with shared
    read/delete access. Runtime data under data\logs and data\plugin_data is
    excluded from the release archive; the application recreates it on first
    run.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $PackageDir,
    [Parameter(Mandatory = $true)]
    [string] $ZipPath
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$packageRoot = [System.IO.Path]::GetFullPath($PackageDir)
$zipFullPath = [System.IO.Path]::GetFullPath($ZipPath)
if (-not [System.IO.Directory]::Exists($packageRoot)) {
    throw "Package directory not found: $packageRoot"
}

$zipDir = [System.IO.Path]::GetDirectoryName($zipFullPath)
if (-not [System.IO.Directory]::Exists($zipDir)) {
    [System.IO.Directory]::CreateDirectory($zipDir) | Out-Null
}
if ([System.IO.File]::Exists($zipFullPath)) {
    [System.IO.File]::Delete($zipFullPath)
}

$tempZipPath = $zipFullPath + '.tmp'
if ([System.IO.File]::Exists($tempZipPath)) {
    [System.IO.File]::Delete($tempZipPath)
}

$share = [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
$zipStream = $null
$archive = $null
try {
    $zipStream = [System.IO.File]::Open(
        $tempZipPath,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::Read
    )
    $archive = New-Object System.IO.Compression.ZipArchive(
        $zipStream,
        [System.IO.Compression.ZipArchiveMode]::Create,
        $false
    )

    $debugArtifactExtensions = @(
        '.pdb', '.c', '.pyx', '.cpp', '.h', '.exp', '.lib', '.a'
    )
    $files = Get-ChildItem -LiteralPath $packageRoot -Recurse -File -Force
    foreach ($file in $files) {
        $relativePath = $file.FullName.Substring($packageRoot.Length + 1)
        $normalized = $relativePath.Replace('\', '/')
        if ($normalized -match '^data/(logs|plugin_data)/') {
            continue
        }
        # debugpy/pydevd carry symbols and generated sources that are never
        # loaded at runtime; keep them out of the release archive.
        if ($normalized -match '^(debugpy|_pydev|_pydevd|pydev|pydevd)' -and
            $debugArtifactExtensions -contains $file.Extension) {
            continue
        }
        if ($normalized -match '(^|/)__pycache__/') {
            continue
        }

        $source = $null
        try {
            $source = [System.IO.File]::Open(
                $file.FullName,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::Read,
                $share
            )
            $entry = $archive.CreateEntry(
                $normalized,
                [System.IO.Compression.CompressionLevel]::Optimal
            )
            $target = $entry.Open()
            try {
                $source.CopyTo($target)
            }
            finally {
                $target.Dispose()
            }
        }
        finally {
            if ($null -ne $source) {
                $source.Dispose()
            }
        }
    }

    $archive.Dispose()
    $archive = $null
    $zipStream.Dispose()
    $zipStream = $null

    [System.IO.File]::Move($tempZipPath, $zipFullPath)
}
finally {
    if ($null -ne $archive) {
        $archive.Dispose()
    }
    if ($null -ne $zipStream) {
        $zipStream.Dispose()
    }
    if ([System.IO.File]::Exists($tempZipPath)) {
        [System.IO.File]::Delete($tempZipPath)
    }
}

if (-not [System.IO.File]::Exists($zipFullPath)) {
    throw "Release zip archive was not created: $zipFullPath"
}
Write-Host "Created $zipFullPath"
