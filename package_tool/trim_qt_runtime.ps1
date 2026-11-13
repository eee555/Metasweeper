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
) | Where-Object { Test-Path -LiteralPath $_ -PathType Container })
# 本地源码可能保留已删除统计插件的 __pycache__，目录复制会将其带入包中。
$unusedDirectories += @('plugins\stats', '_internal\plugins\stats', 'internal\plugins\stats' | ForEach-Object {
    $directory = Join-Path $package $_
    if (Test-Path -LiteralPath $directory -PathType Container) { $directory }
})
# Qt 自动收集的屏幕虚拟键盘使用 QML；保留其他输入法插件。
$unusedPluginPaths = @((Join-Path $qtPlugins 'platforminputcontexts\qtvirtualkeyboardplugin.dll'))
# Qt 可能收集 PDF 图像插件，却未分发它依赖的 Qt6Pdf.dll。
if (-not (Test-Path -LiteralPath (Join-Path $qtRuntime 'Qt6Pdf.dll'))) {
    $unusedPluginPaths += Join-Path $qtPlugins 'imageformats\qpdf.dll'
}
$unusedFiles = @($unusedPluginPaths | ForEach-Object {
    if (Test-Path -LiteralPath $_ -PathType Leaf) { Get-Item -LiteralPath $_ }
})
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
    if ($file.DirectoryName -eq $qtRuntime -and $file.Name -match '^qt6(3d|quick|qml|charts|virtualkeyboard|graphs|datavisualization|pdf|multimedia|location|positioning|remoteobjects|scxml|sensors|texttospeech|spatialaudio|test|webengine|webchannel|websockets|webview).*\.dll$') {
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
$removedBytes = 0L
foreach ($directory in $unusedDirectories) {
    $removedBytes += (Get-ChildItem -LiteralPath $directory -Recurse -File | Measure-Object Length -Sum).Sum
    Write-Output ('Unused directory: {0}' -f $directory)
    if ($Apply) { Remove-Item -LiteralPath $directory -Recurse -Force }
}
foreach ($file in $unusedFiles) {
    $removedBytes += $file.Length
    Write-Output ('Unused Qt plugin: {0}' -f $file.FullName)
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