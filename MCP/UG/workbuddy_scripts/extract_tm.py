# -*- coding: utf-8 -*-
import re, os
XML = r"E:\NX\Program Files\Siemens\NX2007\NXBIN\managed\NXOpen.xml"
with open(XML, "r", encoding="utf-8", errors="replace") as f:
    txt = f.read()

def members(cls, ns="GeometricUtilities"):
    pat = re.compile(r'([MPF]):NXOpen\.' + ns + r'\.' + re.escape(cls) + r'\.([^\"]+?)(?:\([^)]*\))?\s*"')
    found = {}
    for m in pat.finditer(txt):
        found.setdefault(m.group(1), set()).add(m.group(2))
    sigs = re.findall(r'M:NXOpen\.' + ns + r'\.' + re.escape(cls) + r'\.[A-Za-z_]+\([^)]*\)', txt)
    return found, sorted(set(sigs))

for cls in ["TransformMotion"]:
    found, sigs = members(cls)
    print("==== %s ====" % cls)
    for k in ["P","M","F"]:
        if k in found:
            print("  [%s] %s" % (k, ", ".join(sorted(found[k]))))
    for s in sigs[:60]:
        print("  SIG:", s)
    print()

# MotionType options
mt = re.findall(r'F:NXOpen\.GeometricUtilities\.TransformMotion\.[A-Za-z_]+', txt)
print("TransformMotion enum flags:", sorted(set(mt)))
# and MoveObjectResultOptions already known
