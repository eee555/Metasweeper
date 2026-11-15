# Tests

Test modules are grouped by the subsystem they exercise:

- `game/`: game UI, engine, and startup behavior
- `networking/`: ZMQ client, server, and lifecycle behavior
- `plugin_manager/`: plugin manager UI, loading, settings, and process behavior
- `plugin_sdk/`: SDK lifecycle, service, and configuration APIs
- `plugins/`: individual plugins, queries, and regression findings
- `replay/`: replay import, storage, and playback behavior
- `shared_types/`: shared protocol types, widgets, and sound helpers
- `utils/`: utility functions and startup refactoring checks

Run the full suite with `python -m pytest tests/`. Pytest discovers test modules recursively.
