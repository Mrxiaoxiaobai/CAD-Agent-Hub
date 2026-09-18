# SX-815Q cyclic conveyor - build all parts in-place (no booleans)
import NXOpen, NXOpen.UF, math, traceback
theSession = NXOpen.Session.GetSession()
work = theSession.Parts.Work
ufs = NXOpen.UF.UFSession.GetUFSession()

GRAY, SILVER, BLACK, BLUE = 159, 87, 216, 91
parts = []          # (body, color, translucency)
fails = []

def bbox(b):
    return [float(v) for v in ufs.ModlGeneral.AskBoundingBox(int(b.Tag))]

def _extrude(curves, direction, dist):
    section = work.Sections.CreateSection(0.00095, 0.001, 0.5)
    rule = work.ScRuleFactory.CreateRuleCurveDumb(curves)
    section.AddToSection([rule], curves[0], NXOpen.NXObject.Null, NXOpen.NXObject.Null,
                         NXOpen.Point3d(0.0, 0.0, 0.0), NXOpen.Section.Mode.Create, False)
    builder = work.Features.CreateExtrudeBuilder(NXOpen.Features.Feature.Null)
    builder.Section = section
    builder.Direction = work.Directions.CreateDirection(
        NXOpen.Point3d(0.0, 0.0, 0.0), direction,
        NXOpen.SmartObject.UpdateOption.WithinModeling)
    builder.Limits.StartExtend.Value.RightHandSide = '0'
    builder.Limits.EndExtend.Value.RightHandSide = str(float(dist))
    builder.BooleanOperation.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Create
    feat = builder.CommitFeature(); builder.Destroy()
    body = feat.GetBodies()[0]
    for c in curves:
        c.Blank()
    return body

def add(body, color, name=None, trans=None):
    if name:
        try: body.SetName(name)
        except Exception: pass
    parts.append((body, color, trans))
    return body

def box(ox, oy, oz, lx, ly, lz, color, name=None):
    b = work.Features.CreateBlockFeatureBuilder(NXOpen.Features.Feature.Null)
    b.Type = NXOpen.Features.BlockFeatureBuilder.Types.OriginAndEdgeLengths
    b.SetOriginAndLengths(NXOpen.Point3d(float(ox), float(oy), float(oz)),
                          str(float(lx)), str(float(ly)), str(float(lz)))
    b.SetBooleanOperationAndTarget(NXOpen.Features.Feature.BooleanType.Create, NXOpen.Body.Null)
    f = b.CommitFeature(); b.Destroy()
    return add(f.GetBodies()[0], color, name)

def cyl_y(cx, y0, y1, cz, r, color, name=None):
    arc = work.Curves.CreateArc(NXOpen.Point3d(float(cx), float(y0), float(cz)),
        NXOpen.Vector3d(1.0, 0.0, 0.0), NXOpen.Vector3d(0.0, 0.0, 1.0),
        float(r), 0.0, 2.0 * math.pi)
    return add(_extrude([arc], NXOpen.Vector3d(0.0, 1.0, 0.0), float(y1 - y0)), color, name)

def cyl_x(cy, x0, x1, cz, r, color, name=None):
    arc = work.Curves.CreateArc(NXOpen.Point3d(float(x0), float(cy), float(cz)),
        NXOpen.Vector3d(0.0, 1.0, 0.0), NXOpen.Vector3d(0.0, 0.0, 1.0),
        float(r), 0.0, 2.0 * math.pi)
    return add(_extrude([arc], NXOpen.Vector3d(1.0, 0.0, 0.0), float(x1 - x0)), color, name)

def cyl_z(cx, cy, z0, z1, r, color, name=None):
    arc = work.Curves.CreateArc(NXOpen.Point3d(float(cx), float(cy), float(z0)),
        NXOpen.Vector3d(1.0, 0.0, 0.0), NXOpen.Vector3d(0.0, 1.0, 0.0),
        float(r), 0.0, 2.0 * math.pi)
    return add(_extrude([arc], NXOpen.Vector3d(0.0, 0.0, 1.0), float(z1 - z0)), color, name)

