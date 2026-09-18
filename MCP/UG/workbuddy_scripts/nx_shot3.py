# -*- coding: utf-8 -*-
"""截取 NX 图形窗口（保证不被其它窗口遮挡）。

做法：
1. 枚举可见的顶层窗口，把除 NX 与系统外壳（桌面/任务栏）之外的窗口全部临时隐藏；
2. NX 窗口显式设为全屏 + TOPMOST + 前台；
3. 发两次 Esc 取消导入后的选中高亮（否则实体显示为红色）；
4. 按 NX 窗口矩形裁剪截图；
5. 恢复所有被隐藏的窗口。

用法: python nx_shot3.py <out.png>
"""
import ctypes
import ctypes.wintypes as wt
import sys
import time

from PIL import ImageGrab

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
SW_HIDE = 0
SW_SHOW = 5
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_SHOWWINDOW = 0x0040
VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x0002
PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

SHELL_CLASSES = (
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow", "ApplicationFrameWindow_Cloaked",
)


def list_windows():
    wins = []

    def _cb(hwnd, lparam):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            cbuf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cbuf, 256)
            wins.append((hwnd, buf.value, cbuf.value, bool(user32.IsWindowVisible(hwnd))))
        return True

    user32.EnumWindows(PROC(_cb), 0)
    return wins


def tap_esc(times=2):
    for _ in range(times):
        user32.keybd_event(VK_ESCAPE, 0, 0, 0)
        user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.25)


def is_browser(title, cls):
    t = title.lower()
    c = cls.lower()
    return ("chrome" in c or "chrome" in t or "edge" in c
            or "firefox" in c or "msedge" in c)


def main():
    wins = list_windows()
    nx = None
    for hwnd, title, cls, vis in wins:
        if vis and title.startswith("NX") and not is_browser(title, cls):
            nx = (hwnd, title)
            break
    if nx is None:
        for hwnd, title, cls, vis in wins:
            if vis and ("NX" in title) and not is_browser(title, cls) \
                    and (("建模" in title) or (".prt" in title) or ("基本环境" in title)):
                nx = (hwnd, title)
                break
    if nx is None:
        for hwnd, title, cls, vis in wins:
            if vis and ("NX" in title) and not is_browser(title, cls) \
                    and not title.lower().endswith("- google chrome"):
                nx = (hwnd, title)
                break
    if nx is None:
        print("NO_NX_WINDOW")
        return 1

    hidden = []
    for hwnd, title, cls, vis in wins:
        if not vis or hwnd == nx[0]:
            continue
        if cls in SHELL_CLASSES:
            continue
        user32.ShowWindow(hwnd, SW_HIDE)
        hidden.append((hwnd, title))
    print("nx:", nx)
    print("hidden_count:", len(hidden))
    for h, t in hidden[:12]:
        print("   hide:", t[:60])

    hwnd, title = nx
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, sw, sh, SWP_SHOWWINDOW)
    user32.SetForegroundWindow(hwnd)
    time.sleep(2.2)
    tap_esc(2)
    time.sleep(0.8)

    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    bbox = (rect.left, rect.top, rect.right, rect.bottom)
    print("rect:", bbox)
    img = ImageGrab.grab(bbox=bbox)
    out = sys.argv[1] if len(sys.argv) > 1 else r"E:\workbuddy-成果\2026-09-15-12-10-47\nx_view.png"
    img.save(out)
    print("saved", out, img.size)

    for h, t in hidden:
        user32.ShowWindow(h, SW_SHOW)
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0040)
    print("restored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
