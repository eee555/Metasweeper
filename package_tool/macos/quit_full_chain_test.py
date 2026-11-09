"""全链路退出测试：忠实模拟 Cmd+Q 路径，实测 _cleanup 耗时。

启动完整的元扫雷主程序（源码模式），5 秒后触发 quit()（与 Cmd+Q 同路径：
aboutToQuit → GameServerBridge.stop → terminate 插件管理器 → wait），
测量 quit() 到事件循环返回的耗时。修复前该值恒为 5 秒（关闭卡顿根因）。

实现说明：子进程 stdout 直接写文件（不走管道），避免插件管理器子进程
继承管道读端导致外层永远等不到 EOF；测试结束时会清理全部残留进程。
通过 METASWEEPER_ZMQ_ENDPOINT 随机化端口，不与正在运行的实例冲突。
用法: QT_QPA_PLATFORM=offscreen .venv/bin/python package_tool/macos/quit_full_chain_test.py
"""
import os
import re
import subprocess
import sys
import time

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(TEST_DIR, "..", ".."))
SRC = os.path.join(ROOT, "src")

FAKE_MAIN = "/tmp/metasweeper_quit_full_chain"
INNER_LOG = "/tmp/metasweeper_quit_full_chain/inner.log"
os.makedirs(FAKE_MAIN, exist_ok=True)
policy_dst = os.path.join(FAKE_MAIN, "AI_AGENT_POLICY.md")
if not os.path.exists(policy_dst):
    subprocess.run(["cp", os.path.join(ROOT, "AI_AGENT_POLICY.md"),
                    policy_dst], check=True)

HOOK = r'''
import os
import threading
import time as _t
import PySide6.QtWidgets as _W


def _crit(*a, **k):
    # 离屏模式下模态弹窗会永久阻塞，改为打印内容并退出，让失败可见
    print("=== DIALOG ===", flush=True)
    print(a[2] if len(a) > 2 else repr(a), flush=True)
    print("=== END ===", flush=True)
    os._exit(3)


_W.QMessageBox.critical = _crit
_W.QMessageBox.warning = _crit

from PySide6.QtCore import QMetaObject, Qt as _Qt


def _quit_later():
    # 等 QApplication 就绪（主程序启动约需数秒），再从队列触发 quit，
    # 与 Cmd+Q 走完全相同的 aboutToQuit → _cleanup 路径
    app = None
    deadline = _t.monotonic() + 60
    while _t.monotonic() < deadline:
        app = _W.QApplication.instance()
        if app is not None:
            break
        _t.sleep(0.2)
    if app is None:
        print("TIMER: no QApplication", flush=True)
        os._exit(4)

    t0 = _t.monotonic()

    def on_about_to_quit():
        # main.py 的 _cleanup 先于本回调连接、先执行，耗时即清理耗时
        print(f"QUIT_CLEANUP_ELAPSED={_t.monotonic() - t0:.2f}", flush=True)

    app.aboutToQuit.connect(on_about_to_quit)
    print("TIMER: firing quit", flush=True)
    QMetaObject.invokeMethod(app, "quit", _Qt.ConnectionType.QueuedConnection)


threading.Thread(target=_quit_later, daemon=True).start()
'''

INNER = (
    "import os, sys, traceback; sys.argv = ['fake_main.py'];\n"
    f"exec({HOOK!r})\n"
    f"_src_main = {os.path.join(SRC, 'main.py')!r}\n"
    "try:\n"
    "    exec(compile(open(_src_main).read(), _src_main, 'exec'), "
    "{'__name__': '__main__', '__file__': _src_main})\n"
    "except SystemExit as e:\n"
    "    print(f'SYSEXIT={e.code}', flush=True)\n"
    "except BaseException:\n"
    "    traceback.print_exc()\n"
    "    sys.exit(2)\n"
)


def main() -> int:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_FONT_DPI"] = "96"
    env["PYTHONPATH"] = SRC
    env["METASWEEPER_ZMQ_ENDPOINT"] = (
        f"tcp://127.0.0.1:{os.getpid() % 20000 + 40000}")

    inner_log = open(INNER_LOG, "w")
    proc = subprocess.Popen(
        [os.path.join(ROOT, ".venv", "bin", "python"), "-u", "-c", INNER],
        cwd=FAKE_MAIN, env=env, stdout=inner_log, stderr=subprocess.STDOUT,
    )
    t_start = time.monotonic()
    timed_out = False
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        proc.wait()
    inner_log.close()

    # 清理插件管理器（无论主进程以何种方式退出）
    pgrep = subprocess.run(["pgrep", "-f", "python -m plugin_manager"],
                           capture_output=True, text=True)
    orphan_pids = [p for p in pgrep.stdout.split() if p.strip()]
    for pid in orphan_pids:
        subprocess.run(["kill", "-9", pid], capture_output=True)

    with open(INNER_LOG, encoding="utf-8", errors="replace") as f:
        log = f.read()
    quit_match = re.search(r"QUIT_CLEANUP_ELAPSED=([\d.]+)", log)

    print("--- 内部日志关键行 ---")
    for line in log.splitlines():
        if any(k in line for k in ("EXEC:", "TIMER:", "QUIT_CLEANUP",
                                   "=== DIALOG", "SYSEXIT", "Traceback",
                                   "Error", "capture guard")):
            print("  " + line[:160])
    print("---")

    if timed_out:
        print("[FAIL] 主程序 60 秒未退出")
        return 1
    if "SYSEXIT" not in log:
        print("[FAIL] 主程序异常退出（无 SYSEXIT），见上方日志")
        return 1
    if quit_match is None:
        print("[FAIL] 未捕获退出耗时")
        return 1

    elapsed = float(quit_match.group(1))
    print(f"[ok] quit() → _cleanup 完成，耗时 {elapsed:.2f} 秒")
    if orphan_pids:
        print(f"[FAIL] 插件管理器残留: {orphan_pids}")
        return 1
    print("[ok] 插件管理器无残留")
    ok = elapsed < 3.0
    print("\n全链路退出测试" + ("通过 ✅" if ok else "未达标 ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