def poly_yz(pts, x0, thick, color, name=None):
    curves = []
    n = len(pts)
    for i in range(n):
        y1, z1 = pts[i]; y2, z2 = pts[(i + 1) % n]
        curves.append(work.Curves.CreateLine(
            NXOpen.Point3d(float(x0), float(y1), float(z1)),
            NXOpen.Point3d(float(x0), float(y2), float(z2))))
    return add(_extrude(curves, NXOpen.Vector3d(1.0, 0.0, 0.0), float(thick)), color, name)

def safe(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as e:
        fails.append((kw.get('name') or (fn.__name__ + str(a[:2])), str(e)[:150]))
        return None

# ================= 1. frame =================
safe(box, -280, -30, 160, 560, 60, 70, GRAY, name='BEAM')                    # cross beam
SIDE_PTS = [(-85, 240), (85, 240), (85, 150), (55, 40), (-55, 40), (-85, 150)]
safe(poly_yz, SIDE_PTS, -292, 12, GRAY, name='SIDE_PLATE_L')                 # side plate 1
safe(poly_yz, SIDE_PTS, 280, 12, GRAY, name='SIDE_PLATE_R')                  # side plate 2
safe(box, -320, -70, 30, 80, 140, 10, GRAY, name='BASE_PAD_L')               # base plate L
safe(box, 240, -70, 30, 80, 140, 10, GRAY, name='BASE_PAD_R')                # base plate R
# bearing blocks under roller shafts
for sx in (-255, 255):
    safe(box, sx - 6, 42, 233, 12, 12, 15, GRAY, name='BRG_BLK')
    safe(box, sx - 6, -54, 233, 12, 12, 15, GRAY, name='BRG_BLK')
for sx in (-180, 180):
    safe(box, sx - 6, 42, 233, 12, 12, 15, GRAY, name='BRG_BLK')
# guide plate 1 (left end, on side plate) / guide plate 2 (right, on belt)
safe(box, -292, -45, 240, 12, 90, 35, GRAY, name='GUIDE1')
safe(box, 240, -30, 270, 12, 60, 35, GRAY, name='GUIDE2')

# ================= 2. rollers & shafts (axes along Y) =================
for sx in (-255, 255):
    safe(cyl_y, sx, -54, 54, 252, 4, SILVER, name='SHAFT_DRIVEN')
    safe(cyl_y, sx, -12, 12, 252, 15, BLACK, name='ROLLER_B1')
    safe(cyl_y, sx, 16, 40, 252, 15, BLACK, name='ROLLER_B2')
for sx in (-180, 180):
    safe(cyl_y, sx, 6, 54, 252, 4, SILVER, name='SHAFT_MID')
    safe(cyl_y, sx, 16, 40, 252, 15, BLACK, name='ROLLER_MID')

# ================= 3. drive group (below beam, like cover) =================
safe(cyl_x, 0, 120, 128, 130, 55, SILVER, name='DISC_PLATE')                 # round fixing disc
safe(cyl_x, 0, 128, 178, 130, 6, SILVER, name='SHAFT_DRIVE')                 # drive shaft
safe(cyl_x, 0, 133, 153, 130, 16, BLACK, name='ROLLER_DRIVE')                # drive roller
safe(cyl_x, 0, 156, 168, 130, 20, SILVER, name='PULLEY_SYNC')                # timing pulley
safe(cyl_x, -20, 96, 106, 100, 10, SILVER, name='PULLEY_TENSION')            # tension pulley
safe(box, 96, -26, 72, 12, 12, 18, GRAY, name='TENSION_BRKT')                # bracket
safe(box, 106, -26, 72, 16, 12, 12, GRAY, name='TENSION_ARM')                # arm to disc

# ================= 4. belts (2 flat PVC loops) =================
safe(box, -255, -12, 267, 510, 24, 2.5, BLACK, name='BELT1_TOP')
safe(box, -255, -12, 234.5, 510, 24, 2.5, BLACK, name='BELT1_BOT')
safe(cyl_y, -255, -12, 12, 252, 17.5, BLACK, name='BELT1_WL')
safe(cyl_y, 255, -12, 12, 252, 17.5, BLACK, name='BELT1_WR')
safe(box, -180, 16, 267, 360, 24, 2.5, BLACK, name='BELT2_TOP')
safe(box, -180, 16, 234.5, 360, 24, 2.5, BLACK, name='BELT2_BOT')
safe(cyl_y, -180, 16, 40, 252, 17.5, BLACK, name='BELT2_WL')
safe(cyl_y, 180, 16, 40, 252, 17.5, BLACK, name='BELT2_WR')

# ================= 5. baffles =================
safe(box, -270, -17, 270, 540, 3, 30, GRAY, name='BAFFLE_L')
safe(box, -180, 15, 270, 360, 3, 15, GRAY, name='BAFFLE_M')
safe(box, -270, 44, 270, 540, 3, 30, GRAY, name='BAFFLE_R')

# ================= 6. hopper =================
safe(box, 275, -42, 240, 60, 84, 30, GRAY, name='HOPPER_BASE')
safe(cyl_z, 300, -20, 270, 450, 19, BLUE, name='HOPPER_TUBE1', trans=70)
safe(cyl_z, 300, 20, 270, 450, 19, BLUE, name='HOPPER_TUBE2', trans=70)
safe(box, 272, -46, 450, 56, 92, 12, GRAY, name='HOPPER_CAP')
safe(cyl_z, 300, -20, 462, 472, 10, BLACK, name='CAP_STUB1')
safe(cyl_z, 300, 20, 462, 472, 10, BLACK, name='CAP_STUB2')

# ================= 7. pushers (x2) =================
for px in (-120, 40):
    safe(cyl_y, px, -75, -35, 285, 8, BLACK, name='CYL_PUSHER')
    safe(cyl_y, px, -35, -8, 285, 3, SILVER, name='ROD_PUSHER')
    safe(box, px - 12, -8, 276, 24, 12, 18, GRAY, name='CLAMP_PUSHER')
    safe(box, px - 8, -72, 270, 16, 14, 8, GRAY, name='RISER_PUSHER')

# ================= 8. sensors (x2) =================
safe(box, 286, -54, 250, 14, 12, 22, BLACK, name='SENSOR1')
safe(cyl_y, 293, -66, -54, 261, 1.5, SILVER, name='SENSOR1_TIP')
safe(box, 256, 47, 274, 14, 12, 20, BLACK, name='SENSOR2')
safe(cyl_y, 263, 33, 47, 284, 1.5, SILVER, name='SENSOR2_TIP')

# ================= 9. leveling screws (x4) =================
for lx, ly in ((-310, -50), (-310, 50), (310, -50), (310, 50)):
    safe(cyl_z, lx, ly, 5, 30, 2.5, SILVER, name='ADJ_SCREW')

# ================= color / translucency =================
for body, color, trans in parts:
    try:
        ufs.Obj.SetColor(int(body.Tag), color)
        if trans:
            ufs.Obj.SetTranslucency(int(body.Tag), trans)
    except Exception as e:
        fails.append(('color', str(e)[:100]))

# ================= view + save =================
vw = work.Views.WorkView
vw.Orient(NXOpen.View.Canned.Trimetric, NXOpen.View.ScaleAdjustment.Fit)
vw.Fit()

n_bodies = len(list(work.Bodies))
info = {'bodies': n_bodies, 'parts': len(parts), 'fails': fails}
try:
    work.SaveAs(r'D:\三维建模结果\conveyor_815q.prt')
    info['saved'] = r'D:\三维建模结果\conveyor_815q.prt'
except Exception as e:
    info['save_err'] = str(e)[:300]
result = info
