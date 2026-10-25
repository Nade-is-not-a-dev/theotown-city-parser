"""Analysis: scalars, heights, terrain stats.

Colours below use the corrected RGB values (see format.correct_rgba).
With the raw A,R,G,B reading, water and sand are swapped.
"""
import colorsys
from collections import Counter

from .format import find_key_value, find_section, load_city, parse_tagged_int_array
from .ground import parse_ground_types
from .objects import build_string_table, parse_objects


def classify_terrain(r, g, b):
    """One corrected minimap pixel -> water / sand / forest / other.

    water: cyan, hue ~175-215. sand: beige, hue ~30-55, low saturation,
    bright. forest: green, hue ~85-170. other: brown dirt, grey, olive.
    """
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    hd = h * 360
    if 175 <= hd <= 215 and b > r + 10:
        return "water"
    if 30 <= hd <= 55 and s < 0.45 and v > 0.65:
        return "sand"
    if 85 <= hd <= 170:
        return "forest"
    return "other"


def minimap_stats(minimap, w, h):
    """Colour counts and terrain percentages for a corrected minimap."""
    from .format import correct_rgba
    corr = correct_rgba(minimap)
    pix = [tuple(corr[i + 1:i + 4]) for i in range(0, len(corr), 4)]
    cnt = Counter(pix)
    classes = Counter(classify_terrain(*p) for p in pix)
    return {
        "pixels": len(pix),
        "distinct_colours": len(cnt),
        "most_common_colours": [
            {"rgb": list(c), "count": n} for c, n in cnt.most_common(8)
        ],
        "terrain_classes_pct": {
            k: round(v / len(pix) * 100, 2) for k, v in classes.most_common()
        },
    }


def _heights(dec):
    """Parse heights / heightsDX / heightsDY arrays (raw tagged values)."""
    out = {}
    for key in ["heights", "heightsDX", "heightsDY"]:
        vals, n16, _ = parse_tagged_int_array(dec, key)
        if not vals:
            continue
        # Positions of int16 entries: row starts are at multiples of 256.
        i = find_section(dec, key)
        idx = i + 3 + len(key) + 1
        pos = []
        n = 0
        while n < len(vals) and idx < len(dec):
            tag = dec[idx]
            if tag == 0x0F:
                idx += 2
                n += 1
            elif tag == 0x0E:
                pos.append(n)
                idx += 3
                n += 1
            else:
                break
        out[key] = {
            "count": len(vals),
            "int16_entries": n16,
            "min": min(vals),
            "max": max(vals),
            "mean": round(sum(vals) / len(vals), 3),
            "int16_positions_first10": pos[:10],
            "int16_positions_all_multiple_of_256": (
                all(p % 256 == 0 for p in pos) if pos else None
            ),
        }
    return out


def analyse(path):
    """Full summary for one .city file. Read-only; no files are written."""
    c = load_city(path)
    dec = c["decompressed"]
    hdr = c["header"]
    obj_off = c["object_offset"]

    scalars = {}
    for key in ["width", "height", "name", "seed", "gamemode", "shift x",
                "shift y", "scale x", "rank lvl", "rank day", "id", "xp",
                "cxp", "absolute day", "speed", "estate"]:
        v = find_key_value(dec, key, start=obj_off)
        if v is not None:
            scalars[key] = v

    taxes = []
    for n in range(9):
        v = find_key_value(dec, f"tax {n}", start=obj_off)
        if v is not None:
            taxes.append(v)

    sections = {}
    for key in ["ground", "ground arr", "fences", "heights", "heightsDX",
                "heightsDY", "soundmanager", "trees", "roads", "bus stops",
                "rails", "buildings", "date", "budget", "statistics"]:
        off = find_section(dec, key)
        sections[key] = off if off >= 0 else None

    # Things on the map: trees, roads, buildings, rails, bus stops.
    # The string table is built once and shared by all section parsers.
    strings = build_string_table(dec, obj_off)
    objects = parse_objects(dec, strings)
    roads_off = find_section(dec, "roads")
    approx = {
        "roads_empty_array": (
            dec[roads_off + 3 + len("roads"):roads_off + 3 + len("roads") + 2] == b"\x01\x02"
            if roads_off >= 0 else None
        ),
    }

    result = {
        "path": c["path"],
        "file_size": c["file_size"],
        "header_len": c["header_len"],
        "header": hdr,
        "gzip_len": c["gzip_len"],
        "decompressed_len": c["decompressed_len"],
        "minimap_size": c["minimap_size"],
        "preview_size": c["preview_size"],
        "object_offset": obj_off,
        "minimap_stats": minimap_stats(c["minimap"], hdr.get("width", 256), hdr.get("height", 256)),
        "main_object_scalars": scalars,
        "taxes_0_to_8": taxes,
        "sections_offsets_in_decompressed": sections,
        "heights_arrays": _heights(dec),
        "approx_counts_heuristic": approx,
        "ground_types_from_ground_arr": parse_ground_types(dec, strings),
        "objects": objects,
        "notes": [
            "Header money should match budget.estate in the main object.",
            "Heights look delta-encoded per row; int16 entries at multiples of 256 are likely row-start absolute heights — hypothesis, not verified.",
            "Trees/roads/buildings are fully parsed (type, x, y) via the string-table parser in objects.py. "
            "88 tree entries in the test city have no type string, only f/x/y — reported as '<no type>'.",
            "Minimap/preview pixels are A,B,G,R, not A,R,G,B. Yellow in the raw reading is water, blue in the raw reading is sand/land.",
            "This tool is READ-ONLY. It never writes a .city file.",
        ],
    }
    return result
