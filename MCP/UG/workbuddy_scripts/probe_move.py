# -*- coding: utf-8 -*-
# Live probe (inside NX): verify MoveObjectBuilder / MoveBodyBuilder actually
# translate a body, and sanity-check instantiation of newly-found builders.
# Runs in a NON-displayed in-memory temp part, closed without saving.
import NXOpen, NXOpen.UF, traceback

theSession = NXOpen.Session.GetSession()
ufs = NXOpen.UF.UFSession.GetUFSession()
R = {}

# create a non-displayed temp part so we never disturb the user's view
fn = theSession.Parts.FileNew()
fn.TemplateFileName = "model-plain-1-mm-template.prt"
fn.UseBlankTemplate = False
fn.ApplicationName = "ModelTemplate"
fn.Units = NXOpen.Part.Units.Millimeters
fn.NewFileName = "nx_probe_move.prt"
fn.MasterFileName = "nx_probe_move.prt"
fn.MakeDisplayedPart = False
fn.Commit(); fn.Destroy()
tp = theSession.Parts.Work
R['temp_part'] = tp.Name if tp else 'NONE'

def bbox(tag):
    return [round(float(v),2) for v in ufs.ModlGeneral.AskBoundingBox(int(tag))]

# --- build a tiny sphere at origin ---
sb = tp.Features.CreateSphereBuilder(NXOpen.Features.Sphere.Null)
sb.Type = NXOpen.Features.SphereBuilder.Types.CenterPointAndDiameter
sb.CenterPoint = tp.Points.CreatePoint(NXOpen.Point3d(0.0,0.0,0.0))
sb.Diameter.RightHandSide = "4"
sf = sb.CommitFeature(); sb.Destroy()
sph = sf.GetBodies()[0]; stag = int(sph.Tag)
b0 = bbox(stag)

MV = {}
# ===== TEST 1: MoveObjectBuilder translate (+100 in X) =====
try:
    mb = tp.Features.CreateMoveObjectBuilder(NXOpen.Features.MoveObject.Null)
    MV['moveobject_factory_ok'] = True
    try:
        mb.ObjectToMoveObject.Add(sph); MV['obj_add_ok'] = True
    except Exception as e:
        try:
            mb.ObjectToMoveObject.AddMultiple([sph]); MV['obj_addmultiple_ok'] = True
        except Exception as e2:
            MV['obj_add_err'] = repr(e2)[:160]
    mb.MoveObjectResult = NXOpen.Features.MoveObjectBuilder.MoveObjectResultOptions.MoveOriginal
    mb.Associative = False
    tm = mb.TransformMotion
    try:
        tm.DeltaXc.Value = 100.0; MV['delta_value_set'] = True
    except Exception as e:
        try:
            tm.DeltaXc.RightHandSide = "100"; MV['delta_rhs_set'] = True
        except Exception as e2:
            MV['delta_set_err'] = repr(e2)[:160]
    tm.DeltaYc.RightHandSide = "0"
    tm.DeltaZc.RightHandSide = "0"
    f = mb.CommitFeature(); mb.Destroy()
    b1 = bbox(stag)
    MV['bbox_before'] = b0
    MV['bbox_after'] = b1
    MV['translated_100x'] = (abs(b1[0]-b0[0]-100) < 0.5)
except Exception as e:
    MV['moveobject_err'] = repr(e)[:300]

# cleanup sphere
try: ufs.Obj.DeleteObject(stag)
except Exception: pass

# ===== TEST 2: MoveBodyBuilder =====
MBB = {}
try:
    # build a block
    bb = tp.Features.CreateBlockFeatureBuilder(NXOpen.Features.Feature.Null)
    bb.Type = NXOpen.Features.BlockFeatureBuilder.Types.OriginAndEdgeLengths
    bb.SetOriginAndLengths(NXOpen.Point3d(0.0,0.0,0.0), "20", "20", "20")
    bb.SetBooleanOperationAndTarget(NXOpen.Features.Feature.BooleanType.Create, NXOpen.Body.Null)
    blk = bb.CommitFeature(); bb.Destroy()
    blk_body = blk.GetBodies()[0]; btag = int(blk_body.Tag)
    bb0 = bbox(btag)
    mbb = tp.Features.CreateMoveBodyBuilder(NXOpen.Features.MoveBody.Null)
    MBB['factory_ok'] = True
    try:
        mbb.BodyToMove = blk_body; MBB['body_to_move_settable'] = True
    except Exception as e:
        MBB['body_to_move_err'] = repr(e)[:160]
    try:
        mo = mbb.Motion
        mo.DeltaYc.RightHandSide = "50"
        mo.DeltaXc.RightHandSide = "0"
        mo.DeltaZc.RightHandSide = "0"
        MBB['motion_set_ok'] = True
    except Exception as e:
        MBB['motion_err'] = repr(e)[:160]
    try:
        f2 = mbb.CommitFeature(); mbb.Destroy()
        bb1 = bbox(btag)
        MBB['bbox_before'] = bb0; MBB['bbox_after'] = bb1
        MBB['moved_50y'] = (abs(bb1[1]-bb0[1]-50) < 0.5)
    except Exception as e:
        MBB['commit_err'] = repr(e)[:200]
    try: ufs.Obj.DeleteObject(btag)
    except Exception: pass
except Exception as e:
    MBB['FATAL'] = repr(e)[:300]
R['moveobject_test'] = MV
R['movebody_test'] = MBB

# ===== TEST 3: instantiation sanity of newly discovered builders =====
INST = {}
candidates = {
    'SweptBuilder':'Swept', 'PatternFeatureBuilder':'PatternFeature',
    'MirrorBodyBuilder':'MirrorBody', 'ThickenBuilder':'Thicken',
    'ShellBuilder':'Shell', 'TrimBodyBuilder':'TrimBody',
    'SplitBodyBuilder':'SplitBody', 'DraftBodyBuilder':'DraftBody',
    'ScaleBuilder':'Scale', 'RevolveBuilder':'Revolve',
    'TubeBuilder':'Tube', 'TextBuilder':'Text',
    'InstanceFeatureBuilder':'InstanceFeature', 'RuledBuilder':'Ruled',
    'ThroughCurvesBuilder':'ThroughCurves', 'SewBuilder':'Sew',
}
for name, arg in candidates.items():
    fnc = getattr(tp.Features, 'Create'+name, None)
    if fnc is None:
        INST[name] = 'NO_FACTORY'
        continue
    try:
        if 'Scale' in name:
            b2 = fnc(NXOpen.Features.Scale.Null)
        elif name in ('Swept','Ruled','ThroughCurves','Sew','TrimBody','SplitBody','Shell','Thicken','DraftBody','PatternFeature','MirrorBody','Tube','Text','InstanceFeature'):
            b2 = fnc(NXOpen.Features.__dict__.get(arg, NXOpen.Features.Feature).Null if hasattr(NXOpen.Features, arg) else NXOpen.Features.Feature.Null)
        else:
            b2 = fnc(NXOpen.Features.Feature.Null)
        INST[name] = 'INSTANTIABLE'
        try: b2.Destroy()
        except Exception: pass
    except Exception as e:
        INST[name] = 'ERR:'+repr(e)[:120]
R['instantiation'] = INST

# close temp part WITHOUT saving
try:
    tp.Close(NXOpen.BasePartCloseWholeTree.FalseValue, NXOpen.BasePartCloseModified.No, None)
    R['temp_part_closed'] = True
except Exception as e:
    R['close_err'] = repr(e)[:160]

result = R
