---
name: nx-mcp-bridge-modeling
description: |
  Drive a LIVE Siemens NX (UG) session in real time through the CAD-Agent-Hub MCP bridge
  (`siemens-nx` MCP server + in-NX .NET Remoting DLL), executing raw NXOpen Python via the
  `run_python` tool. TRIGGER when: user says 画个/建模/实时画 in an NX context AND the NX MCP
  tools (`mcp__siemens-nx__*`) are available; or the user mentions the CAD-Agent-Hub bridge,
  NXOpenSession endpoint, run_python against NX, or wants WorkBuddy to "drive NX directly".
  Covers: bridge liveness check, the verified build recipes (block / sketch / extrude /
  rotated parts / **exact ellipsoids via sphere+scale for realistic organic shapes**),
  the exact NX2007 binding quirks, bounding-box + color + delete APIs,
  the SaveAs name-collision trap, the **unstable body-tag trap**, the STEP round-trip
  part-cleaning trick, the reliable screenshot-verification script,
  and **body translation via MoveObjectBuilder/MoveBodyBuilder** (2026-09-18: the old
  "move/rotate all dead" claim was a testing error — translation works).
  NOTE: this is a DIFFERENT mechanism from `nx-journal-automation` (that one = offline
  run_journal.exe journals). **THIS is the PRIMARY/首选 NX modeling path** — use it whenever
  the interactive MCP bridge is in play; `nx-journal-automation` is only the fallback.
description_zh: "用 MCP 桥实时驱动运行中的 NX（run_python + NXOpen）—— NX 建模首选方案"
description_en: "Drive a live NX session via the CAD-Agent-Hub MCP bridge (primary NX path)"
agent_created: true
metadata:
  category: cad-automation
  version: "1.4.1"
---

# 用 MCP 桥实时驱动运行中的 NX（NXOpen via run_python）

> 🥇 **NX 建模首选方案（2026-09-17 定稿）**。用户视角的协议只有一句：
> **用户发一句话 → 我全包 → 用户只看 NX 里的结果。**
> 用户不需要双击任何东西、不需要敲命令、不需要懂任何术语。
> 次选（仅在本桥不可用时）见 `nx-journal-automation`。
>
> 与 `nx-journal-automation` 的区别：那个是**离线 `run_journal.exe` 播 journal**；
> 本技能是**对话式实时驱动一个已经开着的 NX**（WorkBuddy 当 MCP 驾驶座）。

## 0. 用户视角协议（每次接活先做这 3 步，不用问用户）

用户说"画个 XX"时，**不要**让用户去开 NX、不要报路径、不要讲原理。直接：

```bash
python "E:\workbuddy-成果\2026-09-15-12-10-47\nx_ready.py" --status
```

- 输出 `RESULT: READY` → NX 已开、桥在线，**直接开始建模**。
- 输出 `RESULT: NOT_READY` → 去掉 `--status` 再跑一次，脚本会**自动打开 NX** 并
  轮询到桥上线（最长 180 秒），拿到 `RESULT: READY` 再建模。全程无需用户操作。
- 输出 `RESULT: NX_RUNNING_NO_BRIDGE` → NX 开着但桥没加载。改用离线兜底
  （`nx-journal-automation`）或提示用户重启一次 NX；**不要**再开第二个 NX。
- 输出 `RESULT: FAILED` → 桥没等到，同样走兜底，并把情况如实告诉用户。

> 桌面 `nx_start.bat` 现在就是调这个脚本（= 同一个逻辑），用户临时想自己开也行。
> 旧的两段式（离线建模 + 查看）入口已备份为桌面 `nx_start_旧方案_离线建模.bat`。

产出约定：模型统一存 **`D:\三维建模结果\<名字>.prt`**；建完存盘后**只回报结果**，
（`✅ 清单 + 一句话结论`），不复述 NXOpen 术语。

## 0b. 前置与在线判定

- NX 装好后，装 `UGII_USER_DIR`（指向 CAD-Agent-Hub 的 `MCP/UG/nx_user`）→ NX 启动时
  自动加载 `NXMcPRemotingServer.dll`，端点 `http://127.0.0.1:48161/NXOpenSession` 在线。
- **在线判定**（最省事）：读日志 `%TEMP%\nx_mcp_remoting_server.log`，出现
  `Ready on http://127.0.0.1:48161/NXOpenSession pid=<pid>` 即在线。
- 或直接调 `mcp__siemens-nx__ping` → 返回 `ok:true, transport=dotnet-remoting, work_part=...`。
- NX 没开 → 工具调用报 `BridgeConnectionError`（正常）。**先跑 `nx_ready.py` 自动开 NX**，
  不要叫用户自己开（见 §0）。

## 1. 最关键的事实：`run_python` 是**进程内真实 NXOpen**

- `mcp__siemens-nx__run_python` 里的代码在 **NX 进程内部**执行（CPython 3.8，不是 IronPython）。
  - **没有 `System` 模块**；对象是**真实的 NXOpen 对象，不是 remoting 代理**。
  - 代码末尾给 `result = <任意可序列化对象>` 即可把数据带回。
- 因此：**能用 `run_python` 就别用高层 MCP 特征工具**。高层工具（`extrude_sketch` 等）在
  回传"草图对象"时会因 remoting 代理报 `NXOpen.NXException: 传递的 self 参数无效。, 对象不再存在`。
  规避套路 = **MCP 建草图 + `run_python` 按名字找草图/曲线再拉伸/上色**。

## 2. 每次都要写的三行样板

