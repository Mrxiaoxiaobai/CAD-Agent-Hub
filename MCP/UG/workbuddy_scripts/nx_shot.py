# -*- coding: utf-8 -*-
"""把 NX 窗口调到前台（可选最大化）并截屏，用于核对 NX 里的建模结果。

用法:
  python nx_shot.py --max            只把 NX 最大化并置前，不截图
  python nx_shot.py <out.png>        置前 + 截屏保存到指定路径
  python nx_shot.py                  置前 + 截屏到默认路径 nx_view.png

注意: ShowWindow(9)/SW_RESTORE 会把最大化窗口还原，所以恢复布局要用 SW_MAXIMIZE(3)。
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

from PIL import ImageGrab

ROOT = r"E:\workbuddy-成果\2026-09-15-12-10-47"
user32 = ctypes.windll.user32
SW_MAXIMIZE = 3


def find_nx_windows():
    found = []

    def _cb(hwnd, lparam):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            title = buf.value
            if "NX" in title:
                found.append((hwnd, title, bool(user32.IsWindowVisible(hwnd))))
        return True

    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    user32.EnumWindows(proc(_cb), 0)
    return found


def focus_nx(maximize):
    wins = find_nx_windows()
    target = None
    for h, t, v in wins:
        if v:
            target = h
            break
    if not target:
        print("no visible NX window found:", wins)
        return None
    if maximize:
        user32.ShowWindow(target, SW_MAXIMIZE)
    user32.SetForegroundWindow(target)
    time.sleep(1.5)
    print("focused hwnd=%s maximize=%s" % (target, maximize))
    return target


def main():
    args = sys.argv[1:]
    if "--max" in args:
        focus_nx(True)
        return
    focus_nx(False)
    out = args[0] if args else os.path.join(ROOT, "nx_view.png")
    img = ImageGrab.grab()
    img.save(out)
    print("saved", out, img.size)


if __name__ == "__main__":
    main()
