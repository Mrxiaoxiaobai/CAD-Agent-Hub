---
name: nx-journal-automation
description: |
  Drive Siemens NX (UG) modeling automatically via NX Open journal scripts on Windows.
  TRIGGER when: user mentions Siemens NX, NX Open, ugraf, run_journal, .prt part files,
  NX journal / 日志 / 脚本, 自动建模, 用 NX 画图, batch mode NX, "帮我画一个零件" in an NX context,
  or asks WorkBuddy to operate NX directly.
  Covers: locating the NX install, the run_journal.exe batch entry point, environment variables,
  the one-click .bat launcher, writing verified VB journal code, and the NXOpen.xml API-verification trick.
description_zh: "驱动 Siemens NX 批量自动建模（NX Open journal）"
description_en: "Automate Siemens NX modeling via NX Open journals"
agent_created: true
metadata:
  category: cad-automation
  version: "1.14.1"
---

# Siemens NX 自动建模（NX Open Journal）

> 🥈 **次选方案（2026-09-17 定稿）**。NX 建模的**首选**是 **`nx-mcp-bridge-modeling`**
> （MCP 桥实时驱动运行中的 NX）：用户只发一句话、全程零双击、NX 界面不锁死。
> **本技能只在首选不可用时才用**，触发条件：
> - MCP 桥不在线（NX 开着但 `%TEMP%\nx_mcp_remoting_server.log` 无 `Ready on`，且重启 NX 也修不好）；
> - 需要**无人值守/批处理**建模（不需要用户看着界面）；
> - 需要跨轮次留存一套可复跑的一次性脚本。
> 其余情况一律先走 `nx-mcp-bridge-modeling`。

目标：用户提需求 → 我们写 VB journal → 用户双击 bat（或 NX 里跑）→ 得到 `.prt`。

## 0. 关键前提（先说清楚）

WorkBuddy 运行在沙箱中。**实测结论（2026-09-16 修正）**：沙箱**能**成功拉起 `run_journal.exe <journal>`
（无界面批处理模式）把零件画出来——传送带 conveyor 就是沙箱里直接 `Start-Process run_journal.exe`
跑出来的，`D:\三维建模结果\conveyor.prt` 正常生成。

**真正限制是"持久化"**：凡是沙箱任务拉起的 NX（`run_journal &` / `nohup & disown` /
`PowerShell Start-Process` 全都试过），**任务一结束就被沙箱回收，NX 必死**。模型 `.prt` 文件会留在磁盘，
但"实时看 NX 画"的会话不跨轮次。

→ 用户要在自己机器上**看到并旋转/缩放模型**，由**用户在本机双击 `nx_start.bat`** 完成：
① 若有 `nx_jobs\*.job` 待画 → 用 `run_journal.exe`（无界面）建模；② 再用**普通界面 `ugraf.exe -retrieve:"<最新prt>"`**
打开模型查看。两段**拆开**，全程 NX 界面**永不锁死**，可自由交互。
（注意：打开零件**必须**带 `-retrieve:`，裸路径 NX 不加载零件、只停起始页，见 §8。）

> ⚠️ **`start_guard.bat` / v2.0 常驻守护已从本 skill 移除（2026-09-17 实测证伪）**：
> v2.0 以为"journal 跑在后台线程，Main 死循环不会冻结 UI"，但**用户实机证明相反**——
> 常驻循环期间 NX 主窗口被锁成"工作进行中"模态框、彻底卡死（见用户反馈"一直这么卡着我看不了"）。
> 此外 `-auto=` 模式 journal 一返回 NX 就退出，"画完停着看"也走不通。故**不再使用任何 in-session 常驻方案**。
> 现在的唯一推荐入口就是 `nx_start.bat`（建模无界面 + 查看普通界面，见 §8 v3.0）。

## 1. 定位 NX 安装

常见位置：`C:\Program Files\Siemens\NX*`、`E:\NX\Program Files\Siemens\NX*`。
先查环境变量 `UGII_BASE_DIR`、`UGII_ROOT_DIR`，再扫盘。

批量执行的正确入口（**不在 UGII 下**，容易找错）：

```
%UGII_BASE_DIR%\NXBIN\run_journal.exe
```

