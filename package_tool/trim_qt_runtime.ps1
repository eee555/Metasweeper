param(
    [Parameter(Mandatory = $true)][string]$PackageDir,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$package = (Resolve-Path $PackageDir).Path
$qtRuntime = $package
$pysideRoot = Join-Path $package 'PySide6'
if (Test-Path -LiteralPath (Join-Path $package '_internal\PySide6')) {
    $qtRuntime = Join-Path $package '_internal\PySide6'
    $pysideRoot = $qtRuntime
}
$qtPlugins = Join-Path $pysideRoot 'plugins'
if (Test-Path -LiteralPath (Join-Path $pysideRoot 'qt-plugins')) {
    $qtPlugins = Join-Path $pysideRoot 'qt-plugins'
}
$dumpbin = Get-Command dumpbin.exe -ErrorAction SilentlyContinue
if (-not $dumpbin) {
    throw 'dumpbin.exe not found. Run from the Visual Studio developer environment.'
}
$unusedDirectories = @(@(
    (Join-Path $pysideRoot 'qml')
    (Join-Path $qtPlugins 'qmltooling')
    (Join-Path $qtPlugins 'multimedia')
) | Where-Object { Test-Path -LiteralPath $_ -PathType Container })
# 本地源码可能保留已删除统计插件的 __pycache__，目录复制会将其带入包中。
$unusedDirectories += @('plugins\stats', '_internal\plugins\stats', 'internal\plugins\stats' | ForEach-Object {
    $directory = Join-Path $package $_
    if (Test-Path -LiteralPath $directory -PathType Container) { $directory }
})
# Plugins for features omitted from the Windows build.
$unusedPaths = @(
    (Join-Path $qtPlugins 'platforminputcontexts\qtvirtualkeyboardplugin.dll')
    (Join-Path $qtPlugins 'imageformats\qpdf.dll')
)
$qtTranslations = Join-Path $pysideRoot 'translations'
$unusedFiles = @($unusedPaths | ForEach-Object {
    if (Test-Path -LiteralPath $_ -PathType Leaf) { Get-Item -LiteralPath $_ }
})
if (Test-Path -LiteralPath $qtTranslations -PathType Container) {
    $unusedFiles += @(Get-ChildItem -LiteralPath $qtTranslations -File -Filter '*.qm' | Where-Object {
        $_.Name -match '^qtmultimedia_' -or $_.BaseName -notmatch '_(zh(_(CN|TW))?|en(_(US|GB))?|de(_DE)?|pl(_PL)?|ja(_JP)?)$'
    })
}
$excludedFiles = @{}
foreach ($file in $unusedFiles) { $excludedFiles[$file.FullName] = $true }
foreach ($directory in $unusedDirectories) {
    Get-ChildItem -LiteralPath $directory -Recurse -File | ForEach-Object { $excludedFiles[$_.FullName] = $true }
}
$files = @(Get-ChildItem $package -Recurse -File | Where-Object {
    $_.Extension -in '.exe', '.dll', '.pyd' -and -not $excludedFiles.ContainsKey($_.FullName)
})
$candidates = @{}
foreach ($file in $files) {
    # Qt can load this software OpenGL fallback dynamically. Omit it from Windows releases.
    if ($file.DirectoryName -eq $qtRuntime -and $file.Name -eq 'opengl32sw.dll') {
        $candidates[$file.Name.ToLowerInvariant()] = $file
        continue
    }
    if ($file.DirectoryName -eq $qtRuntime -and ($file.Name -match '^qt6(3d|quick|qml|charts|virtualkeyboard|graphs|datavisualization|pdf|multimedia|opengl|location|positioning|remoteobjects|scxml|sensors|texttospeech|spatialaudio|test|webengine|webchannel|websockets|webview).*\.dll$' -or $file.Name -match '^(avcodec|avformat|avutil|swscale|swresample)-\d+\.dll$')) {
        $candidates[$file.Name.ToLowerInvariant()] = $file
    }
}
$imports = @{}
foreach ($file in $files) {
    $output = & $dumpbin.Source /NOLOGO /DEPENDENTS $file.FullName 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Cannot inspect $($file.FullName): $output" }
    $imports[$file.FullName] = @($output | ForEach-Object {
            if ($_ -match '^\s+([\w.\-]+\.dll)\s*$') { $Matches[1].ToLowerInvariant() }
        })
}
$removable = @{}
foreach ($name in $candidates.Keys) { $removable[$name] = $true }
do {
    $changed = $false
    foreach ($file in $files) {
        if ($file.DirectoryName -eq $qtRuntime -and $removable.ContainsKey($file.Name.ToLowerInvariant())) { continue }
        foreach ($dependency in $imports[$file.FullName]) {
            if ($removable.ContainsKey($dependency)) {
                $removable.Remove($dependency)
                $changed = $true
            }
        }
    }
} while ($changed)
# Validate recursive targets and reject junctions before deleting any directory.
$packagePrefix = $package.TrimEnd('\') + '\'
foreach ($directory in $unusedDirectories) {
    $target = Get-Item -LiteralPath $directory
    if (-not $target.FullName.StartsWith($packagePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Qt trim directory is outside the package: $directory"
    }
    while ($target.FullName.StartsWith($packagePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        if ($target.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Qt trim directory crosses a junction or link: $($target.FullName)"
        }
        $target = $target.Parent
    }
}
$removedBytes = 0L
foreach ($directory in $unusedDirectories) {
    $removedBytes += (Get-ChildItem -LiteralPath $directory -Recurse -File | Measure-Object Length -Sum).Sum
    Write-Output ('Unused directory: {0}' -f $directory)
    if ($Apply) { Remove-Item -LiteralPath $directory -Recurse -Force }
}
foreach ($file in $unusedFiles) {
    $removedBytes += $file.Length
    Write-Output ('Unused Qt file: {0}' -f $file.FullName)
    if ($Apply) { Remove-Item -LiteralPath $file.FullName -Force }
}
foreach ($name in @($removable.Keys | Sort-Object)) {
    $file = $candidates[$name]
    $removedBytes += $file.Length
    Write-Output ('{0} {1:N2} MiB' -f $file.Name, ($file.Length / 1MB))
    if ($Apply) { Remove-Item -LiteralPath $file.FullName -Force }
}
Write-Output ('Removable Qt DLLs: {0}; unused directories: {1}; total size: {2:N2} MiB; applied: {3}' -f $removable.Count, $unusedDirectories.Count, ($removedBytes / 1MB), $Apply.IsPresent)
if ($Apply) {
    $remaining = @(Get-ChildItem -LiteralPath $qtRuntime -File | Where-Object {
        $_.Name -match '^(Qt6(Qml|Quick|Charts|VirtualKeyboard).*\.dll|Qt(Qml|Quick|QuickWidgets|Charts)\.pyd)$'
    })
    if ($remaining.Count) {
        throw ('QML runtime is still required by retained binaries: {0}' -f ($remaining.Name -join ', '))
    }
}