```python
import NXOpen, NXOpen.UF        # import NXOpen 后 NXOpen.UF 并不存在，必须显式 import
theSession = NXOpen.Session.GetSession()
work = theSession.Parts.Work
ufs = NXOpen.UF.UFSession.GetUFSession()
```

**头号坑：所有数值参数必须是 `float`。** `Point3d(0,0,0)` / `Vector3d(0,1,0)`（int）会报
`期望的是 double 类型，找到的是 int`。一律写 `0.0, 0.0, 0.0`。

## 3. 已验证的建模配方

### 3.1 长方体（block）

```python
b = work.Features.CreateBlockFeatureBuilder(NXOpen.Features.Feature.Null)   # 注意：Feature.Null
b.Type = NXOpen.Features.BlockFeatureBuilder.Types.OriginAndEdgeLengths
b.SetOriginAndLengths(NXOpen.Point3d(ox, oy, oz), str(l), str(w), str(h))   # origin = 最小角
b.SetBooleanOperationAndTarget(NXOpen.Features.Feature.BooleanType.Create, NXOpen.Body.Null)
feat = b.CommitFeature(); b.Destroy()
body = feat.GetBodies()[0]
```
- `origin` 是**最小角**（不是中心）；`str(...)` 传尺寸。
- `BooleanType.Create` = 建独立新体（不与已有体合并）。改 `Unite/Subtract/Intersect` + 第二个参数传目标 Body 可做布尔。

### 3.2 草图（用高层 MCP 工具，别用 run_python 手搓）

`mcp__siemens-nx__create_parametric_sketch`，参数：
- `name`：草图名（**全局唯一**，重复会报错）。
- `plane`：只支持 `"XY"` / `"XZ"` / `"YZ"`。局部 (u,v) → 世界坐标 = `origin + u*u_axis + v*v_axis`：

| plane | u_axis | v_axis | normal |
|---|---|---|---|
| XY | (1,0,0) | (0,1,0) | (0,0,1) |
| XZ | (1,0,0) | (0,0,1) | (0,-1,0) |
| YZ | (0,1,0) | (0,0,1) | (1,0,0) |

- `geometry`：`{"type":"line","start":[u,v],"end":[u,v],"name":"L0"}`、
  `{"type":"circle","center":[u,v],"radius":20}`、`{"type":"rectangle","origin":[u,v],"width":..,"height":..}`、`{"type":"arc",...}`。
- `origin`：草图平面上的原点（局部 (0,0) 对应的世界点）。
- **任意多边形（含旋转矩形）用 4 条 `line` 画**——这正是"旋转件"的实现手段（见 §4）。

### 3.3 拉伸（run_python，按名找曲线/草图）

```python
# 若曲线是草图几何：
sketch = None
for s in work.Sketches:
    if s.Name == 'SK_NAME': sketch = s; break
curves = list(sketch.GetAllGeometry())
# 若曲线是散线：直接用你创建时留下的列表 curves
section = work.Sections.CreateSection(0.00095, 0.001, 0.5)
rule = work.ScRuleFactory.CreateRuleCurveDumb(curves)
section.AddToSection([rule], curves[0], NXOpen.NXObject.Null, NXOpen.NXObject.Null,
                     NXOpen.Point3d(0.0, 0.0, 0.0), NXOpen.Section.Mode.Create, False)
builder = work.Features.CreateExtrudeBuilder(NXOpen.Features.Feature.Null)
builder.Section = section
builder.Direction = work.Directions.CreateDirection(
    NXOpen.Point3d(0.0,0.0,0.0), NXOpen.Vector3d(0.0,0.0,1.0),      # 拉伸方向
    NXOpen.SmartObject.UpdateOption.WithinModeling)
builder.Limits.StartExtend.Value.RightHandSide = '0'                # 起点偏移（字符串）
builder.Limits.EndExtend.Value.RightHandSide = '28'                 # 终点偏移
builder.BooleanOperation.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Create
feat = builder.CommitFeature(); builder.Destroy()
body = feat.GetBodies()[0]
for c in curves: c.Blank()     # 拉完把辅助线隐藏
```
- 散线用 `work.Curves.CreateLine(Point3d, Point3d)` 造（**无需草图**，最省事）。
- `AddToSection` 第二参数传"种子曲线"= `curves[0]`，`rule` 里带全部曲线，可自动成环。

### 3.4 ⭐ 圆/圆柱：`CreateArc` 一次成型（**免草图，最省事的"球/圆柱/圆盘"**）

2026-09-17 实测：`work.Curves.CreateArc` 有重载
`CreateArc(center, xDirection, yDirection, radius, startAngle, endAngle)`。
**`startAngle=0, endAngle=2π` 直接得到一整圆**，无需任何草图、无需 Activate，
然后照 §3.3 拉伸即可。这是本绑定里**最可靠的"圆形件"造法**（车轮、圆盘、球感体、卡通件全靠它）。

```python
import math
arc = work.Curves.CreateArc(
    NXOpen.Point3d(cx, y0, cz),            # 圆心（在 XZ 平面时 Y 取常数）
    NXOpen.Vector3d(1.0, 0.0, 0.0),        # 圆所在平面的 x 方向
    NXOpen.Vector3d(0.0, 0.0, 1.0),        # 圆所在平面的 y 方向（→ 圆画在 XZ 平面）
    float(r), 0.0, 2.0 * math.pi)          # 半径、起角、终角（都必须是 float）
# 之后照 §3.3 建 section + 拉伸；拉完 arc.Blank() 藏掉辅助线
```
- 圆画在 XZ 平面 → 沿 Y 拉伸成"圆柱/圆盘"（正面看是圆）。
- 圆画在 XY 平面 → 沿 Z 拉伸（正面看是圆，Z 向厚度）。
- **"平面卡通件"整套打法**：把造型拆成一堆圆（+少量矩形），全部同轴拉伸、给不同深度，
  再统一布尔相加，就得到有立体感又不失轮廓的 3D 物。小鹏 P7 之后那只卡通小狗（见 §7 案例）
  15 个圆/矩形 → 1 个实体，就是这么做的。

