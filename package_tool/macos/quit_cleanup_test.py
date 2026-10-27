"""验证插件管理器退出兜底逻辑：terminate 超时后升级 kill，异常不外泄。

复现 main.py _cleanup 的真实场景（macOS 下 SIGTERM 优雅关闭依赖
插件管理器的 Qt 事件循环，可能永不执行）。
用法: QT_QPA_PLATFORM=offscreen .venv/bin/python package_tool/macos/quit_cleanup_test.py
"""
import os
import subprocess
import sys
import time

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(TEST_DIR, "..", ".."))
SRC = os.path.join(ROOT, "src")
DATA_DIR = "/tmp/metasweeper_quit_test"
os.makedirs(DATA_DIR, exist_ok=True)


def manager_alive(proc) -> bool:
    return proc.poll() is None


def main() -> int:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = SRC
    proc = subprocess.Popen(
        [sys.executable, "-m", "plugin_manager", "--mode", "tray",
         "--data-dir", DATA_DIR],
        cwd=SRC, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(8)  # 等插件管理器完全启动
    if not manager_alive(proc):
        print(f"[FAIL] 插件管理器提前退出: {proc.returncode}")
        return 1
    print("[ok] 插件管理器已启动并稳定运行")

    # ── 验证 SIGTERM 直接优雅退出（关闭不卡顿的关键） ──
    start = time.monotonic()
    proc.terminate()
    escalated = False
    try:
        proc.wait(timeout=5)
        elapsed = time.monotonic() - start
        print(f"[ok] SIGTERM 直接退出（{elapsed:.2f} 秒，无需升级）")
    except subprocess.TimeoutExpired:
        escalated = True
        elapsed = time.monotonic() - start
        print(f"[FAIL] SIGTERM 5 秒未退出（{elapsed:.2f} 秒），需升级 kill ——"
              "主程序关闭将卡顿 5 秒")
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("[FAIL] SIGKILL 后仍未退出")
            return 1

    if manager_alive(proc):
        print("[FAIL] 进程仍存活")
        return 1
    if escalated:
        return 1
    print(f"\n退出验证通过 ✅（优雅退出耗时 {elapsed:.2f} 秒，退出码 {proc.returncode}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
