# -*- coding: utf-8 -*-
# NX API capability probe -- runs INSIDE the NX process via run_python.
# Goal: (A) enumerate all Create*Builder factories, (B) hunt for a WORKING body
# move/rotate, (C) empirically test a few unverified features on a temp part that
# gets closed-without-save at the end (no pollution of the user's file).
import NXOpen, NXOpen.UF, traceback

theSession = NXOpen.Session.GetSession()
work = theSession.Parts.Work
ufs = NXOpen.UF.UFSession.GetUFSession()

R = {}

# ---------- (A) enumerate all Create*Builder factory methods ----------
fc = work.Features
allcreates = [m for m in dir(fc) if m.startswith('Create')]
R['total_create_methods'] = len(allcreates)
KWS = ['Move','Transform','Translate','Rotate','Pattern','Sweep','Loft','Blend',
       'Chamfer','Hole','Shell','Thicken','Offset','Trim','Split','Fillet','Draft',
       'Tube','Revolve','Cone','Sphere','Scale','Boolean','Extrude','Block','Cylinder',
       'Mirror','Wrap','Rib','Thread','Groove','Slot','Keyway','Boss','Pad','Bridge',
       'Sew','Sheet','Flange','Bend','Protrusion','Cut','Datum','TrimBody','Subtract',
       'Unite','Intersect','Feature','FromCurves','Studio','Helix','Law','Spline']
hits = sorted({m for m in allcreates for k in KWS if k.lower() in m.lower()})
R['create_hits'] = hits

# ---------- (B) MOVE / ROTATE hunt ----------
mv = {}
# B1: which Create* on FeatureCollection mention move/transform
mv['fc_move_related'] = [m for m in allcreates if 'move' in m.lower() or 'transform' in m.lower() or 'translate' in m.lower() or 'rotate' in m.lower()]
# B2: NXOpen.Features classes about move/transform
featcls = [c for c in dir(NXOpen.Features) if any(t in c.lower() for t in ['move','transform','translate','rotate'])]
mv['features_classes'] = featcls
# B3: UF Modl transform/move methods
modl_t = [m for m in dir(ufs.Modl) if any(t in m.lower() for t in ['transform','move','rotat'])]
mv['uf_modl_t'] = modl_t
R['move_hunt'] = mv

