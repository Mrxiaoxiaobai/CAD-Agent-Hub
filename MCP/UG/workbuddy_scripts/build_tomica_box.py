# -*- coding: utf-8 -*-
"""多美卡小车收纳盒：六面榫卯，免布尔直接用体素拼。横排/纵叠/前后都能互锁。
最大车尺寸 80x40x40 -> 内壁 85x45x45；壁厚4；榫/卯 14x14 截面、深8。
模型演示：A在原点，B接A右侧(横)，C叠A上方(纵)。"""
import NXOpen, NXOpen.UF, math

theSession = NXOpen.Session.GetSession()
work = theSession.Parts.Work
if work is None or work.Name != 'tomica_box':
    work = theSession.Parts.NewDisplay('tomica_box', NXOpen.Part.Units.Millimeters)
ufs = NXOpen.UF.UFSession.GetUFSession()

COL_BODY = 159   # 中灰 盒体/卯
COL_TEN  = 91    # 浅蓝 榫(凸) 高亮

def block(ox, oy, oz, lx, ly, lz, name, color=COL_BODY):
    b = work.Features.CreateBlockFeatureBuilder(NXOpen.Features.Feature.Null)
    b.Type = NXOpen.Features.BlockFeatureBuilder.Types.OriginAndEdgeLengths
    b.SetOriginAndLengths(NXOpen.Point3d(float(ox), float(oy), float(oz)),
                          str(float(lx)), str(float(ly)), str(float(lz)))
    b.SetBooleanOperationAndTarget(NXOpen.Features.Feature.BooleanType.Create, NXOpen.Body.Null)
    feat = b.CommitFeature(); b.Destroy()
    bd = feat.GetBodies()[0]; bd.SetName(name)
    ufs.Obj.SetColor(int(bd.Tag), int(color))
    return bd

# ---- 单个盒（含六面榫卯），整体平移 (dx,dy,dz) ----
def build_box(dx, dy, dz, tag):
    # 盒体：底 + 四壁（开口朝上）
    block(dx+0,   dy+0,   dz+0,   93, 53, 4,  f'{tag}_BOTTOM')         # 底板 z0..4
    block(dx+0,   dy+0,   dz+4,   93, 4,  45, f'{tag}_WALL_BK')        # 后墙 y0..4
    block(dx+0,   dy+49,  dz+4,   93, 4,  45, f'{tag}_WALL_FR')        # 前墙 y49..53
    block(dx+0,   dy+4,   dz+4,   4,  45, 45, f'{tag}_WALL_LF')        # 左墙 x0..4
    block(dx+89,  dy+4,   dz+4,   4,  45, 45, f'{tag}_WALL_RT')        # 右墙 x89..93
    # 内壁 85(x4..89) x 45(y4..49) x 45(z4..49)

    # 榫(凸)：顶 / 右 / 前
    block(dx+39.5, dy+19.5, dz+49,  14, 14, 8, f'{tag}_TEN_TOP',  COL_TEN)  # 顶面 +Z
    block(dx+93,   dy+19.5, dz+19.5, 8,  14, 14, f'{tag}_TEN_RT',  COL_TEN)  # 右面 +X
    block(dx+39.5, dy+53,   dz+19.5, 14, 8,  14, f'{tag}_TEN_FR',  COL_TEN)  # 前面 +Y

    # 卯(凹)= 方井：底 / 左 / 后，各4薄壁围出 15x15 内腔、深8
    def well(axis, c1, c2, name):
        half, wt, dep = 7.5, 2.0, 8.0
        a0, a1 = c1-half-wt, c1+half+wt
        b0, b1 = c2-half-wt, c2+half+wt
        ia0, ia1 = c1-half, c1+half
        ib0, ib1 = c2-half, c2+half
        d0 = -dep
        if axis == 'z':  # 开口在XY，深沿-Z；中心(c1=Y,c2=X)
            block(dx+ia1, dy+b0, dz+d0, a1-ia1, b1-b0, dep, name+'0')  # +X壁
            block(dx+a0,  dy+b0, dz+d0, ia0-a0, b1-b0, dep, name+'1')  # -X壁
            block(dx+a0,  dy+ib1, dz+d0, a1-a0, b1-ib1, dep, name+'2') # +Y壁
            block(dx+a0,  dy+b0, dz+d0, a1-a0, ib0-b0, dep, name+'3')  # -Y壁
        elif axis == 'x':  # 开口在YZ，深沿-X；中心(c1=Y,c2=Z)
            block(dx+d0, dy+ia1, dz+b0, dep, a1-ia1, b1-b0, name+'0')  # +Y壁
            block(dx+d0, dy+a0,  dz+b0, dep, ia0-a0, b1-b0, name+'1')  # -Y壁
            block(dx+d0, dy+a0,  dz+ib1, dep, a1-a0, b1-ib1, name+'2') # +Z壁
            block(dx+d0, dy+a0,  dz+b0, dep, a1-a0, ib0-b0, name+'3')  # -Z壁
        elif axis == 'y':  # 开口在XZ，深沿-Y；中心(c1=X,c2=Z)
            block(dx+ia1, dy+d0, dz+b0, a1-ia1, dep, b1-b0, name+'0')  # +X壁
            block(dx+a0,  dy+d0, dz+b0, ia0-a0, dep, b1-b0, name+'1')  # -X壁
            block(dx+a0,  dy+d0, dz+ib1, a1-a0, dep, b1-ib1, name+'2') # +Z壁
            block(dx+a0,  dy+d0, dz+b0, a1-a0, dep, ib0-b0, name+'3')  # -Z壁
    well('z', 26.5, 46.5, f'{tag}_MORT_BOT')   # 底面 -Z（接上方盒的顶榫）
    well('x', 26.5, 26.5, f'{tag}_MORT_LF')    # 左面 -X（接右邻盒的右榫）
    well('y', 46.5, 26.5, f'{tag}_MORT_BK')    # 后面 -Y（接前邻盒的前榫）

# A 原点；B 接 A 右侧(横, dx=101)；C 叠 A 上方(纵, dz=57)
build_box(0,   0,  0,  'A')
build_box(101, 0,  0,  'B')   # B左面卯(世界93..101) 接 A右面榫(世界93..101)
build_box(0,   0,  57, 'C')   # C底面卯(世界49..57) 接 A顶面榫(世界49..57)

# 视图：标准轴测 + 适配
vw = work.Views.WorkView
vw.Orient(NXOpen.View.Canned.Trimetric, NXOpen.View.ScaleAdjustment.Fit)
vw.Fit()

# 存盘
work.SaveAs(r'D:\三维建模结果\tomica_box.prt')

result = {'part': work.Name, 'n_bodies': len(list(work.Bodies)),
          'saved': r'D:\三维建模结果\tomica_box.prt'}