## 4. 移动实体（平移）—— MoveObjectBuilder / MoveBodyBuilder（2026-09-18 文档核查更正）

> ⚠️ **重大更正**：旧版本节的"三条旋转/移动路全废"是**2026-09-17 测错了**。
> 2026-09-18 用 NX 自带 `NXOpen.xml` 静态核查 + 真机探针确认：
> **`CreateMoveObjectBuilder`、`CreateMoveBodyBuilder` 都存在且可用**，是平移实体的标准手段。
> 旧结论作废，本节重写。

### 4.1 ⚠️ 平移一个实体 —— 实机不可用（2026-09-18 真机翻案）
**真机实测（NX2007 活会话）**：`work.Features.CreateMoveObjectBuilder` **不存在**
（AttributeError: FeatureCollection object has no attribute 'CreateMoveObjectBuilder'）。
文档里有、实机没有。下面的代码留作档案，**别用**；要挪实体 → 删除重建，或一开始就建在目标位姿。

```python
def move_body(body, dx, dy, dz, copy=False):
    mb = work.Features.CreateMoveObjectBuilder(NXOpen.Features.MoveObject.Null)
    mb.ObjectToMoveObject.Add(body)                       # 要移动的体（SelectObjectList.Add）
    mb.MoveObjectResult = (NXOpen.Features.MoveObjectBuilder
                           .MoveObjectResultOptions.CopyOriginal if copy
                           else NXOpen.Features.MoveObjectBuilder
                           .MoveObjectResultOptions.MoveOriginal)
    mb.Associative = False
    tm = mb.TransformMotion
    tm.DeltaXc.RightHandSide = str(float(dx))
    tm.DeltaYc.RightHandSide = str(float(dy))
    tm.DeltaZc.RightHandSide = str(float(dz))
    f = mb.CommitFeature(); mb.Destroy()
    return f
```
- `ObjectToMoveObject` 若 `.Add` 报错，改 `.AddMultiple([body])`。
- 平移后按 §5 包围盒核对是否真动了（`|ΔminX| ≈ dx`）。

### 4.2 ⚠️ 备选：MoveBodyBuilder —— 实机同样不可用
`mbb.BodyToMove = body` → 实机报 **not writable**（2026-09-18 真机确认）。
```python
mbb = work.Features.CreateMoveBodyBuilder(NXOpen.Features.MoveBody.Null)
mbb.BodyToMove = body          # 实测可设（旧记"只读"是错的）
mo = mbb.Motion
mo.DeltaXc.RightHandSide = str(dx); mo.DeltaYc.RightHandSide = str(dy)
mo.DeltaZc.RightHandSide = str(dz)
f = mbb.CommitFeature(); mbb.Destroy()
```

### 4.3 旋转/平移整体系 —— 一律「建成目标姿态」或删除重建（唯一可靠路）
**结论（2026-09-18 真机定稿）：本绑定移动/旋转实体全部不可用**（4.1 工厂缺失、4.2 只读、
UF TransformEntities 对 body no-op）。需要改位姿的件：删掉按新位置重建（配方都在，成本低）。
`MoveObjectBuilder.TransformMotion` 文档只暴露平移增量（`DeltaXc/Yc/Zc`）+ `Option`，
**未暴露 `Angle/Axis`**，所以"整体系绕任意轴旋转"还不能在文档层面确认。
- **绕竖轴(Z) / 横轴(Y) 的姿态件**（门、翼、掀盖等）：继续用下面这套"直接建成目标姿态"的绕过法（已验证可靠），不事后旋转。
- 绕**竖轴(Z)**旋转的门/翼 → 在 XY 平面画**算好角度的 4 条线**（旋转矩形），沿 Z 拉伸。
  旋转矩阵：`v' = (vx·cosφ - vy·sinφ, vx·sinφ + vy·cosφ)`；长度方向 `u=R(φ)·(-1,0)`、
  厚度方向 `n=R(φ)·(0,1)`；四角 = `H, H+u·L, H+u·L+n·t, H+n·t`（H=铰链点）。
  左右门 φ 取相反号（左门 φ 负、右门 φ 正 → 都向车外张）。
- 绕**横轴(Y)**掀起的后备箱盖 → 在 XZ 平面画旋转后的截面矩形，沿 Y 拉伸。
  绕 +Y 旋转 θ：`(Δx,Δz) → rot2((Δx,Δz), -θ)`（等价 `x'=x·cosθ+z·sinθ, z'=-x·sinθ+z·cosθ`）。
- 验证姿态：用 §5 包围盒确认端点在预期一侧（例如左门 maxY 明显 > 车侧 Y）。

### 4.4 旧"三条路全废"记录（仅供复盘，勿据此实施）
- 旧记"`CreateMoveObjectBuilder` 方法不存在" → **错**，文档+探针均确认存在。
- 旧记"`CreateMoveBodyBuilder.BodyToMove` 只读" → **错**，实测可设。
- `ufs.Modl.TransformEntities(...)` 对 body 仍是 no-op（这条是真的）。

### 4.5 ⭐ 视角配方（2026-09-18 实测定稿）
`vw.Rotate(origin, (0,0,1), θ)` 是**绕竖轴的转台 yaw**（θ 累加）。目标图同款轴测视角：

