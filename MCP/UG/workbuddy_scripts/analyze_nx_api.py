# -*- coding: utf-8 -*-
# Static analysis of NXOpen.xml / NXOpen.UF.xml to build an authoritative
# capability matrix + hunt for Move/Transform APIs. No live NX needed.
import re, os

NXBIN = r"E:\NX\Program Files\Siemens\NX2007\NXBIN\managed"
xml_main = os.path.join(NXBIN, "NXOpen.xml")
xml_uf = os.path.join(NXBIN, "NXOpen.UF.xml")

def read(p):
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

main = read(xml_main)
uf = read(xml_uf)

out = {}

# 1) All FeatureCollection.Create* factory methods (authoritative builder list)
fc_methods = re.findall(r'M:NXOpen\.Features\.FeatureCollection\.Create(\w+)\(', main)
fc_methods = sorted(set(fc_methods))
out['featurecollection_create_count'] = len(fc_methods)
out['featurecollection_create'] = fc_methods

# 2) Move / Transform related classes & factories
move_classes = sorted(set(re.findall(r'T:NXOpen\.Features\.(?:Move|Transform|Translate|Rotate)\w*', main)))
out['features_move_transform_classes'] = move_classes
move_factories = [m for m in fc_methods if re.search(r'(Move|Transform|Translate|Rotate)', m, re.I)]
out['featurecollection_move_factories'] = move_factories

# 3) Does CreateLoftBuilder exist? (skill claims NOT)
out['has_loft'] = 'Loft' in fc_methods or 'LoftBuilder' in fc_methods or bool(re.search(r'CreateLoft', main))

# 4) UF Modl transform / move functions
uf_modl = re.findall(r'M:NXOpen\.UF\.UFSession\.Modl\.(\w+)\(', uf)
uf_modl = sorted(set(uf_modl))
out['uf_modl_total'] = len(uf_modl)
out['uf_modl_transform_related'] = [m for m in uf_modl if re.search(r'(transform|move|rotat|translate)', m, re.I)]
# also ask for full signature snippets of transform entities
for fn in ['TransformEntities']:
    m = re.search(r'M:NXOpen\.UF\.UFSession\.Modl\.'+fn+r'\([^)]*\)', uf)
    out.setdefault('uf_signatures', {})[fn] = m.group(0) if m else 'NOT FOUND'

# 5) UF for body transform alternatives
uf_transform_classes = sorted(set(re.findall(r'T:NXOpen\.UF\.UFModl\w*', uf)))
out['uf_modl_classes'] = [c for c in uf_transform_classes if re.search(r'(transform|move)', c, re.I)]

# 6) check MoveObjectBuilder factory existence precisely
out['moveobject_factory'] = bool(re.search(r'CreateMoveObjectBuilder', main))
out['movebody_factory'] = bool(re.search(r'CreateMoveBodyBuilder', main))

import json
print(json.dumps(out, ensure_ascii=False, indent=1))
