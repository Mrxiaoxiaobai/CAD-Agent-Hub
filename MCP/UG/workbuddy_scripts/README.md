# WorkBuddy × NX 配套脚本集

这些脚本配合 `skills/nx-mcp-bridge-modeling` 使用，用于在运行中的 Siemens NX (UG) 2007 会话里实时建模。

## 文件说明
- `nx_ready.py` — 一键就绪检查：检测 MCP 桥是否在线，不在则自动拉起带桥的 NX（桌面 `nx_start.bat` 即调用它）。
- `nx_shot3.py` — 截图核对：隐藏遮挡窗口、按 NX 区域裁剪，生成 PNG 供 AI 自证造型。用法 `python nx_shot3.py out.png`。
- `nx_shot.py` — 旧版置顶截图（会被其他窗口挡住，备用）。
- `build_conveyor.py` — 示例：SX-815Q 循环输送带装配体（PDF 抄图）。
- `build_tomica_box.py` — 示例：多美卡小车收纳盒（六面榫卯互锁）。
- `probe_nx_api.py` / `probe_move.py` / `analyze_nx_api.py` / `extract_members.py` / `extract_tm.py` — NXOpen API 探测脚本（能力矩阵/移动平移验证用，临时验证即可）。

> 注意：`.prt` / `.png` / `.pdf` 等二进制与大文件不入库；本目录只收脚本与说明。