```python
vw.Orient(NXOpen.View.Canned.Trimetric, NXOpen.View.ScaleAdjustment.Fit)
vw.Rotate(NXOpen.Point3d(0.0,0.0,0.0), NXOpen.Vector3d(0.0,0.0,1.0), 67.5)
vw.Fit()
```

- 机理：Trimetric 相机在方位角约 -45°（即 +X/-Y 侧，**朝观众的面放 -Y 侧**是对的）；
  yaw θ 后相机方位角 ≈ -45°-θ。要在画面里同时看到「-Y 面的件 + 长轴件走向右上方」，
  取 **θ=67.5**（可用区间约 θ∈(-45,135)，θ 越大件越"侧"）。
- 注意：连续两次 Rotate 的转轴随视角变，**不与 Orient 后直接转严格等价**——
  保险做法永远是「先 Orient 重置，再一次 Rotate 到位」。
- 真机实测脚本见工作区 `probe_move.py`（在内存临时零件里平移球体/方块并核对包围盒，测完关闭不保存）。

## 5. 查询 / 着色 / 删除 / 存盘

### 包围盒（验证几何最有用）
```python
box = [float(v) for v in ufs.ModlGeneral.AskBoundingBox(int(body.Tag))]
# 返回 6 个数：minx,miny,minz,maxx,maxy,maxz
```
- **注意是 `ufs.ModlGeneral.AskBoundingBox`，不是 `ufs.Modl`**（`ufs.Modl` 没这个方法）。
- `ufs.Bound` 是"边界"不是包围盒；`Body` 没有 `GetBoundingBox`。

### 着色（灰/透明等）
```python
ufs.Obj.SetColor(int(body.Tag), 159)          # 159 = 中灰色
ufs.Obj.SetTranslucency(int(body.Tag), 80)    # 透明：80（0=不透明）
```
**调色板索引（实测，`ufs.Disp.AskColor(idx, 1)` 返回 HSV，model=1 即 HSV）：**
| 索引 | 名称 | 索引 | 名称 |
|---|---|---|---|
| 44 | 浅灰色 | 130 | 岩灰色 |
| 50 | 淡灰色 | 159 | **中灰色**（车身首选） |
| 87 | 银灰色 | 173 | 深灰色 |
| 91 | **浅蓝色**（玻璃首选） | 201 | 铁灰色 |
| 123 | 烟灰色 | 210 | 炭灰色 |

- **坑**：索引 36 是**绿色**、37 是**粉色**（不是灰）。要灰必须查上面的表，别凭记忆写 36。
- `ufs.Disp.AskColor(idx, model)` 的 `model`：1=HSV（返回 (name, [h,s,v])）。

### 删除实体（清理试建件）
```python
ufs.Obj.DeleteObject(int(body.Tag))
```
- **Feature 没有 `Delete()`**（只有各种 DeleteAttribute*）；删实体走 `Obj.DeleteObject`。
- 试建件别忘了删——它们会留在零件里。

### 存盘 / SaveAs（撞名陷阱）
```python
# ⭐ 新建"干净的空零件"做新总成（本绑定 NewDisplay 只要 2 个参数！）：
newp = theSession.Parts.NewDisplay('part_name', NXOpen.Part.Units.Millimeters)
# 传 3 参数会报"函数采用 2 个参数，传递 3 个"；建完自动成为工作零件。
# 建新总成前必用——否则会画进当前打开的旧零件里。
```
```python
# 存"当前零件"（已 SaveAs 过、FullPath 有值）—— Save 必须给两个参数！
work.Save(NXOpen.BasePart.SaveComponents.TrueValue,
          NXOpen.BasePart.CloseAfterSave.FalseValue)
```
- **坑（实测）**：`work.Save()` 报 `函数采用 2 个参数，传递 0 个`；
  用文档里的类型名 `NXOpen.BasePartSaveComponents` 又报 **`传递的第一个参数无效`**。
  正确的是 **`NXOpen.BasePart.SaveComponents`**（注意是 `BasePart` 的内嵌枚举，文档类型名误导）。
- SaveAs 见下；**目标文件名已存在时**，稳妥做法是先 `os.rename` 备份成 `xxx_old_<时间戳>.prt`（**不要直接删**）。
  ```python
  work.SaveAs(r'D:\三维建模结果\xpeng_p7.prt')
  ```
- **若 SaveAs 报 `文件已存在` 但磁盘上根本没这个文件** → 说明**会话里还载着同名零件**（旧会话留下的）。
  先关掉它再 SaveAs：
  ```python
  for p in list(theSession.Parts):
      if int(p.Tag) == <stale_tag>:
          p.Close(NXOpen.BasePartCloseWholeTree.FalseValue,
                  NXOpen.BasePartCloseModified.CloseModified, None)
  ```
  用 `theSession.Parts` 遍历可先查出 `name / full / tag`，据此认人。

## 5b. ⚠️ 布尔相加（Unite）只能加"真相交"的体

```python
bb = work.Features.CreateBooleanBuilder(NXOpen.Features.BooleanFeature.Null)
bb.Operation = NXOpen.Features.Feature.BooleanType.Unite      # Unite / Subtract / Intersect
bb.Target = target_body        # 必须是 Body 对象（不是 tag）
bb.Tool   = tool_body
bb.RetainTarget = False
bb.RetainTool   = False
bf = bb.CommitFeature(); bb.Destroy()
target_body = list(bf.GetBodies())[0]      # 每加一次都要刷新目标引用
```
**实测血泪（2026-09-17，卡通小狗把主体搞丢过一次）**：
- 两个体**不相交**时 `CommitFeature()` **不报错**，但**工具体不会被吸收**（留在零件里当孤立体）；
  更糟的是随后某一步可能把 **target 本体吃掉** → 主体直接消失，只能重建。