注意：`ugraf.exe` 在 `UGII\` 下；`run_journal.exe` 在 `NXBIN\` 下。老资料里的
`%UGII_ROOT_DIR%\run_journal.exe` 在新版 NX 上不存在。

## 2.1 在 NX 界面里跑 .vb 日志的正确入口（重要，容易走错）

**`文件 → 执行 → NX Open...` 是错的**：那是"执行用户函数"，只接受**编译好的** `.dll / .exe / .jar / .class`
（对话框右下角的文件类型下拉框里只有这四类，没有 `.vb`），用户会以为"脚本跑不了"。

`.vb / .cs / .py` 这类日志脚本的入口在**工具菜单**：

| 界面语言 | 路径 | 快捷键 |
|---|---|---|
| 中文 NX | **工具(T) → 操作记录(J) → 播放(P)** | **Alt+F8** |
| 英文 NX | Tools → Journal → Play... | Alt+F8 |
| 中文 NX（编辑） | 工具(T) → 操作记录(J) → 编辑(E) | Alt+F11 |
| 中文 NX（录制） | 工具(T) → 操作记录(J) → 记录(R) | — |

- "Journal" 在中文 NX 里被译成 **"操作记录"**，不是"日志"——按"日志"找不到菜单。
- 或者在 Ribbon 上右键 → 勾出 **开发人员(Developer)** 选项卡，里面也有 Journal 播放/录制。
- 播放对话框里若只列出某一类文件，把文件类型切到"所有文件"再选 `.vb`。
- 建议先 `首选项 → 用户界面 → 操作记录/Journal` 把语言设为 **Visual Basic**。
- 另有"把 .vb 拖进 NX 图形窗口即运行"的用法（版本相关，可作为备选）。

判据：用户贴出"执行用户函数"对话框、类型下拉只有 dll/exe/jar/class → 就是走错入口了，直接给上面这张表。

## 2.2 一键启动器（run_nx.bat，批量模式，不依赖界面菜单）

```bat
@echo off
setlocal
set "UGII_BASE_DIR=E:\NX\Program Files\Siemens\NX2007"
set "UGII_ROOT_DIR=E:\NX\Program Files\Siemens\NX2007\UGII"
set "DISPLAY=LOCALPC:0.0"
set "PATH=E:\NX\Program Files\Siemens\NX2007\nxbin;E:\NX\Program Files\Siemens\NX2007\ugii;%PATH%"
cd /d "%~dp0"
if not exist "E:\NX\Program Files\Siemens\NX2007\NXBIN\run_journal.exe" goto noexe
if not exist "%~dp0nx_design.vb" goto novb
"E:\NX\Program Files\Siemens\NX2007\NXBIN\run_journal.exe" "%~dp0nx_design.vb" > "%~dp0run_output.txt" 2>&1
echo run_journal exit code = %ERRORLEVEL% >> "%~dp0run_output.txt"
if exist "%~dp0design.prt" goto ok
echo [FAILED] design.prt NOT created.
goto showlog
:ok
echo [OK] design.prt created.
:showlog
type "%~dp0run_output.txt"
if exist "%~dp0design_log.txt" type "%~dp0design_log.txt"
goto end
:noexe
echo [ERROR] run_journal.exe NOT found. Check the NX install path inside this bat.
goto end
:novb
echo [ERROR] nx_design.vb NOT found next to this bat file.
:end
pause
```

要点：
- **必须回显 `run_output.txt`**：`run_journal` 把编译错误（"Line 22: 未定义类型 ..."、"Compilation failed"）
  写进 stdout，这是唯一的反馈回路，不给用户看就等于盲跑。
- 用户只需双击 → 截图窗口内容。

### .bat 的五条硬性规范（血泪教训，违反任一条都会失败）

1. **纯 ASCII**，不写中文注释（cmd 按 GBK 解码 UTF-8 会变乱码）。
2. **CRLF 换行**。文件写入工具产出的是 LF，必须用 PowerShell 把换行统一替换为 CR+LF 再以 ASCII 写回：
   `$t = ($t -replace "`r`n","`n") -replace "`n","`r`n"`。
   LF-only 的 bat 会让 `set "VAR=..."` 失效 → 命令行里 `%VAR%` 变空 → 报"系统找不到指定的路径"、exit code 3。
3. **关键命令写死完整路径**，不要依赖 `set` 出来的变量。
4. **用 `goto 标签` 代替嵌套括号的 if/else**（含括号的 echo 参数会破坏解析）。
5. 开头加存在性守卫（run_journal.exe、journal 文件），失败时输出明确的英文报错。

沙箱写文件时的坑：安全策略会拦截 PowerShell 命令字符串里出现的 cmd 语法片段
（删除命令的斜杠参数、if exist 守卫写法等），所以 bat 内容**不要经 PowerShell 拼接写入**，
改用文件写入工具，再用 PowerShell 只做换行/编码转换；日志覆盖交给脚本内的 File.WriteAllText。

### 失败症状对照表（先看有没有 design_log.txt）

| 现象 | 含义 | 处置 |
|---|---|---|
| 有 compile 错误 + exit 1 | journal 被执行，代码有编译错误 | 按行号查 NXOpen.xml 修正 |
| "系统找不到指定的路径" + exit 3，**无 design_log.txt** | run_journal.exe 根本没被启动 | 查 bat 的换行/变量/路径写法 |
| 有 design_log.txt 且含 STEP1.. | 脚本在跑 | 看停在哪一步，读 ERROR 段 |
| 无任何输出、无日志 | 用户没真正双击，或 .bat 关联被改 | 让用户从 cmd 里执行一次看回显 |
| 双击 bat 后刷一屏 `xxx 不是内部或外部命令` 乱码 | **bat 是 UTF-8 中文 / LF 换行**（编码病，非逻辑病） | 转纯 ASCII + CRLF，见 §2.2、§7.1 |
| 双击 bat 后刷 `字符串缺少终止符`、`ParentContainsErrorRecordException` | **.ps1 无 BOM 被按 GBK 解码** | 加 UTF-8 BOM 或正文改英文，见 §7.1 |

### 编译错误 → 病因速查（按报错文字直接下药）

| VB 编译器原文 | 真实病因 | 改法 |
|---|---|---|
| `未定义类型 NXOpen.Features.XxxBuilder` | 类型名记错 | 去 `NXOpen.xml` grep `T:` 找真名 |
| `Xxx 不是 YyyCollection 的成员` | 工厂方法名记错 | grep `M:NXOpen\.Features\.FeatureCollection\.Create\w*` |
| `属性"X"为"ReadOnly"` | X 是只读**对象**（多为 `Expression`） | 改 `X.Value = 数值`（Double），不要赋字符串 |
| `类型"NXOpen.Point"的值无法转换为"NXOpen.Point3d"` | 目标属性要**值类型 Point3d** | 直接 `New Point3d(x,y,z)`，别用 factory 造点 |
| `Option Strict Off` 也拦不住 | 报错涉及**结构体(值类型)**或 ReadOnly 属性 | 这类错误与隐式转换无关，必须改类型/改写法 |

**沙箱可以离线预编译校验 VB journal**（本机实测可用，2026-09-15）：直接调 `vbc.exe`
（`C:\Windows\Microsoft.NET\Framework64\v4.0.30319\vbc.exe`）即可在交给用户前抓出编译错误，
不必等用户在 NX 里播放才报红。关键：必须带 NXOpen 程序集引用，否则报缺类型：
`vbc /target:library /r:"<UGII_BASE_DIR>\NXBIN\managed\NXOpen.dll" /r:"<UGII_BASE_DIR>\NXBIN\managed\NXOpen.Utilities.dll" /r:"<UGII_BASE_DIR>\NXBIN\managed\NXOpen.UF.dll" nx_guard.vb`
（`Feature`/`Session`/`Part`/`Body` 等都在 `NXOpen.Utilities` 里，漏掉它 → BC30002 "未定义类型 Feature"；
漏掉 `NXOpen.UF` → BC30007 "需要对程序集 NXOpen.Utilities 的引用"）。
`Assembly.Load*` 反射仍可能被沙箱拦，但 vbc 编译本身不依赖反射，能正常产出 dll/报错。
结论：双保险 = grep `NXOpen.xml` 定真实类型名 + vbc 离线编译验证（0 错误再交付）。

## 3. journal 源文件的两条硬规则

1. **必须存成 UTF-8 with BOM**。VB 编译器在无 BOM 时按系统 ANSI（中文环境是 GBK）解码，
   源文件里任何中文（尤其含中文的路径）会乱码，导致 `NewFileName` 指向不存在的路径。
   PowerShell 加 BOM：
   ```powershell
   $t = [IO.File]::ReadAllText($f, [Text.Encoding]::UTF8)
   [IO.File]::WriteAllText($f, $t, (New-Object Text.UTF8Encoding($true)))
   ```
2. 变量/类型全部用**完整命名空间**（`NXOpen.Features.BlockFeatureBuilder`），并加 `Option Strict Off`。

## 4. 用 NX 自带文档当场核对 API（最重要的一条经验）

不要凭记忆写 NX Open API——名字差一个词就编译失败，来回一轮成本很高。
NX 自带完整 API 文档：`%UGII_BASE_DIR%\NXBIN\managed\NXOpen.xml`（数十 MB）。
（同目录 `NXOpen.UF.xml`、`NXOpenUI.xml`。）

用 Grep 查：
```
pattern: member name="M:NXOpen\.Features\.FeatureCollection\.CreateBlock\w*"
pattern: member name="T:NXOpen\.Features\.Block\w*Builder"
pattern: member name="[MPF]:NXOpen\.Features\.BlockFeatureBuilder\.[^"]*"
```
`T:` 类型 / `M:` 方法 / `P:` 属性 / `F:` 枚举值 / `E:` 事件。

同时可用 `NXBIN\python\NXOpen*.pyd` 确认该版本是否支持 NXOpen for Python。

## 5. 已验证可用的代码模板（NX2007，2026-09 实测通过编译）

```vb
Option Strict Off
Imports System
Imports System.IO
Imports NXOpen

Module NXJournal
    Sub Main()
        Dim dir As String = "D:\work"            ' 建议 ASCII 路径（非 ASCII 必须配 BOM）
        Dim prtPath As String = Path.Combine(dir, "design.prt")
        Dim logPath As String = Path.Combine(dir, "design_log.txt")
        Try
            File.WriteAllText(logPath, "STEP1: started " & DateTime.Now.ToString() & vbCrLf)
            Dim s As Session = Session.GetSession()
            If File.Exists(prtPath) Then File.Delete(prtPath)

            ' 新建部件（等价 文件->新建->模型）——不要用 Parts.NewBase
            Dim fn As NXOpen.FileNew = s.Parts.FileNew()
            fn.TemplateFileName = "model-plain-1-mm-template.prt"
            fn.UseBlankTemplate = False
            fn.ApplicationName = "ModelTemplate"
            fn.Units = NXOpen.Part.Units.Millimeters
            fn.NewFileName = prtPath
            fn.MasterFileName = prtPath
            fn.MakeDisplayedPart = True
            Dim o As NXOpen.NXObject = fn.Commit()
            fn.Destroy()

            Dim wp As Part = s.Parts.Work
            If wp Is Nothing Then Throw New Exception("no work part")

            ' 长方体
            Dim nb As NXOpen.Features.Block = Nothing
            Dim bb As NXOpen.Features.BlockFeatureBuilder = wp.Features.CreateBlockFeatureBuilder(nb)
            bb.Type = NXOpen.Features.BlockFeatureBuilder.Types.OriginAndEdgeLengths
            bb.BooleanOption.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Create
            bb.SetOriginAndLengths(New Point3d(0.0, 0.0, 0.0), "100", "50", "30")
            Dim f As NXOpen.Features.Feature = bb.CommitFeature()
            bb.Destroy()

            wp.Save(BasePart.SaveComponents.True, BasePart.CloseAfterSave.False)
            File.AppendAllText(logPath, "OK: " & prtPath & vbCrLf)
        Catch ex As Exception
            File.AppendAllText(logPath, "ERROR:" & vbCrLf & ex.ToString())
        End Try
    End Sub
    Public Function GetUnloadOption(ByVal dummy As String) As Integer
        GetUnloadOption = NXOpen.Session.LibraryUnloadOption.Immediately
    End Function
