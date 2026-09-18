# -*- coding: utf-8 -*-
# Extract member signatures for key builder classes to write correct test code.
import re, os
XML = r"E:\NX\Program Files\Siemens\NX2007\NXBIN\managed\NXOpen.xml"
with open(XML, "r", encoding="utf-8", errors="replace") as f:
    txt = f.read()

def members(cls):
    # collect M:/P:/F: lines whose name starts with the class
    pat = re.compile(r'([MPF]):NXOpen\.Features\.' + re.escape(cls) + r'\.([^\"]+?)(?:\([^)]*\))?\s*"')
    found = {}
    for m in pat.finditer(txt):
        kind, name = m.group(1), m.group(2)
        found.setdefault(kind, set()).add(name)
    # also grab any full signatures
    sigs = re.findall(r'M:NXOpen\.Features\.' + re.escape(cls) + r'\.[A-Za-z_]+\([^)]*\)', txt)
    return found, sorted(set(sigs))

for cls in ["MoveObjectBuilder", "MoveBodyBuilder", "MoveFaceBuilder"]:
    found, sigs = members(cls)
    print("==== %s ====" % cls)
    for k in ["P","M","F"]:
        if k in found:
            print("  [%s] %s" % (k, ", ".join(sorted(found[k]))))
    # print a few signature samples
    for s in sigs[:40]:
        print("  SIG:", s)
    print()
