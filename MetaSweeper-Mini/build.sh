#!/usr/bin/env bash
set -euo pipefail
mini="$(cd "$(dirname "$0")" && pwd)"
prepare_args=("$mini/prepare.py")
for arg in "$@"; do
    if [[ "$arg" == --offline || "$arg" == --frozen ]]; then
        prepare_args+=(--offline)
        break
    fi
done
"${MINI_PYTHON:-python3}" "${prepare_args[@]}"

export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$mini/obj/linux-sdl3}"
cd "$mini"
cargo build --locked --release "$@"
mkdir -p "$mini/../dist/linux-sdl3"
install -m 755 "$CARGO_TARGET_DIR/release/MetaSweeper-Mini" "$mini/../dist/linux-sdl3/MetaSweeper-Mini"
wc -c "$mini/../dist/linux-sdl3/MetaSweeper-Mini"