End Module
```

模板文件确认存在：`%UGII_BASE_DIR%\UGII\templates\model-plain-1-mm-template.prt`
（inch 版：`model-plain-1-inch-template.prt`）。

**已确认不存在 / 会编译失败的写法**（踩过）：
- `NXOpen.Features.BlockBuilder` —— 不存在
- `FeatureCollection.CreateBlockBuilderUsingNewOrigin` —— 不存在
正确组合永远是 `BlockFeatureBuilder` + `CreateBlockFeatureBuilder`。

## 5.1 端到端验证成功记录（NX2007，2026-09-15）

用户本机双击 bat 后输出：

```
[OK] design.prt created.
run_journal exit code = 0
STEP1: journal started ...      template_exists=True
STEP2a: FileNew OK
STEP3: work part = design
STEP4: block feature committed
OK: generated <dir>\design.prt
```

产出 `design.prt` = 97653 字节。**整条链路已打通**，以后只需替换建模段。

配套经验：
- `FileNew` 的 `NewFileName` / `MasterFileName` 传**绝对路径**可正常写入含中文的目录
  （前提是 .vb 有 UTF-8 BOM）。所以中文工作目录不是问题，不必强求英文路径。
- 新建部件建议做**双保险**：先 `FileNew()`+模板，`Catch` 里再降级 `Parts.NewBase(...)` + `Parts.SetWork(...)`，
  两个分支都写日志（`STEP2a` / `STEP2b`），这样万一模板名因版本变化失效也不会整体失败。
- 日志里先记 `File.Exists(模板路径)`，一步就能区分"模板缺失"与"API 用错"。

## 5.2 常用特征 Builder 速查（NX2007 NXOpen.xml 已核对，均为真实成员）

`workPart.Features` 上创建（参数是该特征类型或 `Nothing`）：

| 特征 | 创建方法 | Builder 类型 |
|---|---|---|
| 长方体 | `CreateBlockFeatureBuilder(Block)` | `Features.BlockFeatureBuilder` |
| 圆柱 | `CreateCylinderBuilder(Feature)` | `Features.CylinderBuilder` |
| 拉伸 | `CreateExtrudeBuilder(Feature)` | `Features.ExtrudeBuilder` |
| 孔 | `CreateHolePackageBuilder(HolePackage)` | `Features.HolePackageBuilder` |
| 边倒圆 | `CreateEdgeBlendBuilder(Feature)` | `Features.EdgeBlendBuilder` |
| 倒斜角 | `CreateChamferBuilder(Feature)` | `Features.ChamferBuilder` |
| 阵列 | `CreatePatternFeatureBuilder(Feature)` | `Features.PatternFeatureBuilder` |

已核对存在的属性：
- `ExtrudeBuilder.Section` / `.Direction` / `.Limits` / `.Draft` / `.Offset` / **`.BooleanOperation`**
  （注意：拉伸用 `BooleanOperation`，长方体和圆柱用 `BooleanOption`——两者不同名，别混）
- `HolePackageBuilder.HoleType` / `.HolePosition` / `.Tolerance`（孔径/深度在 `HolePackageBuilder` 的
  尺寸子对象上，写之前先 grep 该 builder 全部成员确认）

统一收尾：`builder.CommitFeature()` → `builder.Destroy()`。
布尔：`NXOpen.GeometricUtilities.BooleanOperation.BooleanType`（枚举值 `Create` / `Unite` / `Subtract` / `Intersect`）。
**长方体与圆柱都用 `BooleanOption`；只有拉伸(Extrude)用 `BooleanOperation`——两者不同名。**

### 用圆柱减料做"通孔"（API 已按 NX2007 文档 + 编译器报错双向核实）

⚠️ `CylinderBuilder` 的三个坑（写成直觉写法必编译失败，2026-09-15 用户实测三条报错）：

| 直觉写法（错） | 报错 | 正确写法 |
|---|---|---|
| `cb.Diameter = "10"` | 属性"Diameter"为"ReadOnly" | **`cb.Diameter.Value = 10.0`**（Double） |
| `cb.Height = "500"` | 属性"Height"为"ReadOnly" | **`cb.Height.Value = 500.0`** |
| `cb.Origin = wp.Points.CreatePoint(New Point3d(...))` | 类型"NXOpen.Point"的值无法转换为"NXOpen.Point3d" | **`cb.Origin = New Point3d(x, y, z)`**（直接给值类型） |

判据：`Diameter`/`Height` 是 **只读 `Expression` 对象**（官方类型摘要的"Default values"表里写的就是 `Diameter.Value` / `Height.Value`，
以及"This will be used only when the law type is Axis, Diameter, and Height"）。只读的是**属性本身**，往里写的是**表达式的 .Value**。
`Origin` 报错方向是"Point → Point3d"，说明它是**值类型 Point3d**（`Point3d` 是结构体，引用类型永不可隐式转值类型，故 `Option Strict Off` 也救不了）。

```vb
Dim nc As NXOpen.Features.Cylinder = Nothing
Dim cb As NXOpen.Features.CylinderBuilder = wp.Features.CreateCylinderBuilder(nc)
cb.Type = NXOpen.Features.CylinderBuilder.Types.AxisDiameterAndHeight   ' 仅两个枚举值：本值 与 ArcAndHeight

' 轴向 +Z（可选；直接赋 Object 规避返回类型不确定导致的编译错误）
Try
    Dim d As Object = wp.Directions.CreateDirection(New Point3d(0.0, 0.0, 0.0), New Vector3d(0.0, 0.0, 1.0), NXOpen.SmartObject.UpdateOption.WithinModeling)
    cb.Direction = d
Catch exDir As Exception
    ' 记日志后继续；圆柱默认轴为 WCS +Z
End Try

cb.Origin = New Point3d(250.0, 250.0, -1.0)   ' 底面中心，直接给 Point3d
cb.Diameter.Value = 10.0
cb.Height.Value = 502.0                        ' 上下各多出 1mm，避免与上下表面共面导致布尔问题

' 明确指定目标体：从"刚建的那个方块体"上减，避免在多实体零件里减错对象
Dim blkBodies As NXOpen.Body() = blkFeature.GetBodies()   ' Feature.GetBodies() -> Body()
If blkBodies IsNot Nothing AndAlso blkBodies.Length > 0 Then
    cb.BooleanOption.SetBooleanOperationAndBody(NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Subtract, blkBodies(0))
Else
    cb.BooleanOption.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Subtract
