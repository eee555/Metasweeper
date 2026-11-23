import argparse
import subprocess
from pathlib import Path


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


if __name__ == "__main__":
    main()
