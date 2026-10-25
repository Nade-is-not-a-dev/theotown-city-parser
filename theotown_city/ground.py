"""Ground types in a .city file.

The 'ground type arr' section lists the ground types in order;
each tile in 'ground arr' has a 'j' field that is an index into
that list (0-31). 'f' is a per-tile variation / frame value.

The reference ids for 'j' and 'f' change between files, so they
are resolved through the string table (see objects.py), not
hard-coded. The old hard-coded ids broke on files saved after
playing, where more strings come before 'ground arr'.
"""
from collections import Counter

from .objects import parse_section

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


def parse_ground_types(dec, strings=None):
    """Count tiles per ground type. Returns {'tiles': n, 'counts': {...}}.

    This is the independent check for the minimap colours: water tiles
    ($water00) should match the cyan pixels in the corrected minimap.
    Tiles with no 'j' use the default ground type (index 0).
    """
    if strings is None:
        from .objects import build_string_table
        strings = build_string_table(dec, 0)
    tiles = parse_section(dec, "ground arr", strings)
    if not isinstance(tiles, list):
        return None
    cnt = Counter()
    for t in tiles:
        if not isinstance(t, dict):
            continue
        j = t.get("j")
        if j is None:
            cnt["<no j / default>"] += 1
        elif 0 <= j < len(GROUND_TYPES):
            cnt[GROUND_TYPES[j]] += 1
        else:
            cnt[f"<j={j}>"] += 1
    return {"tiles": len(tiles), "counts": dict(cnt.most_common())}
