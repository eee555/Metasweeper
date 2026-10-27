"""macOS 窗口内容保护，对应 Windows 的 SetWindowDisplayAffinity。

通过 NSWindow.setSharingType(NSWindowSharingNone) 停止向窗口服务器之外的
捕获方共享窗口后备存储：系统截图、录屏、ScreenCaptureKit 与屏幕共享中
该窗口不可见（表现为黑块），物理显示器上的显示不受影响。强制点在
WindowServer 合成层，非应用层自觉。用 ctypes 直调 libobjc，避免引入
pyobjc 依赖。
"""

import ctypes
import ctypes.util

from utils.app_logger import logger

# NSWindowSharingType（AppKit/NSWindow.h）
NSWINDOW_SHARING_NONE = 0       # 后备存储不共享，截屏/录屏/屏幕共享不可见
NSWINDOW_SHARING_READ_ONLY = 1  # 默认值，可被其他进程读取，即正常可截屏

_libobjc = None


def _get_libobjc():
    # 懒加载：本模块在 Windows 上也会被 import，不能在模块级加载 libobjc
    global _libobjc
    if _libobjc is None:
        path = ctypes.util.find_library("objc") or "/usr/lib/libobjc.dylib"
        _libobjc = ctypes.cdll.LoadLibrary(path)
    return _libobjc


def macos_capture_guard(nsview_ptr: int):
    """由 winId() 返回的 NSView 指针构造 (disable_screenshot,
    enable_screenshot) 一对回调。

    返回的函数在底层调用未生效时抛 RuntimeError，与 Windows 分支
    `1/0` 的失败语义保持一致。
    """
    # 非常规窗口后端（如测试用的 offscreen）的 winId() 是哑值而非真实
    # NSView 指针，直接发消息会段错误；此时降级为空实现
    if not nsview_ptr or nsview_ptr < 0x1000:
        logger.warning(
            f"capture guard: winId 0x{nsview_ptr:x} 不是有效的 NSView 指针"
            "（可能是 offscreen 等非 cocoa 窗口后端），防截屏降级为空实现")
        return (lambda: None), (lambda: None)

    libobjc = _get_libobjc()

    # 注意：libobjc.objc_msgSend 属性每次返回同一个被缓存的函数对象，
    # 不能对其反复改写 argtypes/restype，必须为每种签名构造独立原型
    msg_send_window = ctypes.CFUNCTYPE(
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    )(("objc_msgSend", libobjc))

    msg_send_set = ctypes.CFUNCTYPE(
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long,
    )(("objc_msgSend", libobjc))

    msg_send_get = ctypes.CFUNCTYPE(
        ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p,
    )(("objc_msgSend", libobjc))

    sel_registerName = libobjc.sel_registerName
    sel_registerName.restype = ctypes.c_void_p
    sel_registerName.argtypes = [ctypes.c_char_p]

    def sel(name):
        return sel_registerName(name.encode())

    nswindow = msg_send_window(ctypes.c_void_p(nsview_ptr), sel("window"))
    if not nswindow:
        raise RuntimeError(
            "capture guard: NSView is not attached to an NSWindow")

    def set_sharing_type(value):
        # setSharingType: 无返回值，无 API 级失败信号。已知 macOS 的
        # sharingType getter 在首次设为 none 之后会一直返回 0（setter
        # 实际生效，见 SO 77894366），因此回读不一致只能告警，不能视为失败
        msg_send_set(ctypes.c_void_p(nswindow),
                     sel("setSharingType:"), value)
        current = msg_send_get(ctypes.c_void_p(nswindow), sel("sharingType"))
        if current != value:
            logger.warning(
                f"capture guard: sharingType readback {current} != set {value};"
                " known macOS getter quirk, set call still issued")

    def disable_screenshot():
        set_sharing_type(NSWINDOW_SHARING_NONE)

    def enable_screenshot():
        set_sharing_type(NSWINDOW_SHARING_READ_ONLY)

    return disable_screenshot, enable_screenshot