- 因此：**只按"确认真相交"的顺序相加**（从主件出发，每次加一个和当前目标有重叠的体）。
  圆链（尾巴之类）**相邻两个圆必须真的相交**（圆心距 < 半径和），别留 1~2mm 缝。
- 加完务必数一下 `work.Bodies` 的个数是否符合预期，并复核 target 的包围盒。
- 兼容但更保险的替代：用 §3.3 的 `builder.BooleanOperation.Type` 在**拉伸时就直接并进去**。

## 5c. 视图控制 + 截屏核对（"让用户直接看到结果"）

```python
vw = work.Views.WorkView
vw.Orient(NXOpen.View.Canned.Trimetric, NXOpen.View.ScaleAdjustment.Fit)   # 等轴测+自适应
vw.Fit()
```
- Canned 可取 `Trimetric` / `Front` / `Back` / `Top` / `Right` …
- **方向坑**：NX 的 `Front` 视图是**从 +Y 方向看**。所以"朝向观众的面"要放在 **-Y 侧**，
  否则默认 Front 视图里看到的是背面。（默认启动视图是 Trimetric，它从 (+X,-Y,+Z) 看，-Y 的面可见 ✓）
- 交付前把视图摆好并 `Save`，用户打开就是好角度，不用自己转。

**截屏核对（工具：工作区 `nx_shot.py`）**：
```bash
python nx_shot.py --max                 # 先把 NX 最大化并置前（不截图）
python nx_shot.py <out.png>             # 置前 + 截屏
```
- 实现：`ctypes` 枚举窗口找标题含 `NX` 的 → `SetForegroundWindow` → `PIL.ImageGrab.grab()`。
- **坑**：`ShowWindow(hwnd, 9)`（`SW_RESTORE`）会把**最大化窗口还原**（用户布局被改）；
  要恢复最大化用 **`ShowWindow(hwnd, 3)`（`SW_MAXIMIZE`）**。
- 截屏后自己 `Read` 图片核对造型——这是本流程**唯一能自证"画得像不像"的手段**，务必做。

## 6. 交付纪律（本用户偏好）
- **用户只发一句话，其余全自动**；不要给选择题、不要让他自己开软件。
- 用 **✅ 清单**汇报：建了什么、几个体、关键尺寸、存盘路径；**不复述 API/术语**。
- 交付时附一张 NX 截屏（§5c），用户"只看结果"。
- 用户重视"最大长度/宽度"等硬指标，建完用包围盒核对并**报出实测值**。

## 7. 成品案例（可照抄的比例与做法）

### 7.1 小鹏 P7 鹏翼版（2026-09-17，存在 `D:\三维建模结果\xpeng_p7.prt`）
- 270×105 mm 车身 BLOCK + 座舱 + 4 轮（圆草图拉伸 R20×W16）+ 4 门（绕竖轴 55° 张开）
  + 后备箱盖（绕横轴 50° 掀起）+ 6 块透明车窗；共 17 体。
- 关键点：门/盖都是**直接在目标姿态下建截面**（见 §4），不做事后旋转。
- 车身 **159 中灰色**，车窗 **91 浅蓝色 + 透明度 80**。

### 7.2 卡通小狗（2026-09-17，加在同一零件的 X+400 处）
参考一张正面卡通线稿 → 3D 化。**全部用 §3.4 的圆 + 少量矩形，沿 Y 拉伸成"厚浮雕"**，
正面看轮廓与线稿一致、侧看有厚度。
- 单位换算：量出线稿像素比例 → `mm = px × s`（这只狗取 `s=0.675`，成品宽 159 × 高 159 mm）。
- 主体（全部 Y 居中，靠**不同拉伸深度**产生层次）：
  头 ⌀102 / 两只垂耳 ⌀58 / 身子 ⌀86 / 两个后臀 ⌀54 / 两条前腿（矩形+圆底）
  / 尾巴（**一串相交的圆**，半径 9→5 递减）。
- 五官（**单独体、单独上色，别并进主体**，放在 -Y 侧并凸出 4~5mm）：
  两只眼 ⌀12.4、鼻子（两个 ⌀10.4 横向并排）、舌头（两个 ⌀11 竖向并排）→ 分别 **216 黑** 与 **15 粉**。
- 前腿/前爪的 Y 深度要**比身子更靠 -Y**（凸出约 10mm），否则会被身子吞掉、正面看不见。
- 结果：15 个灰体布尔相加 → 1 个实体 + 4 个五官体 = 5 体；整件 159 × 77 × 159 mm。

### 7.3 真比例小狗（2026-09-17 晚，`D:\三维建模结果\cartoon_dog.prt`）
用户嫌 7.2 的"圆球堆"不像真狗（原话："谁家狗从头到脚是圆柱形"）→ 改用 §8 的椭球重做，
并在**全新零件**里建（天然无历史包袱）。
- 单体 **5 个**：主体（灰 159）+ 黑鼻 + 双眼（216 纯黑）+ 粉舌（150 深粉红）。
- 主体 = **19 个椭球全部 union**：躯干(34,28,42)@z66 / 脖 / 胸 / 头(38,34,34)@z134 /
  吻(21,24,19)@y−28 / 双垂耳 / 后臀×2 / 后脚×2 / **大腿+小腿+前掌×2（三段腿，有锥度）**
  / **尾巴三段**（沿 Y 拉长的椭球，逐段上移 → 向后上翘）。
