param(
    [Parameter(Mandatory)][string]$WorkDir,
    [Parameter(Mandatory)][string]$ResourceDir,
    [string]$PythonPath,
    [switch]$Offline
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
$revision = (Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'ms-toollib.rev')).Trim()
$obj = Join-Path $PSScriptRoot '../../obj'
New-Item -ItemType Directory -Path $obj -Force | Out-Null
$library = Join-Path $obj 'ms-toollib'
$git = (Get-Command git.exe -ErrorAction SilentlyContinue).Source
if (-not $git) { throw 'Git for Windows must be available on PATH to prepare ms_toollib.' }

function Invoke-DependencyGit {
    & $git -C $library @args
    if ($LASTEXITCODE) { throw "Could not prepare ms_toollib at $revision (Git exit code $LASTEXITCODE)." }
}

$current = $null
if (Test-Path -LiteralPath (Join-Path $library '.git')) {
    $current = & $git -C $library rev-parse --verify --quiet HEAD
}
if ($current -ne $revision -or -not (Test-Path -LiteralPath (Join-Path $library 'base/Cargo.toml')) -or
    -not (Test-Path -LiteralPath (Join-Path $library 'LICENSE'))) {
    if ($Offline) { throw "ms_toollib $revision is not cached. Run the first build with network access." }
    New-Item -ItemType Directory -Path $library -Force | Out-Null
    Invoke-DependencyGit init --quiet
    Invoke-DependencyGit fetch --quiet --no-tags --depth=1 'https://github.com/eee555/ms-toollib.git' $revision
    Invoke-DependencyGit checkout --quiet --detach $revision
}
if (& $git -C $library status --porcelain --untracked-files=all) {
    throw "The cached ms_toollib checkout has local changes. Move it out of obj and rebuild to restore $revision."
}
if ($LASTEXITCODE) { throw 'Could not verify the cached ms_toollib checkout.' }
$libraryBase = (Resolve-Path -LiteralPath (Join-Path $library 'base')).Path.Replace('\', '/')
if (-not (Test-Path -LiteralPath (Join-Path $libraryBase 'Cargo.toml'))) {
    throw 'The ms_toollib checkout must contain base/Cargo.toml.'
}
New-Item -ItemType Directory -Path $ResourceDir -Force | Out-Null
$native = $WorkDir

$shim = Join-Path $native 'src'
$manifest = Join-Path $native 'Cargo.toml'
New-Item -ItemType Directory -Path $shim -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot '../Native/native.rs') -Destination (Join-Path $shim 'lib.rs')

$manifestText = @"
[package]
name = "mines_core"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib"]

[dependencies]
ms_toollib = { path = "$libraryBase", default-features = false, features = ["rs"] }

[profile.release]
opt-level = "z"
lto = true
codegen-units = 1
panic = "abort"
strip = true
"@
[IO.File]::WriteAllText($manifest, $manifestText, (New-Object Text.UTF8Encoding($false)))

$rustFlags = $env:RUSTFLAGS
try {
    # Link the Visual C runtime statically and use the system's Universal CRT.
    $env:RUSTFLAGS = '-C target-feature=+crt-static -C link-arg=/NODEFAULTLIB:libucrt.lib -C link-arg=ucrt.lib'
    $cargoArguments = @('build', '--release', '--manifest-path', $manifest)
    if ($Offline) {
        $cargoArguments += '--offline'
    }
    $cargo = (Get-Command cargo.exe -ErrorAction SilentlyContinue).Source
    if (-not $cargo) { $cargo = Join-Path $env:USERPROFILE '.cargo/bin/cargo.exe' }
    & $cargo @cargoArguments
    if ($LASTEXITCODE) {
        throw "Rust build exited with code $LASTEXITCODE."
    }
} finally {
    $env:RUSTFLAGS = $rustFlags
}

$nativeDll = Join-Path $native 'target/release/mines_core.dll'
$resource = Join-Path $ResourceDir 'mines_core.lzms'
$inputStream = [IO.File]::OpenRead($nativeDll)
try {
    $reader = New-Object IO.BinaryReader($inputStream)
    $inputStream.Position = 0x3c
    $inputStream.Position = $reader.ReadInt32() + 4
    if ($reader.ReadUInt16() -ne 0x8664) {
        throw 'Build with the x86_64-pc-windows-msvc Rust toolchain.'
    }
} finally { $inputStream.Dispose() }

if (-not $PythonPath) {
    $PythonPath = Join-Path $repo '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $PythonPath)) {
        $PythonPath = 'python'
    }
}
$media = Join-Path $repo 'src/media'
$sprites = Join-Path $ResourceDir 'classic-shapes.bin'
$countries = Join-Path $ResourceDir 'countries.deflate'
& $PythonPath (Join-Path $PSScriptRoot 'build_resources.py') $media $sprites $nativeDll $resource $countries
if ($LASTEXITCODE) {
    throw 'Failed to generate the drawing commands and compressed native library.'
}

Copy-Item -LiteralPath (Join-Path $library 'LICENSE') -Destination (Join-Path $ResourceDir 'ms_toollib-LICENSE') -Force
