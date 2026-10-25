"""Ground types in a .city file.

The 'ground type arr' section lists the ground types in order;
each tile in 'ground arr' has a 'j' field that is an index into
that list (0-31). 'f' is a per-tile variation / frame value.

The reference ids for 'j' and 'f' (0x52 / 0x53) swap between files,
depending on which key appears first, so the mapping is read from
each file instead of being hard-coded.
"""
import re
import struct
from collections import Counter

from .format import find_section

# Order of 'ground type arr' in the files tested (TheoTown 1.12.88).
GROUND_TYPES = [
    "$ground00", "$dirt00", "$sand00", "$beach_gnd00", "$permanent_snow00",
    "$ground_dirt00", "$ground_wildgrass00", "$ground_darkgrass00",
    "$ground_rockysand00", "$ground_forestgrass00", "$ground_cursedland00",
    "$asphalt00", "$asphalt01", "$asphalt02", "$asphalt03", "$asphalt04",
    "$concrete00", "$concrete01", "$sandstonetiles00", "$brick00",
    "$woodenpier00", "$cobblestones00", "$fancylongtiles00", "$finemarble00",
    "$ground_asphalt00", "$ground_concrete00", "$ground_sandstone00",
    "moonground.kt101", "$moon_ground_ore00", "$moon_ground_ore01",
    "$moon_ground_ore02", "$water00",
]


def parse_ground_types(dec):
    """Count tiles per ground type. Returns {'tiles': n, 'counts': {...}}.

    This is the independent check for the minimap colours: water tiles
    ($water00) should match the cyan pixels in the corrected minimap.
    """
    s = find_section(dec, "ground arr")
    e = find_section(dec, "fences")
    if s < 0 or e < 0:
        return None
    sec = dec[s:e]
    explicits = re.findall(rb"\x13\x00\x01(.)", sec[:200])
    if not explicits:
        return None
    ref_j = 0x52 if explicits[0] == b"j" else 0x53
    i = sec.find(b"\x01", 0) + 1
    cnt = Counter()
    n = 0
    while i < len(sec) and sec[i] != 0x02:
        if sec[i] != 0x03:
            break
        i += 1
        jval = None
        while sec[i] != 0x04:
            if sec[i] == 0x13:
                key = chr(sec[i + 3])
                i += 4
            elif sec[i] == 0x14:
                key = "j" if sec[i + 1] == ref_j else "f"
                i += 2
            else:
                raise ValueError(f"ground arr tag {hex(sec[i])} at {i}")
            if sec[i] == 0x0F:
                v = sec[i + 1]
                i += 2
            elif sec[i] == 0x0E:
                v = struct.unpack(">h", sec[i + 1:i + 3])[0]
                i += 3
            else:
                raise ValueError(f"ground arr value tag {hex(sec[i])} at {i}")
            if key == "j":
                jval = v
        i += 1
        n += 1
        if jval is None:
            cnt["<no j / default>"] += 1
        elif 0 <= jval < len(GROUND_TYPES):
            cnt[GROUND_TYPES[jval]] += 1
        else:
            cnt[f"<j={jval}>"] += 1
    return {"tiles": n, "counts": dict(cnt.most_common())}
