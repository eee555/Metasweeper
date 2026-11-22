# Configuration and replay checksum tests

Run the tests from this directory:

```powershell
.\run-tests.ps1
```

If local script execution is disabled, run the same script for the current process only:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run-tests.ps1
```

The script builds and tests `MetaSweeper-Mini.Tests.csproj` in Release configuration, collects coverage through the XPlat Code Coverage data collector, and prints the overall line and branch rates. Each invocation uses a timestamped directory under `TestResults`, so a previous report cannot be mistaken for the latest one.

Coverlet writes the raw Cobertura report under `TestResults` using a generated GUID directory. The script copies the newest report from the current run to:

```text
coverage\coverage.cobertura.xml
```

`line-rate` and `branch-rate` are decimal fractions. Multiply them by 100 to get percentages, so `0.875` means 87.5 percent. The same attributes appear in the copied Cobertura report, which can be opened by coverage report viewers or uploaded to a coverage service.

## Coverage scope

`coverage.runsettings` enables coverage for the test assembly because the production configuration and checksum files are linked into that assembly. The Coverlet include filters select these classes:

```text
[MetaSweeper-Mini.Tests]ReplayChecksum
[MetaSweeper-Mini.Tests]GameSettings
[MetaSweeper-Mini.Tests]IniFile
[MetaSweeper-Mini.Tests]LocalFiles
[MetaSweeper-Mini.Tests]ShortcutCatalog
```

Compiler-generated members are excluded through `GeneratedCodeAttribute` and `CompilerGeneratedAttribute`, and auto-property accessors are skipped.

The tests cover checksum verification, malformed replay input, generated configuration keys, compatibility with an existing MetaSweeper `gameSetting.ini`, portable replay paths, fixed shortcut definitions and persisted window state. `ReplayChecksum` remains at 100 percent line and branch coverage.

Because `EnableDefaultCompileItems` is false, every test source file must have an explicit `Compile` entry in `MetaSweeper-Mini.Tests.csproj`.

To run the equivalent test command directly without the report copy and rate summary:

```powershell
dotnet test .\MetaSweeper-Mini.Tests.csproj -c Release --collect:"XPlat Code Coverage" --results-directory .\TestResults\manual --settings .\coverage.runsettings
```
