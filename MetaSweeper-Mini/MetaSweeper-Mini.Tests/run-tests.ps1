[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$projectDirectory = $PSScriptRoot
$projectFile = Join-Path $projectDirectory 'MetaSweeper-Mini.Tests.csproj'
$settingsFile = Join-Path $projectDirectory 'coverage.runsettings'
$runName = Get-Date -Format 'yyyyMMdd-HHmmssfff'
$resultsDirectory = Join-Path $projectDirectory "TestResults\$runName"
$coverageDirectory = Join-Path $projectDirectory 'coverage'
$coverageDestination = Join-Path $coverageDirectory 'coverage.cobertura.xml'

New-Item -ItemType Directory -Path $resultsDirectory -Force | Out-Null

Push-Location $projectDirectory
try {
    & dotnet test $projectFile -c Release --collect:"XPlat Code Coverage" --results-directory $resultsDirectory --settings $settingsFile
    $testExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

if ($testExitCode -ne 0) {
    throw "dotnet test failed with exit code $testExitCode."
}

$coverageSource = Get-ChildItem -LiteralPath $resultsDirectory -Filter 'coverage.cobertura.xml' -File -Recurse |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1

if ($null -eq $coverageSource) {
    throw "No coverage.cobertura.xml was produced under '$resultsDirectory'."
}

New-Item -ItemType Directory -Path $coverageDirectory -Force | Out-Null
Copy-Item -LiteralPath $coverageSource.FullName -Destination $coverageDestination -Force

[xml]$coverageReport = Get-Content -LiteralPath $coverageDestination -Raw
$lineRate = $coverageReport.coverage.GetAttribute('line-rate')
$branchRate = $coverageReport.coverage.GetAttribute('branch-rate')

Write-Output "Coverage source: $($coverageSource.FullName)"
Write-Output "Coverage copy: $coverageDestination"
Write-Output "Line rate: $lineRate"
Write-Output "Branch rate: $branchRate"