- 排版原则：**每个新件的椭球中心尽量落在"已并入主体的某个体"内部**，union 成功率最高。
- 尾巴**别用小球串**（会看出"糖葫芦"珠链感）→ 用 **2~3 段轴向拉长的椭球嵌套**，表面才光滑。
- 成品：92 宽 × 123 长 × 168 高 mm；五官（鼻/眼/舌）**不并入主体**，单独上色。

## 8. ⭐⭐ 任意椭球的精确摆放（球 + 非均匀缩放）—— 做"像真东西"的核心武器

NX2007 这个绑定**没有 Loft**（`CreateLoftBuilder` 不存在），但**有**：
`CreateSphereBuilder`（球）、`CreateScaleBuilder`（X/Y/Z 非均匀缩放）、
`CreateConeBuilder`（圆台）、`CreateTubeBuilder`（沿路径的管）、`CreateRevolveBuilder`。

**球 + 缩放 = 任意椭球**，这是把"圆球堆"升级成"真形体"的关键（狗的头/吻/耳/躯干/腿全靠它）。

```python
R = 10.0                      # 基准球半径：别用 1.0（太小易触建模容差）
def ell(cx, cy, cz, rx, ry, rz):
    """在 (cx,cy,cz) 放一个半轴 (rx,ry,rz) 的椭球，返回 body。"""
    kx, ky, kz = rx/R, ry/R, rz/R
    fy = ky / 2.0
    # 缩放绕【世界原点】做（ScaleBuilder.Point 设了也没用）→ 球心必须反算补偿
    pt = work.Points.CreatePoint(NXOpen.Point3d(cx/kx, cy/fy, cz/kz))
    sb = work.Features.CreateSphereBuilder(NXOpen.Features.Sphere.Null)
    sb.Type = NXOpen.Features.SphereBuilder.Types.CenterPointAndDiameter
    sb.CenterPoint = pt
    sb.Diameter.RightHandSide = str(2.0*R)
    sf = sb.CommitFeature(); sb.Destroy()
    body = sf.GetBodies()[0]
    sc = work.Features.CreateScaleBuilder(NXOpen.Features.Scale.Null)
    sc.Type = NXOpen.Features.ScaleBuilder.Types.General    # 三轴自由缩放
    sc.BodyToScale.Add(body)
    sc.Point = pt
    sc.ScaleXdirection.RightHandSide = str(kx)              # X：1:1 生效
    sc.ScaleYdirection.RightHandSide = str(fy)              # Y：填一半（见下）
    sc.ScaleZdirection.RightHandSide = str(kz)              # Z：1:1 生效
    f2 = sc.CommitFeature(); sc.Destroy()
    return list(f2.GetBodies())[0]
```

**实测怪癖（必须记住，否则位置/尺寸全错）**：
- 缩放**绕世界原点**，`sc.Point` 无效 → 位置只能靠**球心补偿**：`球心 = 目标中心 / 有效因子`。
- **Y 方向**：**形状**的缩放系数是**设定值的 2 倍**，而**位置**只按设定值缩放。
  → Y 因子填 `ky/2`，球心 Y 填 `cy/(ky/2)`；X、Z 正常（因子 = k，球心 = c/k）。
- 用这套公式建的椭球，包围盒**与目标值逐位吻合**（实测含偏移 60mm 的样件）。
- 建完用 `ufs.ModlGeneral.AskBoundingBox(tag)` 逐件复核，别信"看着对"。
- 每个椭球会留 1 个辅助点，全建完 `for p in work.Points: p.Blank()` 藏掉。

## 9. ⚠️ body 的 tag **不稳定** —— 绝不要缓存 tag 做后续操作

本绑定里 NX 会**重编号 body tag**（同一个体，前后两次读到的 tag 不同）。
血泪案例：缓存了"6 个游离尾巴球"的 tag 去 `Obj.DeleteObject`，结果**把主体删了**（被迫重建）。

**三条硬规矩**：
1. **不要跨脚本缓存 tag**。要认某个体，用它**当下这一刻**的 bbox / 体积 / 中心。
2. **要长期跟踪 → 给它命名**（名字比 tag 稳）：
   ```python
   main.SetName('DOG_MAIN')                 # 建完命名
   def find_main():
       for bd in work.Bodies:
           if str(bd.Name).upper() == 'DOG_MAIN':
               return bd
   # 每次 union 之后：res.SetName('DOG_MAIN') —— 名字随 target 传下去
   ```
3. 找不到名字时，退化为**取包围盒体积最大的体**（但要小心：头 351k ≈ 躯干 350k 会误判，
   所以**顺序上先合并几个小件把主体做大**，再继续加头这类大件）。

**配套：union 必须"校验 + 重试"**（因为 §5b 的静默失败）：
```python
def unite_verified(target, tool, nm):
    before = <当前 body 数>
    for attempt in (1, 2):
        try:
            ... CommitFeature() ...
            if <当前 body 数> < before:          # 真吸收了
                res.SetName(MARK); return res, True, attempt
            target = find_main() or target
        except Exception:
            ...
    return target, False, 0
```
把每步结果写进日志（`try1/try2/ok/FAILED`），一眼看出哪步没生效。本轮 19 件**全部 try1 一次成功**。

## 10. ⭐ 零件"洗白"：STEP 往返（去掉历史包袱）

