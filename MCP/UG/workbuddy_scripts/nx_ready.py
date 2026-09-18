# -*- coding: utf-8 -*-
r"""
NX 一键就绪 —— 全流程唯一入口逻辑（2026-09-17 定稿）

目的：把「NX 已打开 + 建模桥已在线」这件事变成一句话就能搞定的事。
      之后对话里说一句"画个 XX"，就可以直接开始建模，用户只需要看 NX 里的结果。

桥在线的两条判据（任一成立即算就绪）：
  1) TCP 能连上 127.0.0.1:48161
  2) %TEMP%\nx_mcp_remoting_server.log 里出现 "Ready on http://127.0.0.1:48161"

用法：
  python nx_ready.py                 确保 NX 就绪（没开就自动打开）
  python nx_ready.py <part.prt>      就绪后打开指定零件（仅在新开 NX 时生效）
  python nx_ready.py --status        只查状态，绝不启动任何东西

输出末行恒为 RESULT: READY / NOT_READY / NX_RUNNING_NO_BRIDGE / FAILED
退出码：0 = 就绪，1 = 未就绪
"""
import os
import socket
import subprocess
import sys
import time

NXROOT = r"E:\NX\Program Files\Siemens\NX2007"
UGII = os.path.join(NXROOT, "UGII")
NXBIN = os.path.join(NXROOT, "NXBIN")
# 桥 DLL 部署在这里；NX 靠 UGII_USER_DIR\startup 自动调用它的 Startup()
BRIDGE_ROOT = r"E:\workbuddy-成果\2026-09-15-12-10-47\CAD-Agent-Hub\MCP\UG\nx_user"
TMP = os.environ.get("TEMP") or r"C:\Users\xajsxy\AppData\Local\Temp"
LOG = os.path.join(TMP, "nx_mcp_remoting_server.log")
HOST, PORT = "127.0.0.1", 48161
WAIT_SECONDS = 180


def nx_env():
    """显式给全 NX 需要的环境变量 —— 不能依赖当前 shell 继承。"""
    env = os.environ.copy()
    env["UGII_BASE_DIR"] = NXROOT
    env["UGII_ROOT_DIR"] = UGII
    env["UGII_USER_DIR"] = BRIDGE_ROOT      # 缺这个桥就不会自动加载
    env["DISPLAY"] = "LOCALPC:0.0"
    env["PATH"] = NXBIN + os.pathsep + UGII + os.pathsep + env.get("PATH", "")
    return env


def nx_running():
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq ugraf.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding="gbk", errors="replace",
            timeout=25).stdout
    except Exception:
        return False
    return "ugraf.exe" in out.lower()


def port_open():
    s = socket.socket()
    s.settimeout(1.0)
    try:
        s.connect((HOST, PORT))
        return True
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def log_ready():
    # 只信任"最近一次事件仍是 Ready"：若之后出现过 Server stopped，说明桥已掉，
    # 不能仅凭历史日志里的 Ready 误报在线（这是 2026-09-18 发现的假阳性根因）。
    try:
        with open(LOG, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except Exception:
        return False
    last_ready = text.rfind("Ready on http://%s:%d" % (HOST, PORT))
    last_stop = text.rfind("Server stopped")
    if last_ready == -1:
        return False
    if last_stop != -1 and last_stop > last_ready:
        return False
    return True


def is_ready():
    return port_open() or log_ready()


def launch(part=None):
    cmd = [os.path.join(UGII, "ugraf.exe")]
    if part:
        cmd.append("-retrieve:" + part)   # 必须带 -retrieve:，裸路径 NX 只停在起始页
    flags = getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(cmd, env=nx_env(), cwd=UGII, creationflags=flags)


def line(tag, msg):
    print("  [%s] %s" % (tag, msg))
    sys.stdout.flush()


def main():
    argv = list(sys.argv[1:])
    status_only = "--status" in argv
    argv = [a for a in argv if a != "--status"]
    part = argv[0] if argv else None
    if part and not os.path.isfile(part):
        line("!!", "指定的零件不存在，忽略：%s" % part)
        part = None

    print("=" * 58)
    print("  NX 就绪检查")
    print("=" * 58)

    if is_ready():
        line("OK", "NX 已打开，建模桥在线 —— 可以直接说“画个 XX”。")
        print("RESULT: READY")
        return 0

    running = nx_running()

    if status_only:
        line("--", "NX 进程在跑" if running else "NX 没开，桥也没在线。")
        print("RESULT: NOT_READY")
        return 1

    if running:
        # NX 开着但桥没上线：多半是这次启动早于桥安装，或环境变量当时没生效。
        line("!!", "检测到 NX 进程在跑，但建模桥没上线。")
        line("!!", "我这边会改用兜底方案（离线建模），不需要你操作。")
        print("RESULT: NX_RUNNING_NO_BRIDGE")
        return 1

    line(">>", "NX 没开，正在自动打开（首次启动约 30-90 秒）...")
    launch(part)

    t0 = time.time()
    while time.time() - t0 < WAIT_SECONDS:
        if is_ready():
            line("OK", "桥已在线，用了 %d 秒。" % int(time.time() - t0))
            print("RESULT: READY")
            return 0
        time.sleep(3)

    line("!!", "等了 %d 秒桥还没上线，可能 NX 弹了报错窗口。" % WAIT_SECONDS)
    print("RESULT: FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
