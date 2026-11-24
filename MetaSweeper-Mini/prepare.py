import argparse
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path


def prepare_mini_library(cache, revision, patch):
    target = cache.with_name("ms-toollib-mini")
    stamp = f"{revision}\n{hashlib.sha256(patch.read_bytes()).hexdigest()}\n"
    stamp_file = target / "revision"

    def ready():
        if target.resolve() != cache.parent.resolve() / target.name:
            raise ValueError(f"Mini dependency directory resolves outside the build cache: {target}")
        return ((target / "base" / "Cargo.toml").is_file() and stamp_file.is_file()
                and stamp_file.read_text(encoding="ascii") == stamp)

    if ready():
        return

    with tempfile.TemporaryDirectory(dir=cache.parent, prefix="mini-library-") as temporary:
        scratch = Path(temporary)
        source = scratch / "source"
        source.mkdir()
        files = subprocess.check_output(
            ["git", "-C", str(cache), "ls-files", "-z", "--", "base"], text=True,
            encoding="utf-8",
        ).split("\0")
        for name in filter(None, files):
            destination = source / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cache / name, destination)
        subprocess.run(["git", "init", "--quiet"], cwd=source, check=True)
        subprocess.run(
            ["git", "apply", "--recount", str(patch)], cwd=source, check=True,
        )
        (source / "revision").write_text(stamp, encoding="ascii")
        if ready():
            return
        previous = scratch / "previous"
        if target.exists():
            target.rename(previous)
        try:
            source.rename(target)
        except OSError:
            if ready():
                return
            if previous.exists():
                previous.rename(target)
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    mini = Path(__file__).resolve().parent
    cache = mini / "obj" / "ms-toollib"
    revision = (mini / "ms-toollib.rev").read_text(encoding="ascii").strip()

    def git(*arguments, check=True):
        return subprocess.run(
            ["git", "-C", str(cache), *arguments], check=check,
            stdout=subprocess.PIPE, text=True,
        ).stdout.strip()

    if not (cache / ".git").exists():
        if args.offline:
            parser.exit(1, f"ms_toollib is not cached at {cache}\n")
        cache.mkdir(parents=True, exist_ok=True)
        git("init", "--quiet")
    if git("status", "--porcelain", "--untracked-files=all"):
        parser.exit(1, f"The ms_toollib checkout has local changes: {cache}\n")
    if git("rev-parse", "--verify", "--quiet", "HEAD", check=False) != revision:
        if args.offline:
            parser.exit(1, f"ms_toollib revision {revision} is not checked out at {cache}\n")
        git("fetch", "--quiet", "--no-tags", "--depth=1", "https://github.com/eee555/ms-toollib.git", revision)
        git("checkout", "--quiet", "--detach", revision)
    if not (cache / "base" / "Cargo.toml").is_file() or not (cache / "LICENSE").is_file():
        parser.exit(1, f"The ms_toollib checkout is incomplete: {cache}\n")
    prepare_mini_library(cache, revision, mini / "ms-toollib-mini.patch")


if __name__ == "__main__":
    main()