零件建久了会积一堆**孤儿特征**（删掉实体后残留的草图/螺旋线，还会在图形区显示成蓝线）。
彻底清干净的办法：**把实体搬进一个全新零件**。
1. `export_exchange(file_name="x.step", format="step", application_protocol="ap242", include_curves=False, overwrite=True)`
   → `include_curves=False` 顺带把残留曲线滤掉，只走实体。
2. `create_part(file_name="new.prt", units="millimeters")`
3. `import_exchange(file_name="x.step", format="auto", include_curves=False, sew_surfaces=True, simplify_geometry=True)`
   → 返回 `body_count_added / update_error_count`，可直接核对。

输出文件都落在 `CAD-Agent-Hub\MCP\UG\workspace\`。
**注意**：STEP 只带几何，**颜色要重新设**；导入后实体常**处于选中高亮态（橙红色）**，
按一次 Esc 即恢复本色——别以为颜色设错了。
（更省事的做法：**一开始就在 `create_part` 出来的新零件里建**，根本不用洗。）

## 11. 截屏核对的升级版（工具：工作区 `nx_shot3.py`）

`nx_shot.py` 的坑：别的窗口（资源管理器、自己写的系统窗口）挡在 NX 前面 → 截出来是别人的窗。
`nx_shot3.py` 的做法（已验证稳定）：
1. `SetProcessDpiAwareness(2)`；
2. 枚举可见顶层窗口，把**除 NX 与系统外壳**（Progman/WorkerW/Shell_TrayWnd…）之外的**全部临时隐藏**；
3. NX 显式 `SetWindowPos(TOPMOST, 0,0,screenW,screenH)`（比 `ShowWindow(MAXIMIZE)` 稳，不会被 Windows 贴靠挤成半屏）；
4. 发 **两次 Esc**（取消导入/操作后的选中高亮）；
5. `GetWindowRect` → `ImageGrab.grab(bbox=...)` **按窗口裁剪**；
6. 恢复被隐藏的窗口 + 取消 TOPMOST。

用法：`python nx_shot3.py <out.png>`。截完**自己 Read 图片核对造型**——这是唯一能自证"像不像"的手段。

⚠️ 找 NX 窗口别只 `"NX" in title`：浏览器标签页标题若含 "NX" 字样（如 GitHub 仓库描述里有
Siemens NX）会被误判成 NX，把真 NX 隐藏掉、截到浏览器。必须**过滤浏览器**（窗口类名/标题含
chrome/edge/firefox 一律跳过）+ 优先 `title.startswith("NX")`（真 NX 标题如 `NX - 基本环境`/
`NX - 建模`）。已修入 `nx_shot3.py`（2026-09-18）。

## 12. 色板实测（NX2007 默认调色板，HSV）
| 用途 | 索引 | 名称 |
|---|---|---|
| 通用灰（车身/狗身） | **159** | 中灰色 |
| 纯黑（眼睛/鼻子） | **216** | 黑色（s=0,v=0） |
| 深粉红（舌头） | **150** | 深粉红色 |
| 玻璃蓝 | **91** | 浅蓝色 |
| ⚠️ 别用 | 36=绿 / 37=浅粉红 / 15=粉灰(其实是灰) / 210=炭灰(近黑但非黑) | |
- 取色：`ufs.Disp.AskColor(idx, 1)` → `(name, [h,s,v])`，**h 是 0~360 度、s/v 是 0~1**（筛颜色时别把 h 当 0~1 用）。
- 想按名字找：先遍历 1~259 收集 `name/HSV`，再挑。

## 13. ⭐ 权威能力矩阵（来源：`NXOpen.xml`，2026-09-18 静态核查）

`work.Features` 上共 **210** 个 `Create*Builder` 工厂。下表是建模最常用、且本绑定已确认存在的，
按用途分组。**状态**：✅= 已真机验证可用；🟡= 文档确认存在、待真机 commit 验证；⬜= 存在但本技能尚未用到。

### 13.1 体素 / 基础
| 特征 | 工厂 | 状态 | 备注 |
|---|---|---|---|
| 长方体 | `CreateBlockFeatureBuilder` | ✅ | §3.1 |
| 圆柱 | `CreateCylinderBuilder` | ✅ | 见 journal 技能 §5.2 |
| 球 | `CreateSphereBuilder` | ✅ | §8 椭球基底 |
| 圆锥 | `CreateConeBuilder` | 🟡 | 文档存在 |
| 管（沿路径） | `CreateTubeBuilder` | 🟡 | 文档存在 |
| 拉伸 | `CreateExtrudeBuilder` | ✅ | §3.3 |
| 旋转 | `CreateRevolveBuilder` | ✅ | 旧绕行法依赖它 |
| 缩放 | `CreateScaleBuilder` | ✅ | §8 椭球 |

### 13.2 扫掠 / 放样（**更正：本绑定"无 Loft"是错的**）
| 特征 | 工厂 | 状态 | 备注 |
|---|---|---|---|
| 扫掠 | `CreateSweptBuilder` | 🟡 | 比 Loft 更强，可做放样/扫掠 |
| 通过曲线 | `CreateThroughCurvesBuilder` | 🟡 | 类放样 |
| 直纹面 | `CreateRuledBuilder` | 🟡 | |
| 沿引导扫掠 | `CreateSweepAlongGuideBuilder` | 🟡 | |
| 变截面扫掠 | `CreateVarsweepBuilder` | 🟡 | |
| 样式扫掠 | `CreateStyledSweepBuilder` | 🟡 | |

> ⚠️ 旧技能 §8 写"没有 Loft（`CreateLoftBuilder` 不存在）"——文档核查发现 `CreateLoftBuilder` 实际**不在 `FeatureCollection` 上**，但 `SweptBuilder`/`ThroughCurvesBuilder`/`RuledBuilder` 都在，**扫掠/放样类造型用它们即可**，无需 Loft。

### 13.3 阵列 / 镜像 / 布尔 / 编辑
| 特征 | 工厂 | 状态 | 备注 |
|---|---|---|---|
| 布尔（并/减/交） | `CreateBooleanBuilder` | ✅ | §5b |
| 阵列 | `CreatePatternFeatureBuilder` | 🟡 | 文档存在 |
| 镜像体 | `CreateMirrorBodyBuilder` | 🟡 | 文档存在 |
| 镜像特征 | `CreateMirrorFeatureBuilder` | 🟡 | |
| 移动（平移） | `CreateMoveObjectBuilder` | ❌ | §4.1 实机工厂缺失 |
| 移动体 | `CreateMoveBodyBuilder` | ✅ | §4.2 更正 |
| 移动面 | `CreateMoveFaceBuilder` | 🟡 | 含 `Types.RotateAboutAxis` |
| 分割体 | `CreateSplitBodyBuilder` | 🟡 | |
| 修剪体 | `CreateTrimBodyBuilder` | 🟡 | |
| 抽壳 | `CreateShellBuilder` | 🟡 | journal 技能 §5.5 已用 |
| 加厚 | `CreateThickenBuilder` | 🟡 | 面→体 |
| 拔模 | `CreateDraftBodyBuilder` | 🟡 | |
| 偏置面 | `CreateOffsetFaceBuilder` | 🟡 | |
| 倒圆 | `CreateEdgeBlendBuilder` | 🟡 | |
| 倒角 | `CreateChamferBuilder` | 🟡 | |
| 孔 | `CreateHoleFeatureBuilder` / `CreateHolePackageBuilder` | ✅ | journal 技能 §5.2 |
| 螺纹 | `CreateThreadBuilder` | 🟡 | |
| 文字（3D 浮雕） | `CreateTextBuilder` | 🟡 | 可做立体字 |

### 13.4 曲线 / 曲面 / 基准
- 曲线：`CreateArc`/`CreateLine`（✅ 免草图）、`CreateStudioSplineBuilder`、`CreateHelixBuilder`、`CreateLawCurveBuilder`、`CreateCompositeCurveBuilder`、`CreateProjectCurveBuilder`、`CreateSectionCurveBuilder`（🟡）。
- 曲面：`CreateSewBuilder`（缝合）、`CreateStudioSurfaceBuilder`、`CreateThroughCurveMeshBuilder`、`CreateOffsetSurfaceBuilder`、`CreateTrimSheetBuilder`、`CreateNSidedSurfaceBuilder`（🟡）。
- 基准：`CreateDatumAxisBuilder`/`CreateDatumPlaneBuilder`/`CreateDatumCsysBuilder`、`CreateCoaxialBuilder`/`CreateParallelBuilder`/`CreatePerpendicularBuilder`（🟡）。

### 13.5 直接建模 / 面编辑（🟡，文档存在，待验证）
`MoveFaceBuilder`、`DeleteFaceBuilder`、`ResizeFaceBuilder`、`ReplaceFaceBuilder`、`ExtractFaceBuilder`、`CopyFaceBuilder`、`OffsetRegionBuilder`、`EmbossBuilder`、`WrapBuilder` —— 这类"直接编辑面"工具能大幅简化有机造型，是下一步要重点真机验证的方向（一旦可用，比"球+缩放"更贴近真实曲面）。

## 14. ⚠️ 就绪判定假阳性修复 + "沙箱不能起 NX" 的运营现实（2026-09-18）

### 14.1 `nx_ready.py` 的假阳性（已修）
旧 `log_ready()` 只查日志里"是否出现过 `Ready on`"，但日志后面若打印了 `Server stopped`（桥掉了）
仍会误报 READY。2026-09-18 已改为：**只看"最近一次事件"**——若 `Server stopped` 出现在 `Ready on` 之后，判为未就绪。
→ `nx_ready.py --status` 现在反映真实桥状态，不会再让我白跑一轮 `run_python`。

### 14.2 真机测试 / 实时绘制的硬前提：NX 必须由用户在自己的会话里开着
- **实测结论**：在 WorkBuddy 工具/沙箱里用 `subprocess` 启动的 NX（`run_journal` 无界面也好、`ugraf` 也好），
  一旦启动它的那次工具调用结束，NX 进程就被回收，**桥随之消失**，后续 `run_python` 必 `actively refused / timed out`。
  （与 journal 技能 §0 记的"沙箱拉起 NX 拿不到许可会话"是同一类限制。）
- **因此**：`mcp__siemens-nx__run_python` / 实时驱动，**只在"用户本机交互式开着的 NX"上稳定可用**。
  这正是此前小鹏 P7、卡通狗能成功的原因（用户开着 NX）。
- **运营纪律**：要让桥在线、让我能"画个 X"或跑真机探针，用户需先**在自己机器上打开 NX 并保持开着**
  （双击桌面 `nx_start.bat`，或直接开 NX 即可）。我这边接活第一步仍是 `nx_ready.py --status`，
  拿到 `READY` 再建模/测试；若 `NOT_READY` 且 NX 没开，提示用户去开 NX（**不要**由我再 headless 起 NX，必死）。
- 真机探针脚本：`probe_nx_api.py`（枚举全部工厂 + 在未保存临时零件里试特征）、`probe_move.py`（平移实测）、
  `analyze_nx_api.py` / `extract_members.py` / `extract_tm.py`（离线解析 `NXOpen.xml` 出能力矩阵与 API 签名）。