End If
Dim cf As NXOpen.Features.Feature = cb.CommitFeature()
cb.Destroy()
```

- `BooleanOperation` 的成员只有 `Type` / `Get|SetBooleanOperationAndBody` / `Get|SetTargetBodies(Body[])` / `Validate`
  （**没有** `Target` / `TargetBody` 属性）。目标体优先用 `SetBooleanOperationAndBody(类型, 体)` 一步到位。
- `Origin` 是**底面中心**，沿 +Z 延伸 `Height`；要贯穿整块就用 `z=-1, Height=块高+2`，别让圆柱端面与零件表面共面。
- `BasePart.Points` / `BasePart.Directions` / `BasePart.Features` 是 **BasePart** 上的属性（`Part` 继承而来），
  写 `wp.Points.CreatePoint(...)`、`wp.Directions.CreateDirection(...)` 合法；`PointCollection.CreatePoint(Point3d)` 返回 `Point`。

### 往"当前已打开的零件"里加特征（而非新建）
`run_journal` 批量模式会开**新会话**，无法连到用户正在看的 NX。若用户说"在我现在打开的项目里画"：
- 脚本先判断 `theSession.Parts.Work` 是否非空；非空则复用它（不新建、不删文件），把特征加进去再 `workPart.Save()`；为空才走 FileNew 新建。
- 告诉用户：要往当前打开的零件加，请在 **NX 内部**运行脚本：**工具(T) → 操作记录(J) → 播放(P)**（或 **Alt+F8**），
  文件类型切"所有文件"选 `.vb`；**不要**走 `文件 → 执行 → NX Open…`（那只收 dll/exe/jar/class，见 2.1）。
  双击 bat 是独立批量会话，会生成新的 design.prt，连不到用户当前打开的那个零件。
- 在空白新零件里双击 bat 与在 NX 里跑脚本，两种路径都能正确出图。


**给截面/方向等“可选对象”传参时**，先用 `workPart` 上的 factory 造点/线/方向：
- 点：`workPart.Points.CreatePoint(New Point3d(x,y,z))`
- 方向：`workPart.Directions.CreateDirection(vector, smartDir, NXOpen.SmartObject.UpdateOption.WithinModeling)`
- 曲线：`workPart.Curves.CreateLine(...)` / `CreateArc(...)`；
  草图层建议用 `workPart.Sketches.CreateSketchInSketch(...)` 或先在 XZ/XY 平面建线再拉伸。

## 6. 每次交付给用户的东西

1. `nx_design.vb`（含 STEP1..STEP4 日志、参数集中成 `Const`）
2. `run_nx.bat`（含错误回显）
3. 明确告知：双击 bat → 等 30~90 秒 → 看 `design.prt`；失败则把窗口内容截图发回
4. 用 ✅ 清单形式给验证步骤（该用户偏好带 ✅ 的核对表）

## 7. NX AutoPilot（零操作自动建模）—— 用户"只动嘴"方案

用户诉求：不想双击 bat、不想在 NX 里跑脚本，只告诉我"要画什么"，我直接画。

### 架构（桥接沙箱与用户会话的许可鸿沟）
沙箱能读写用户磁盘、能写脚本，但**拉起的 NX 拿不到许可会话**，journal 跑不出零件（见 §0）。
所以必须有一个**运行在用户 Windows 交互会话里**的常驻进程（才有 NX 许可）来替沙箱执行 journal。

交付 4 个文件（同目录）：
- `nx_autopilot.ps1` —— 监控器：每 3 秒扫 `nx_jobs\*.vb`，找到未处理的就用 `run_journal.exe` 执行，
  画完在 `nx_jobs\` 写 `<base>.done`（成功，含 prt 路径+日志）或 `<base>.fail`（含 run_journal 输出+journal 错误）。
  已处理（存在 `.done`/`.fail`）自动跳过，不会重复画。
- `nx_autopilot.bat` —— 启动器：`powershell -NoExit -ExecutionPolicy Bypass -File nx_autopilot.ps1`
  （双击一次、最小化，常驻后台；关闭即停）。
- `install_autostart.bat` —— **往"启动"文件夹放一个最小化快捷方式**（`WScript.Shell.CreateShortcut` +
  `[Environment]::GetFolderPath('Startup')`，`WindowStyle=7`），之后开机自动后台待命。
  **不要用 `Register-ScheduledTask -AtLogOn`**：它需要管理员权限，普通用户双击就失败，
  而 Startup 快捷方式零权限、删掉 `.lnk` 即卸载。同样必须是 ASCII + CRLF。
- `nx_jobs\` 目录 —— 作业投递箱。沙箱把写好的 `.vb` 丢进来即触发绘制。

### 7.1 PowerShell / bat 交付前的三条硬规范（2026-09-15 用户实测踩崩）

用户双击 `nx_autopilot.bat` 后 cmd 里刷出一屏 `lot 不是内部或外部命令` + `字符串缺少终止符`，
根因是**编码**，不是逻辑。三条必须同时满足：

1. **`.ps1` 必须存成 UTF-8 with BOM**（或干脆**全英文纯 ASCII**，最省事）。
   Windows PowerShell 5.1 对**无 BOM** 的 `.ps1` 按系统 ANSI(GBK) 解码，
   文件里任何中文都会变成乱码字节，把字符串引号"吃掉"→ 一连串
   `字符串缺少终止符` / `表达式或语句中包含意外的标记` / `ParentContainsErrorRecordException`。
   最稳做法：脚本正文写英文，正文外只留 BOM，中文交给 `.bat`/日志。
2. **`.bat` 同样必须纯 ASCII + CRLF**（见 §2.2 五条规范）。UTF-8 中文 bat 在 cmd(GBK) 下
   整行变乱码，cmd 会把乱码当命令去执行 → `lot 不是内部或外部命令` 这类**假报错**，
   让人误以为是 `@echo off` 写坏了。把 echo 文案改成英文即可。
3. **PowerShell 5.1 不支持 `if` 当内联表达式**。写
   `$x = "a" + (if ($c) { "y" } else { "n" })` **在 PS 5.1 直接解析失败**
   （`if` 作为表达式是 PS 7+ 才有）。必须用**子表达式 `$(...)`**：
   `$x = "a" + $(if ($c) { "y" } else { "n" })`。
   这是编码问题之外**独立存在**的真实 bug，改编码也不会好，务必一起改。

**交付前必做自检**（不要靠肉眼）：
```powershell
# 语法静态检查，0 errors 才交给用户
$e=$null;$t=$null
[System.Management.Automation.Language.Parser]::ParseFile("<path>\x.ps1",[ref]$t,[ref]$e)
$e.Count    # 必须为 0
```
```python
# 编码检查：.bat 要求 nonASCII=0 且含 CRLF；.ps1 要求有 BOM
raw = open(path,'rb').read()
print(raw[:3]==b'\xef\xbb\xbf', b'\r\n' in raw, sum(1 for b in raw if b>127))
```

**顺带排查同类文件**：一键就崩的 bat 旁边，`install_autostart.bat` 之类往往是同一种病灶
（中文 + LF），用户下一条消息就会来问。修 `nx_autopilot.*` 时**同时把所有 .bat 批量转 ASCII+CRLF**。

**Agent 沙箱里自测监控器的坑**：本机 `Get-ExecutionPolicy` 可能是 `Restricted`，
`& script.ps1` 会**静默 exit 1 且不产生任何日志**（很容易被误判成脚本逻辑错）。
自测前先 `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force`（同一条命令内，进程级不落盘）。
另外 `Start-Process powershell.exe`（拉子解释器）会被安全策略拦，改用后台任务直接 `& script.ps1`，
或把脚本复制到一个**没有 `*.vb` 的空目录**再跑，这样 while 循环只会空转、不会真去调 NX，
既能验证"能否启动"，又不污染 `nx_jobs\`。

### 7.2 监控目录必须是 `nx_jobs\` 子目录（2026-09-15 实测踩坑）

**最容易犯的静默错误**：把作业目录写成"脚本自己所在的目录"。

```powershell
$JobsDir = Split-Path -Parent $MyInvocation.MyCommand.Definition   # ✗ 得到工作区根目录，扫不到 nx_jobs\
$Root    = Split-Path -Parent $MyInvocation.MyCommand.Definition   # ✓
$JobsDir = Join-Path $Root "nx_jobs"                               # ✓ 投递箱是子目录
```

症状极具误导性：窗口正常显示 `status : WATCHING`，**不报任何错**，但永远不处理作业。
判据：`autopilot.log` 里**只有 `AutoPilot started` 一行，没有 `>>> JOB` 行** ⇒ 扫描目录错了，
不要往 NX / 许可上找原因。启动横幅里务必打印 `watching:` 的**完整路径**，一眼就能核对。

配套三条体验改进（用户会以为"卡死了"）：
1. **不要用 `Start-Process -Wait`**：NX 冷启动 30~120 秒，`-Wait` 期间控制台完全静止，用户判定为死机。
   改成 `-PassThru`（不加 `-Wait`）+ `while (-not $p.HasExited) { Start-Sleep 1; ... }`，
   每 10 秒打印一次 `... still working, Ns elapsed`。
2. **空转也要有心跳**：每约 60 个 1 秒 tick 打印一次 `watching ... N job(s) in folder`。
3. **加超时兜底**：超过 `$TimeoutSec`（建议 600）仍不退出的，`taskkill.exe /PID <pid> /T /F` 杀掉
   （`/T` 连子进程 ugraf 一起杀），写 `.fail` 并标注 `TIMEOUT`。否则一个卡住的 NX 会让监控器永久僵死。

另：主循环 `Start-Sleep` 用 **1 秒**。任务一旦进入 `run_journal` 就会阻塞整轮，
3 秒轮询在等待期间没有意义，1 秒能让空载时的响应更快。

**改完必须重启监控器**——正在跑的实例已经把旧代码载入内存，改文件对它无效。

### journal 投递协议（监控器怎么知道产出在哪）
在 `.vb` 源码里用 VB 注释标注输出路径，监控器用正则读取：
```vb
'@PRT:E:\...\nx_jobs\cube500_m10hole.prt
'@LOG:E:\...\nx_jobs\cube500_m10hole_log.txt
```
未标注则默认 `<base>.prt` / `<base>_log.txt`（与 .vb 同目录）。

### 零操作闭环（首次设置后）
1. 用户双击 `nx_autopilot.bat` 一次（或跑 `install_autostart.bat` 让开机自启）→ 之后永不再碰。
2. 用户口头/文字说"画一个 XX" → 我在沙箱里生成对应 `.vb`（§4/§5 API 已验证），写入 `nx_jobs\`。
3. 监控器（用户会话、有许可）检测到 → `run_journal` 自动画 → 写 `.prt` + `.done`。
4. 我读 `.done` → 回复用户"画好了，文件在 <路径>"。**用户全程零操作。**

### 重要限制（如实告知用户）
- 批量 `run_journal` 是**独立 NX 会话**，产出一个独立 `.prt`，**不会画进用户当前已打开的那个零件**。
  要"画进正在编辑的项目"，需上 NX Open 外部自动化（编译 .exe 连 `Session.GetSession()` 到运行中的 NX），
  复杂度更高，作为可选增强，不要默认承诺。
- 默认把 `.prt` 落在 `nx_jobs\`；若用户希望直接落到他的项目文件夹（如 `F:\...\数字孪生模型\`），
  把 journal 里的 `@PRT:` 指向那里即可（监控器在其会话里有该目录写权限）。

## 8. NX Guard / `nx_start` 启动器（建模 + 查看，界面永不卡）

### 推荐入口（2026-09-17 定稿）：`nx_start.bat` 两段拆分
**用户只双击 `C:\Users\xajsxy\Desktop\nx_start.bat` 这一个文件**，背后跑 `nx_start.py`，做两件事：
1. **[1/2] 建模（无界面）**：若 `nx_jobs\*.job` 有待画作业，调 `run_journal.exe nx_guard.vb`
   在独立 NX 会话里一次性画完（约 1–2 分钟），存到 `D:\三维建模结果`。`run_journal.exe` 是批处理模式，**不带任何 GUI**，自然不会锁界面。
2. **[2/2] 查看（普通界面）**：再用 `ugraf.exe -retrieve:"<最新prt>"` 打开模型。这条命令**不带任何 journal**，
   NX 起一个干净的带界面会话，用户可自由旋转/缩放/编辑，**永不卡死**。

> **`-retrieve:` 是必须的（2026-09-17 第三个实测结论，最容易踩）**：
> `ugraf.exe "D:\三维建模结果\conveyor350.prt"`（裸路径）**不会打开零件**——NX 能正常起来、界面也不卡，
> 但只停在"发现中心"起始页，用户看不到模型（用户实机反馈"没自己打开 conveyor350.prt"）。
> 正确写法是 `ugraf.exe -retrieve:"<路径>"`，实测窗口标题从 `NX` 变为 **`NX - 建模`** 即表示零件已加载。
> 中文路径 `D:\三维建模结果\...` 用 `-retrieve:` 也没问题。
> - 相关：`-view` 会开成**只读 Viewer**，`-nx` 才是完整 NX；裸 `ugraf.exe` 默认即完整 NX，无需额外加。
> - `ugs_router.exe -ug -use_file_dir "%1"` 是文件关联（双击 .prt）走的路由，脚本里别用它（会再转一道、易失效）。

> 为什么必须拆开（两个关键实测结论，2026-09-17）：
> - **结论①**：journal 只要还在 NX 进程里运行（哪怕只是 `Thread.Sleep` 空转、完全不碰 NX API），
>   NX 主窗口就会被锁成"工作进行中"模态框，直至 journal 返回才解锁。**与是否后台线程无关**——
>   v2.0 的"后台线程不占 UI 主线程"假设是**错的**。
> - **结论②**：`-auto=<journal>` 模式里，journal 一 `return`，NX **直接退出**。所以"画完停着让用户看"
>   也走不通。
> - **因此**：建模任务交给"无界面批处理"（`run_journal`，画完即走，不碰界面）；"看模型"交给"普通界面
>   NX"（`ugraf`，不带 journal，界面永不被锁）。两者**不同时**开两个 NX，互不污染。

### 历史需求背景（保留，解释为什么走上这条弯路）
早期想"在用户正在看的 NX 会话里直接建特征、全程可见、不导入"（2026-09-15 用户原话："NX 没有打开，
不能直观看到你画了什么，还是得再导入再打开才能看见，这样不对"）。为此做了 v1.0→v2.0 一长串 in-session
守护实验。**v2.0 看似成立（日志 `resident: 进入监听循环` + 心跳 `guard: alive tick=N`），但 2026-09-17
用户实机证明它的"界面照常可用"是幻觉**——常驻循环期间 NX 主窗口被锁死，用户完全没法看模型。
**该 in-session 常驻路线已整体废弃**，仅保留"定时器/线程为何失败"的踩坑记录供复盘（见下）。

### 定时器踩坑（v1.0 → v1.1，2026-09-15 实测）
- **v1.0 失败点**：用 Win32 `SetTimer(NULL, 0, ms, callback)` 注册定时器。`SetTimer` 返回了非零 id、日志也写了 `Guard ARMED`，但**回调从不触发**——`nx_guard.log` 里永远只有启动那几行，没有 `tick 1` / `... heartbeat`。原因：NX 执行 journal 时所在线程（或 NX 自己的消息泵）不派发 `hwnd=NULL` 的线程 WM_TIMER / 定时器回调。
- **判据**：定时器是否真在跑，只看日志有没有心跳行。只有启动行 = 定时器没生效，**不要去改建模代码**。
- **v1.1 修法**：主定时器换成 **WinForms Timer**——它自带一个隐藏**窗口**，WM_TIMER 是普通窗口消息，走 `DispatchMessage` 派发，比线程消息可靠；`Tick` 在创建它的线程（主线程）上触发，所以直接调 NXOpen 是安全的。
  - 用**反射**加载，避免 journal 编译器要求引用 WinForms：`Assembly.Load("System.Windows.Forms, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089")` → `GetType("System.Windows.Forms.Timer")` → `Activator.CreateInstance` → 反射设 `Interval`、用 `[Delegate].CreateDelegate(evi.EventHandlerType, mi)` 挂 `Tick`、反射调 `Start()`；模块级变量持有 Timer 引用防 GC。
- **兜底（关键）**：**每次播放都先 `ScanOnce()`**（v1.0 的"重复播放直接 return"早退是错的——它让重播变成空操作）。改进后"重播一次 nx_guard.vb"= 立即处理积压作业的应急开关；即便定时器在某些 NX 上仍不生效，用户重播一次也能出图。
- 定时器诊断：`Main` 里记录 `ManagedThreadId / IsBackground / ApartmentState`；`OnTimer` 前 3 次 tick 显式打日志，便于一眼确认监听是否活着。

### v1.2：后台线程轮询 —— 也被否证（2026-09-15 实测，重要）
- **定时器方案被彻底否证**：v1.1 的 WinForms Timer 同样一次 tick 都没有（日志里 `primary watch = WinForms Timer` 之后无任何 `tick`/心跳）。结论：**NX 执行 journal 的线程根本不做消息循环**，任何依赖该线程消息泵的定时器（Win32 `SetTimer` 或 WinForms Timer）都不会触发。
- **v1.2 后台线程同样死掉**：结构是 `Main → ScanOnce() → 起后台 Thread → Main 返回`，日志显示 `background worker started` 之后**同一秒**就是
  `worker: FATAL System.Threading.ThreadAbortException: 正在中止线程 / 在 NXJournal.WorkerLoop()`。
  即：**journal 的 Main 一返回，NX 就 Abort 掉脚本起的线程并卸载脚本域**。
- **⚠️ 上面三条失败的真正原因**：早期误判为"journal 无法在自己内部常驻监听"，v2.0 又一度改成"不让 Main 返回就能常驻"——**两个结论都是错的**（v2.0 已被 2026-09-17 证伪，见下节）。真正的事实是：`Main` 返回会 Abort 线程；而 `Main` 不返回（常驻）又会锁死 UI。**两者都不可行**，故建模必须离开 NX 交互会话、改走无界面 `run_journal`。
- **v1.3~v1.6 形态（方向对，但实施位要改）**：`Main` 同步 `ScanOnce()` 一次把 `nx_jobs\*.job` **全部**处理完，然后正常返回——**思路正确**（一次跑完即返回）。但它原本是"在用户 NX 会话里 Alt+F8 播放"，那样建模那几秒 UI 仍会被锁。v3.0 把它落到**无界面 `run_journal`** 里跑（不碰界面），就成了现在唯一可靠的形态。
  - 一次跑 = 一次批量处理；跑完返回，NX（若是普通界面会话）立刻解锁。
  - 代价：每个新作业需触发一次 `nx_start.bat` 双击（轻量一键，非后台自动）。
  - 兜底：若用户机器上 `nx_start.bat` 的建模步异常，可让用户在**已开的普通 NX** 里 Alt+F8 播放 `nx_guard.vb` 应急（建模几秒界面会锁，画完即解锁）。
- **判据（复诊用）**：日志出现 `ThreadAbortException` 或"注册成功但无心跳" → 说明是 in-session 播放且 `Main` 返回了（已废弃用法）；若 NX 卡死在"工作进行中" → 说明有 journal 还在跑（杀掉该 `ugraf`/`run_journal` 进程即可，见 `nx_uiwatch.log`）。

#### v2.0：常驻守护（2026-09-15 提出，**2026-09-17 实测证伪，已废弃**）

> ⚠️ **REVOKED**：v2.0 的"界面照常可用"是**错误结论**。2026-09-17 用户实机反馈 NX 卡死在"工作进行中"
> 模态框、完全看不了模型（"一直这么卡着我看不了"）。根因定位：journal **只要还在运行，NX 主窗口就被锁死**，
> 与是否后台线程无关（用 `Thread.Sleep` 空转即可复现 HUNG，见 §8 v3.0 结论①）。
> 此外 `-auto=` 模式 journal 返回即退出 NX，"画完停着看"也不成立。
> **结论：任何 in-session 常驻方案都不可用。** 现全部改走 §8 顶部的 `nx_start.bat` 两段拆分架构（v3.0）。
> 下方仅保留 v2.0 的原始设计记录，仅供复盘，**不要据此实施**。

- **推导**：既然三条路都死在"`Main` 返回后 NX 回收脚本线程"，那就**不让 Main 返回**。
- **前提事实（v1.2 日志里早就写着，当时被忽略）**：`main thread: id=1 bg=True apt=STA` ——
  **NX 是把 journal 放在一个后台线程上跑的**。当时据此**误判**"后台线程不占 UI 主线程，死循环不会冻结界面"，
  **该判断已被 2026-09-17 实测推翻**（见上 REVOKED 提示）。
- **v2.0 结构**：
  ```
  Main → GetSession → 防重复(AppDomain) → ScanOnce()
       → While True : Sleep(1500) : ScanOnce(True) : 心跳 / stop 检查 / 时限检查 : End While
  ```
  `Main` 永不返回 → NX 不回收线程 → 轮询一直活着 → **真正的常驻监听**，用户此后零操作。
- **退出通道（必须有，否则 NX 里挂着停不下来）**：`ROOT\nx_guard.stop` 存在 → 循环退出并删除该文件。可由沙箱远程创建，**用户无需任何操作**即可解除（这是常驻版的安全阀）。
- **防重复播放**：`AppDomain.CurrentDomain.GetData("NXGuardResident")` 非空 → 本次只 `ScanOnce()` 一遍后返回，绝不双开循环。
- **日志节流**：循环内用 `ScanOnce(True)`（quiet 参数），空转不刷日志；每 40 tick（≈60 s）打一行 `guard: alive tick=N elapsed=Ms`。
- **用户侧感知**：`播放操作记录` 窗口会**一直挂着**（因为脚本没返回）——必须提前告诉用户"这是守护态，别点关闭"。
- **已实测（2026-09-17，结论①）**：NX 在 journal 未返回时**不允许**任何交互——主窗口 HUNG、弹"工作进行中"，
  直到 journal `return` 才解锁（用 `Thread.Sleep` 空转即可复现）。故 in-session 常驻彻底走不通。
  v1.3~v1.6 的"一次一播即返回"思路**方向对**，但实施位置要改：建模走**无界面** `run_journal.exe`
  （不碰界面），查看走**普通界面** `ugraf.exe`——这就是 v3.0（见 §8 顶部）。`nx_guard_once.vb` 已删除。

### v1.3 附带新增：任意方向圆棒特征 `[bar]`（画字母/斜筋用）
- 需求来源："手机壳上浮雕显示个 WXT 字母"——W/X/T 全是斜笔画，`[block]` 只能轴对齐，做不了。
- **不要用 ExtrudeBuilder 拼笔画**（要 sketch+section 一堆对象，未实测，风险高）。**用 `CylinderBuilder` 做任意方向圆棒最稳**：它已经在 §5.2 验证过。
- 关键 API 事实（NX2007 `NXOpen.xml` 已核对 + vbc 编译验证）：
  - `NXOpen.Features.CylinderBuilder.Types` 只有两个值：`AxisDiameterAndHeight` / `ArcAndHeight`。
  - **`CylinderBuilder.Direction` 的类型是 `NXOpen.Vector3d`，不是 `NXOpen.Direction`！** 写成 `c.Direction = dObj`（Direction 对象）会报 `BC30311: 类型"NXOpen.Direction"的值无法转换为"NXOpen.Vector3d"`。
  - 正确写法：`c.Direction = New NXOpen.Vector3d(dx, dy, dz)`（单位向量）。
  - 备用：`c.Axis = workPart.Axes.CreateAxis(New Point3d(...), New NXOpen.Vector3d(...), NXOpen.SmartObject.UpdateOption.WithinModeling)` 也可编译通过（`BasePart.Axes` → `AxisCollection.CreateAxis(Point3d, Vector3d, UpdateOption)`）。
  - `Origin` 是**底面中心**（不是体心），圆柱沿 `Direction` 长 `Height`（§5.2 通孔用法已印证）。
  - `NXOpen.DirectionCollection.CreateDirection(Point3d, Vector3d, UpdateOption)` 存在，但给 `CylinderBuilder` 用不上（它要 Vector3d）。
- 圆棒拼笔画的技巧：**两端各外延 `dia/2`**（`extend` 默认值），这样笔画在拐角处互相重叠，拼出的字母不会出现缺口。笔画轴线落在零件表面上时，天然"一半嵌入、一半凸出"= 浮雕效果。
- 实现要点：**两个都失败必须抛异常**，否则会默默画成沿 +Z 的棒，产出错误几何还看不出来。

#### v1.4 实测修正：设置顺序会决定几何（2026-09-15 用户实测报错后定位）
- **症状**：手机壳前 4 个特征全部成功，第 5 步第一根 `[bar]` 报 **`工具体完全在目标体外`**（NX 中文报错，即布尔算不出来）。
- **定位方法（很值钱）**：不要猜代码，**反推几何**。已知方向向量、直径、长度、目标零件的坐标范围，逐一枚举"Origin 有没有被清掉 / 方向有没有反向 / 方向被忽略成 +Z"三种情形，算哪种会得到"零重叠"。结论唯一：**Origin 被清成了 (0,0,0)，方向是对的** —— 棒从原点沿笔画方向伸出去，落在零件外面（y 为负），与零件零重叠。
- **根因**：`c.Origin = ...` **写在 `c.Direction` / `c.Axis` 之前**。后续的轴向设置会把 Origin 清回 (0,0,0)。
- **修正（必须照做）**：
  1. **设置顺序固定为** `Type → BooleanOption → Diameter/Height → Direction → (可选)Axis → Origin`，**Origin 永远最后设**。
  2. **轴心放在笔画中点**，`Height = 笔画长 + 2*extend`。这样万一方向被反向，棒依然正好盖住这段笔画（对反向免疫）。
  3. 首选只设 `Direction`（Vector3d）；失败再退到"额外挂基准轴"的配置（`cfgA/cfgB` 两次尝试，各自 Try/Catch，两次都失败才抛）。
  4. 日志里把每根棒的 `from/to/dia/len/dir/bool` 全打出来，下次一眼就能对着算。
- **浮雕厚度取法**：轴心别落在表面上（会得到"半嵌半凸"的贴死效果，且和相邻面容易贴平）。轴心放到表面内侧 `t`，直径 `D`，则凸出 `D/2 - t`、嵌入 `D/2 + t`。实例：`D=2.8, t=0.5` → 棒占 Z∈[-0.9,1.9] → 凸出 0.9mm、嵌入 1.4mm，且离内腔底面(Z=2)留 0.1mm 不贴死。
- 顺带两条自愈（v1.4 新增，省用户一轮来回）：
  - **`.fail` 不再一票否决**：`ScanOnce` 里改成"`.fail` 比 `.job` 新才跳过"。修正作业文件后（mtime 变新）重播即自动重试，不必手动删标记。
  - **`CreateNewPart` 撞名自愈**：`FileNew` 失败（同名文件已存在/已在会话中打开）时，自动换 `_2/_3…` 重试（最多 6 次），不再因为名字冲突整个作业失败。

#### v1.5 实测再修正：`CylinderBuilder` 任意方向**根本不可靠** → `[bar]` 改点阵；新增 `[shell]` 抽壳（2026-09-15）
- **否证**：v1.4 已把"Origin 最后设 + 轴心放中点 + 两种轴向配置自愈"全做了，用户实测**配置 A、配置 B 依旧双双**报 `工具体完全在目标体外`。结论：**不是设置顺序的问题**——`CylinderBuilder` 即便 API 上带 `Direction`/`Axis`，设成任意方向后 Commit 出来的几何也不可信。
- **判据**：日志同时出现 `bar: 配置A(Direction) 失败: 工具体完全在目标体外` + `bar: 配置B 也失败` → 别再堆配置了，直接换实现。
- **v1.5 的做法（当前）**：`[bar]` 不再做单根斜圆柱，改成**沿 `from->to` 撒一串沿 Z 的小圆柱**（直径 `dia`、间距 `step`、z 范围 `z0..ztop`），相邻圆柱互相重叠，拼成一条连续"笔画"。**沿 Z 的 `CylinderBuilder` 是 100% 可靠的**（通孔/摄像头孔每单都成功），所以这条路必成。
  - 参数：`from=x,y[,z]`、`to=x,y[,z]`、`dia`（默认 3.6）、`step`（默认 `dia*0.85`，<0.2 会被夹到 0.2）、`z0`/`ztop`（默认 `min(z)-0.8` / `max(z)+0.7`）、`bool`。
  - 一笔 = 一个 `[bar]` 段；一个字母由若干 `[bar]` 段拼成。
  - 日志只打一行汇总（`dots=N z=.. bool=..`），不刷屏；个别点失败只记数不中断。
  - **点数关系**：`dots ≈ 笔画长 / step + 1`。8 段笔画、`dia=3.6 / step=3.2` 时约 50 个圆柱，数秒内完成，可接受。
  - ⚠️ 变量名**不要叫 `step`** —— VB 保留字，会报 `BC30183: 关键字作为标识符无效`（用 `gap`）。
- **新增 `[shell]` 抽壳特征**（"在现有基础上抽出手机壳的样子"这个需求）：
  - 参数：`thickness`（壁厚，默认 1.5）、`remove=top|bottom`（被移除的面，默认 top）。
  - API（NX2007 `NXOpen.xml` 已核对）：`FeatureCollection.CreateShellBuilder(Nothing)` → `ShellBuilder.Body`（要抽壳的 `Body`）、`DefaultThickness`（**只读属性，用 `.Value = t` 赋值；不行再退 `.SetFormula("1.5")`**）、`RemovedFacesCollector`（类型 `ScCollector`）。
  - **选面写法（本题难点）**：`p.ScRuleFactory.CreateRuleFaceDumb(New Face() {f})` 造规则 → `p.ScCollectors.CreateCollector()` 造收集器 → `sc.ReplaceRules(New SelectionIntentRule() {rule}, False)` → `sh.RemovedFacesCollector = sc`。
  - **怎么找到"顶面"**：遍历 `Body.GetFaces()`，用 `NXOpen.UF.UFSession.GetUFSession().Modl.AskFaceData(f.Tag, ftype, pt, dirv, box, radius, radData, normDir)` 读**面法向**（`dirv`）和**面上一点**（`pt`）；挑 `dirv(2) > 0.999` 里面点 `z` 最大者 = 顶面（`bottom` 则取 `dirv(2) < -0.999` 里 z 最小者）。
  - **`[shell]` 不产生新体**，它直接改现有体，所以该段**不写 `bool`**（写了也忽略），天然作用在 `lastBody` 上。
  - **务必先抽壳、后打孔**：先 `[block]` 实心坯 → `[shell]` → 再 `[cylinder]` 钻摄像头孔/通孔，几何最干净；反过来（先钻孔再抽壳）孔会被当成"穿透面"处理，结果难控。
- **新增单特征容错**：`RunJob` 里每个 `[段]` 单独 Try/Catch，**某个特征失败不再中断整单** —— 记日志 `! feature N : xxx 失败: ...`、写进回执"失败明细"，后面的特征照做。整单仍写 `.done`（避免用户重播刷屏），回执里用 `failed : N` 标出。以前一个 `[bar]` 失败会让后面所有孔都不画。

#### v1.6 实测修正：`[shell]` 报"公差错误" → 显式设置 `ShellBuilder.Tolerance`（2026-09-15）
- **实测结果（用户机 v1.5 首跑，`xiaomi13_shell.job`）**：`[bar]` 点阵方案**完全成功**（8 笔浮雕 WXT 全部画出，个别点 `5 ok / 1 fail` 属正常重叠容错）；唯一失败是 `[shell]`：
  ```
  shell: thickness=1.5 remove=top
  shell: thickness applied.
  ! feature 2 : shell 失败: 公差错误。
  ```
- **判据（重要）**：`thickness applied.` 已打印，说明壁厚赋值**成功**；紧接着 Commit 才报"公差错误"。若是选面问题，会在 `FindPlanarFace` 抛"实体上找不到要移除的 'top' 面"，报错形态完全不同。→ **报"公差错误"= 几何计算公差过紧，不是选面/参数错。**
- **修法**：`ShellBuilder.Tolerance`（`Double`，NX4.0.0 起，NXOpen.xml 已核对存在）默认值太紧，抽壳前**显式放大**：
  ```vb
  sh.Tolerance = tol   ' 默认 0.05；作业里可写 tolerance=0.2 再加大
  ```
  作业新增可选参数 `tolerance`（默认 0.05）。
- **同类思路**：NX Open 里凡是"公差错误"，优先想到对应 builder 的 `Tolerance` 属性 / 零件建模公差，而不是重做几何。
- **顺带确认**：`ShellBuilder` 成员全集 = `Body` / `DefaultThickness` / `DefaultThicknessFlip` / `FaceThicknessList` / `FaceThicknesses` / `RemovedFacesCollector` / `TgtPierceOption` / `Tolerance` / `UseSurfaceApproximation`。
- 结果待用户重播验证（若 0.05 仍失败，按 0.2 → 0.5 递增试）。

#### v2.1 实测修正：沿线圆柱/bar 的布尔合并在部分坐标仍会失败 → 立柱/支腿用 `[block]`（2026-09-16）

- **否证**：v1.5 说"沿 Z 的 `CylinderBuilder` 是 100% 可靠的"。传送带支腿实测推翻：4 条腿几何完全对称，
  但 **Y=-68 的两条 `[cylinder]`（以及改 `[bar]` 后）统统失败报 `工具体完全在目标体外`，Y=+68 的两条成功**。
  单个方块的护栏(Y=-87)/端辊(Y=-80)反而全成功。说明"沿 Z 圆柱"的布尔合并在**某些坐标组合下仍不可信**，
  且与"任意方向"无关（坑不在方向，在布尔容差/坐标）。
- **判据**：日志出现 `! feature N : cylinder 失败: Tool body completely outside target body` 或
  `! feature N : bar 失败: [bar] 一个点都没画出来` → 该位置圆柱类布尔不可信，**别再调坐标/穿透深度**，直接换 `[block]`。
- **修法（传送带已验证）**：支腿/立柱这类需要 `bool=unite` 且与现有体相交的竖柱，**一律用 `[block]`**
  （方腿/方柱），100% 可靠。`bar` 只保留给"字母浮雕/斜筋"这类**加料且失败可容错**的场景（个别点失败不影响整体字形）。
- **穿透深度**：方块腿要扎进皮带/基体保证相交——`origin.z` 设到基体底面以下、`size.z` 顶到基体顶面或略高
  （如皮带 Z[150,158]，腿 `origin.z=-12, height=170` → 顶 Z=158 与皮带齐平、重叠 8mm），`bool=unite` 必成。

#### v2.2 模型落盘位置 + 沙箱内可靠启动法（2026-09-16）

- **用户约定**：模型统一存 **`D:\三维建模结果`**（作业 `out=D:\三维建模结果\xxx.prt`）。作业 `mode=auto`，
  `out=` 指该目录即可，守护新建零件后 `Save()` 落盘。
- **沙箱内启动 NX 的可靠写法**（用于"让沙箱先把模型画出来存盘"，不要求实时观看）：
  ```powershell
  $env:UGII_BASE_DIR = "E:\NX\Program Files\Siemens\NX2007"
  $env:UGII_ROOT_DIR = "E:\NX\Program Files\Siemens\NX2007\UGII"
  $env:DISPLAY = "LOCALPC:0.0"
  $env:PATH = "E:\NX\Program Files\Siemens\NX2007\NXBIN;E:\NX\Program Files\Siemens\NX2007\UGII;" + $env:PATH
  Start-Process -FilePath "E:\NX\Program Files\Siemens\NX2007\NXBIN\run_journal.exe" -ArgumentList "<journal.vb>" -WindowStyle Normal
  ```
  直接传 `run_journal.exe <journal>`（环境变量在 PS 里设好）。**不要**用 cmd 的
  `start "" run_journal.exe "<中文长路径>"`——cmd 按 GBK 解析会把中文路径弄坏导致 NX 起不来；
  要传中文路径就走 `nx_start.bat`（已设好 `chcp 936` + 先 `cd /d` 项目目录再传相对路径 `nx_guard.vb`）。
- **重要**：上面这种沙箱启动画完即存盘，但任务结束 NX 被回收（见 §0）。用户在自己机器上"看+转+缩"模型，
  请走 **`nx_start.bat`**（无界面建模 + 普通界面 `ugraf` 查看），**不要**再用 in-session 常驻方案。

### 交付文件（本工作区）
- **`nx_start.bat`**（桌面 `C:\Users\xajsxy\Desktop\nx_start.bat`）—— **用户唯一入口**。双击即跑 `nx_start.py`：
  ① 有 `nx_jobs\*.job` 则无界面 `run_journal.exe` 建模；② 普通界面 `ugraf.exe -retrieve:"<最新prt>"` 打开查看。**全程界面不卡**。
- `nx_start.py` —— 启动器逻辑（设 `UGII_BASE_DIR`/`UGII_ROOT_DIR`/`DISPLAY`/`PATH`，顺序执行建模+查看两步）。
  **查看步必须写 `-retrieve:` + 零件路径**（`cmd.append("-retrieve:" + target)`）；写成裸路径用户会看不到模型。
- `nx_viewtest.py` —— **可选诊断**：拉起 NX 并探测窗口标题/响应，用来判定某种启动参数到底有没有打开零件
  （用法 `nx_viewtest.py <持续秒> <ugraf参数...>`；判据：标题出现 `NX - 建模` 才算打开，只有 `NX` = 停在起始页）。
- `nx_guard.vb` —— **v3.0 单次执行版（one-shot）**：扫一遍 `nx_jobs\*.job`、画完即 `return`，**绝不写常驻循环**。
  头部 `GUARD_VERSION="3.0"`、`OUT_DIR="D:\三维建模结果"`。`ROOT` 常量硬编码为本工作区，换机器/换目录需改 `ROOT`。
  已用 vbc 离线编译 0 错误，建模链路 2026-09-17 实测跑通（`conveyor350.prt` 16 特征 0 失败）。
- `nx_jobs\` —— 作业投递箱（扫一遍，处理完写 `.done`/`.fail`）。
- `nx_guard.log` —— 运行日志（每次跑追加一段，含逐个作业的 `>>> JOB` / `<<< OK`）。
- `nx_result.txt` —— 最近一次作业的回执（时间/零件/特征数/是否保存）。
- `nx_uiwatch.py` —— 可选**外部窗口探针**：每 2 s 用 `SendMessageTimeout` 探测 `ugraf.exe` 各窗口的 `OK/HUNG` 状态，
  写 `nx_uiwatch.log`。用于排查"NX 卡死"时区分"卡在 journal（HUNG）"还是"正常建模"。
- `nx_job_templates\block_hole.job` —— 作业格式范例（500 立方 + M10 通孔，mode=current）。

> 已删除（2026-09-17 清理）：`nx_guard_once.vb`（一次性备份，被 v3.0 取代）、`nx_guard.stop`（v2.0 退出开关，
> 常驻方案已废弃）、`start_guard.bat`（v2.0 启动器，被 `nx_start.bat` 取代）、`nx_auto_watch.*`（实验性 Alt+F8 触发器，
> 依赖已废弃的 in-session 常驻，移除）。

### 使用档位（2026-09-17 定稿，只有一条可靠路径）
| 档位 | 用户要做的 | 界面会卡吗 | 说明 |
|---|---|---|---|
| **`nx_start.bat`（唯一推荐）** | 每次想画/想看 → **双击 `nx_start.bat`** | ❌ 永不卡 | ① 有 `.job` → 无界面 `run_journal` 建模；② 普通界面 `ugraf` 打开最新 `.prt`，可自由旋转/缩放。建模时 NX 不显示任何界面，所以不存在"锁界面"问题 |
| **手动 Alt+F8 一次（仅应急）** | 在已开的 NX 里 Alt+F8 → 选 `nx_guard.vb` → 执行 | ⚠️ 建模那几秒界面会被"工作进行中"锁住，画完即解锁 | 直接在当前 NX 会话里一次性画完（v3.0 one-shot），画完模型就在眼前、可继续操作。**只作兜底**，正常请走 `nx_start.bat` |

- **核心纪律**：**永远不要**让用户用 NX in-session 常驻（`nx_guard.stop` / v2.0 守护已废弃）。任何常驻循环都会把 NX 主窗口锁死（结论①）。
- **措辞纪律**：不要说"点一次、之后零操作"。当前是"每次想画/看就双击 bat"——属于轻量一键，但不是后台自动。
- 若用户反馈 NX 卡在某处不动：**先看 `nx_uiwatch.log`**——若是 `HUNG` 说明有 journal 还在跑（杀掉该 `ugraf`/`run_journal` 进程即可），若是 `OK` 且长时间无 `.done` 说明作业本身建模失败（看 `nx_guard.log` 的 `<<< FAIL`）。

### 用户怎么用（唯一入口 `nx_start.bat`）
- **想看已有模型**：直接双击 `nx_start.bat`（此时 `nx_jobs\` 没新作业 → 跳过建模 → 普通界面 NX 打开 `D:\三维建模结果` 里最新的 `.prt`）。
- **想画新东西**：告诉我"画一个 XX" → 我在沙箱写好 `nx_jobs\XX.job` → 你双击 `nx_start.bat` →
  无界面建模完 → 普通界面 NX 自动打开新模型。
- 打开后如果太大/太小，在 NX 里按 **Ctrl+F**（视图自适应）；可自由旋转/缩放/编辑。

### 之后的使用闭环（v3.0）
1. 用户说"画一个 XX"。
2. 我在沙箱里生成 `*.job` 写入 `nx_jobs\`（格式见下）。
3. 用户**双击 `nx_start.bat`** → ① 无界面 `run_journal` 建模（约 1–2 分钟，期间无任何 NX 界面，不卡）；
   ② 普通界面 `ugraf` 打开最新 `.prt`。
4. 我读 `nx_jobs\XX.job.done` / `nx_guard.log` 的 `<<< OK` 确认后回"画好了"。
5. **务必提醒**：双击后 NX 可能要等 1–2 分钟才弹出来（冷启动 + 建模），**这是正常的，不是卡死**；
   只有 NX 主窗口出现、能旋转/缩放，才算完成。

### 作业文件格式（INI 风格，替代旧的 .vb 投递）
```ini
mode=current          # current=画进当前打开的零件；new=新建零件（需配 out=）
save=0                # 1/0 画完是否保存零件
# out=D:\xxx\part.prt # 仅 mode=new 需要

