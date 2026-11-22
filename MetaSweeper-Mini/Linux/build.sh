#!/usr/bin/env bash
set -euo pipefail
linux="$(cd "$(dirname "$0")" && pwd)"
mini="$(dirname "$linux")"
cache="$mini/obj/ms-toollib"
revision="$(tr -d '\r\n' < "$mini/win/Build/ms-toollib.rev")"
if [[ ! -d "$cache/.git" ]]; then
    mkdir -p "$cache"
    git -C "$cache" init -q
fi
if [[ "$(git -C "$cache" rev-parse --verify HEAD 2>/dev/null || true)" != "$revision" ]]; then
    git -C "$cache" diff --quiet
    git -C "$cache" diff --cached --quiet
    git -C "$cache" fetch -q --no-tags --depth=1 https://github.com/eee555/ms-toollib.git "$revision"
    git -C "$cache" checkout -q --detach "$revision"
fi
if [[ -n "$(git -C "$cache" status --porcelain)" ]]; then
    echo "The pinned ms_toollib checkout has local changes: $cache" >&2
    exit 1
fi

export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$mini/obj/linux-sdl3}"
cd "$linux"
cargo build --locked --release "$@"
mkdir -p "$mini/../dist/linux-sdl3"
install -m 755 "$CARGO_TARGET_DIR/release/MetaSweeper-Mini" "$mini/../dist/linux-sdl3/MetaSweeper-Mini"
wc -c "$mini/../dist/linux-sdl3/MetaSweeper-Mini"