# ---------- (C) empirical tests on an isolated temp part ----------
C = {}
tp = None
try:
    # open a fresh mm temp part in memory (not saved to disk)
    fn = theSession.Parts.FileNew()
    fn.TemplateFileName = "model-plain-1-mm-template.prt"
    fn.UseBlankTemplate = False
    fn.ApplicationName = "ModelTemplate"
    fn.Units = NXOpen.Part.Units.Millimeters
    fn.NewFileName = "nx_probe_temp.prt"
    fn.MasterFileName = "nx_probe_temp.prt"
    fn.MakeDisplayedPart = True
    fn.Commit()
    fn.Destroy()
    tp = theSession.Parts.Work

    bodies_before = len(list(tp.Bodies))

    # base block
    bb = tp.Features.CreateBlockFeatureBuilder(NXOpen.Features.Feature.Null)
    bb.Type = NXOpen.Features.BlockFeatureBuilder.Types.OriginAndEdgeLengths
    bb.SetOriginAndLengths(NXOpen.Point3d(0.0,0.0,0.0), "40", "40", "40")
    bb.SetBooleanOperationAndTarget(NXOpen.Features.Feature.BooleanType.Create, NXOpen.Body.Null)
    blk = bb.CommitFeature(); bb.Destroy()
    blk_body = blk.GetBodies()[0]
    C['block_ok'] = True

    # C1: EdgeBlend (fillet) on block edges
    try:
        eb = tp.Features.CreateEdgeBlendBuilder(NXOpen.Features.Feature.Null)
        edges = list(blk_body.GetEdges())
        eb.EdgesToBlend.Add(edges[0])
        eb.DefaultRadius.RightHandSide = "5"
        ef = eb.CommitFeature(); eb.Destroy()
        C['edgeblend_ok'] = True
        # undo this feature (delete) so it doesn't pollute
        ufs.Obj.DeleteObject(int(ef.Tag))
        C['edgeblend_cleanup'] = True
    except Exception as e:
        C['edgeblend_err'] = repr(e)[:200]

    # C2: Chamfer
    try:
        cb = tp.Features.CreateChamferBuilder(NXOpen.Features.Feature.Null)
        C['chamfer_builder_created'] = True
        cb.Destroy()
    except Exception as e:
        C['chamfer_err'] = repr(e)[:200]

    # C3: Hole (simple through hole)
    try:
        hb = tp.Features.CreateHolePackageBuilder(NXOpen.Features.HolePackage.Null)
        C['hole_builder_created'] = True
        hb.Destroy()
    except Exception as e:
        C['hole_err'] = repr(e)[:200]

    # C4: Pattern feature builder
    try:
        pb = tp.Features.CreatePatternFeatureBuilder(NXOpen.Features.PatternFeature.Null)
        C['pattern_builder_created'] = True
        pb.Destroy()
    except Exception as e:
        C['pattern_err'] = repr(e)[:200]

    # C5: Shell builder
    try:
        shb = tp.Features.CreateShellBuilder(NXOpen.Features.Shell.Null)
        C['shell_builder_created'] = True
        shb.Destroy()
    except Exception as e:
        C['shell_err'] = repr(e)[:200]

    # C6: Sweep builder (along curve)
    try:
        swb = tp.Features.CreateSweepBuilder(NXOpen.Features.Sweep.Null)
        C['sweep_builder_created'] = True
        swb.Destroy()
    except Exception as e:
        C['sweep_err'] = repr(e)[:200]

    # C7: Loft builder (skill says does NOT exist)
    try:
        lfb = tp.Features.CreateLoftBuilder(NXOpen.Features.Loft.Null)
        C['loft_builder_created'] = True
        lfb.Destroy()
    except Exception as e:
        C['loft_err'] = repr(e)[:200]

    # ---------- real MOVE test on a tiny sphere in temp part ----------
    MT = {}
    sb = tp.Features.CreateSphereBuilder(NXOpen.Features.Sphere.Null)
    sb.Type = NXOpen.Features.SphereBuilder.Types.CenterPointAndDiameter
    sb.CenterPoint = tp.Points.CreatePoint(NXOpen.Point3d(0.0,0.0,0.0))
    sb.Diameter.RightHandSide = "4"
    sf = sb.CommitFeature(); sb.Destroy()
    sph = sf.GetBodies()[0]
    stag = int(sph.Tag)
    box0 = [float(v) for v in ufs.ModlGeneral.AskBoundingBox(stag)]
    MT['bbox_before'] = [round(x,2) for x in box0]

    # try UF Modl.TransformEntities with a translation matrix (row-major 4x4)
    T = [1,0,0,100,  0,1,0,0,  0,0,1,0,  0,0,0,1]
    try:
        rr = ufs.Modl.TransformEntities(1, [stag], T)
        MT['uf_transformentities_return'] = str(rr)
        box1 = [float(v) for v in ufs.ModlGeneral.AskBoundingBox(stag)]
        MT['bbox_after_uf'] = [round(x,2) for x in box1]
        MT['uf_moved'] = (abs(box1[0]-box0[0]-100) < 0.01)
    except Exception as e:
        MT['uf_transformentities_err'] = repr(e)[:200]

    # try MoveObjectBuilder if creatable: try several factory spellings
    for fname in ['CreateMoveObjectBuilder','CreateMoveObject']:
        fn2 = getattr(tp.Features, fname, None)
        if fn2 is not None:
            try:
                # try with Feature.Null, then with NXOpen.Features.MoveObject.Null, then no-arg-ish
                for arg in [NXOpen.Features.Feature.Null]:
                    try:
                        mb = fn2(arg); MT['%s_ok'%fname]=True; mb.Destroy(); break
                    except Exception as e2:
                        MT['%s_arg_err'%fname] = repr(e2)[:160]
            except Exception as e:
                MT['%s_call_err'%fname] = repr(e)[:160]
        else:
            MT['%s'%fname] = 'MISSING'

    # try MoveBodyBuilder
    try:
        mbb = tp.Features.CreateMoveBodyBuilder(NXOpen.Features.MoveBody.Null)
        MT['movebody_builder_created'] = True
        # can we set body to move?
        try:
            mbb.BodyToMove = sph
            MT['movebody_body_to_move_settable'] = True
        except Exception as e:
            MT['movebody_body_to_move_err'] = repr(e)[:160]
        mbb.Destroy()
    except Exception as e:
        MT['movebody_err'] = repr(e)[:160]

    # clean up the sphere
    ufs.Obj.DeleteObject(stag)
    MT['sphere_cleaned'] = True
    C['move_test'] = MT

    # close temp part without saving
    tp.Close(NXOpen.BasePartCloseWholeTree.FalseValue, NXOpen.BasePartCloseModified.No, None)
    C['temp_part_closed'] = True
except Exception as e:
    C['FATAL'] = repr(e)[:300]
    try:
        if tp is not None and int(tp.Tag) in [int(p.Tag) for p in theSession.Parts]:
            tp.Close(NXOpen.BasePartCloseWholeTree.FalseValue, NXOpen.BasePartCloseModified.No, None)
    except Exception:
        pass

R['empirical'] = C
result = R