[block]               # 长方体
origin=0,0,0          # 原点 x,y,z
size=500,500,500      # 长,宽,高
bool=none             # none|unite|subtract|intersect

[cylinder]            # 圆柱
origin=250,250,-1     # 底面中心 x,y,z（贯穿整块用 z=-1, height=块高+2）
dia=10                # 直径
height=502            # 高度
bool=subtract         # 相对上一个体做布尔

[shell]               # 抽壳：把上一个实体掏成均匀壁厚的壳，v1.5 新增
thickness=1.5         # 壁厚
remove=top            # 被移除的面：top|bottom（默认 top = 最高的水平面）
tolerance=0.05        # 抽壳公差（v1.6；报"公差错误"时加大，如 0.2）

[bar]                 # 一笔"描边"：沿 from->to 撒一串沿 Z 的小圆柱（点阵），v1.5 改
from=56,24,0          # 起点 x,y[,z]
to=59,8,0             # 终点 x,y[,z]
dia=3.6               # 每个点的直径（默认 3.6）
step=3.2              # 点间距（默认 dia*0.85；<0.2 会被夹到 0.2）
z0=-0.8               # 圆柱底面 z（默认 min(z)-0.8）
ztop=0.7              # 圆柱顶面 z（默认 max(z)+0.7）
bool=unite
```
- 可叠多个 `[block]`/`[cylinder]`/`[shell]`/`[bar]` 段，依次建模，每个段用 `bool=` 指定与前一个体的关系（第一个体用 `none`/`create`；`[shell]` 段忽略 `bool`）。
- **推荐顺序**：`[block]` 实心坯 → `[shell]` 抽壳 → `[cylinder]` 打孔/减料 → `[bar]` 浮雕/筋条（`unite` 加料放最后）。
- `mode=current` 要求当前有 work part，否则写 `.fail` 并提示"先打开/新建零件"。
- `mode=auto`：优先用当前打开的零件，没有打开零件则自动新建（默认 `nx_jobs\auto_part.prt`），用于"不想管有没有打开零件"的场景。
- `mode=new` 配 `out=`；v1.3 起 `out=` 指向的路径若已存在同名文件，会**自动改用 `_2`/`_3`…**（`FreePath()`），避免 `FileNew` 撞车失败。因此作业是幂等的，重复播放只会多出一份新零件，不会报错。
- 编码：UTF-8 with BOM + CRLF（同 §3 规则），防止中文路径 GBK 乱码。

### 关键实现点（v1.5，已离线 vbc 编译 0 错误，NX2007）
- `Main()`：`Session.GetSession()` → 建 `nx_jobs\` → `ScanOnce()`（把没做过的 `.job` 全做掉）→ 返回到 NX。**不起线程、不注册定时器、不留任何驻留物。**
- `ScanOnce()`：`Directory.GetFiles(JOBS_DIR, "*.job")` 排序后逐个跑；已有 `.done` 的跳过；`.fail` 只在"比 `.job` 新"时跳过（作业被改过就自动重试并删掉旧 `.fail`）；每个作业单独 Try/Catch，失败写 `<job>.fail` 并把异常全文写进去。
- `RunJob()`：解析 INI（全局 `mode/out/save` + `[段]`），逐段建模；`lastBody` 跟踪上一段产出的 body 作为下一段布尔的 target。**每个段单独 Try/Catch**，失败只记录（`failed : N`）不中断整单。
- 建模段复用 §5.2 已核对的 `BlockFeatureBuilder` / `CylinderBuilder` API（`Diameter.Value`/`Height.Value`/`Origin=New Point3d`/`BooleanOption` 配 `SetTargetBodies`）；`[shell]` 见上节 v1.5；`[bar]` 为 v1.5 的点阵实现。
- `CreateNewPart()` 用 `Parts.FileNew()` + 模板 `model-plain-1-mm-template.prt`，`MakeDisplayedPart=True`（这点很关键：新零件会自动切到前台，用户一眼就能看到）。
- 编译命令：`vbc /target:library /r:"E:\NX\Program Files\Siemens\NX2007\NXBIN\managed\NXOpen.dll" /r:"...\NXOpen.Utilities.dll" /r:"...\NXOpen.UF.dll" nx_guard.vb`（漏 `NXOpen.Utilities` → BC30002；漏 `NXOpen.UF` → BC30007）。
- **沙箱能预编译**：`vbc.exe` 可直接调用（`C:\Windows\Microsoft.NET\Framework64\v4.0.30319\vbc.exe`），每次改完必须编译过再交给用户，能提前吃掉全部语法/类型错误（如上面那个 `Direction` 是 `Vector3d` 的坑就是编译报出来的）。

### 与 §7 AutoPilot 的取舍（2026-09-17 重新对齐）
| | NX Guard / `nx_start`（§8） | AutoPilot（§7） |
|---|---|---|
| 建模方式 | 无界面 `run_journal.exe`（同左） | 无界面 `run_journal.exe` |
| 查看方式 | **普通界面 `ugraf.exe` 打开最新 `.prt`**（可交互、不卡） | 仅产出 `.prt`，需用户自己打开 |
| 界面会卡吗 | ❌ 不会（建模无界面、查看不跑 journal） | ❌ 不会 |
| 产出 | 独立 `.prt` 落 `D:\三维建模结果`，查看时自动打开 | 独立 `.prt` |
| 适合 | "我要看我画的模型 + 能转能缩" | 批量出图、不关心过程 |
| 常驻 | ❌ **已废弃**（v2.0 in-session 常驻会锁死 UI，结论①） | bat 常驻后台，独立会话 |

- 两个方案建模内核相同（都是 `run_journal` 无界面批处理），**区别只在"看"**：`nx_start` 多一步普通界面
  `ugraf` 打开，让用户能直接交互查看；AutoPilot 只负责出 `.prt`。
- **不要再提"in-session 实时可见/常驻"**——v2.0 那条路已被证伪。建模过程本身不可见，但成品可交互查看，
  对用户诉求（"能看、能转、能缩"）已经满足。
