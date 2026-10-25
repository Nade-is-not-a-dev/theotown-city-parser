"""Object parsing for the main City object.

The binary format uses a string table: every new string (key or
value) is stored once, in order, and later uses are a 1-byte
reference (tag 0x14 for keys, 0x17 for values) or a 2-byte
reference (tag 0x15). Tag 0x18 is a short string (1-byte length).

A linear scan first builds that table. A recursive parser then
reads values with it, so a reference id means the same thing in
every file even though the numbers change between files.

Objects (tag 0x03) come in two shapes:
- plain maps: fields are key + value, e.g. ground tiles {'j': 31, 'f': 8}
- class objects: a 0x14 marker, then an unnamed type string, then
  key + value fields, e.g. trees/roads/buildings
  {'_type': '$road00', 'x': 39, 'y': 223, ...}
The two are told apart by what follows the 0x14 marker: a type
string means class object, a value tag means the marker was a key.
"""
import struct
from collections import Counter

from .format import find_section, s8

_VALUE_TAGS = (0x01, 0x03, 0x07, 0x08, 0x09, 0x0E, 0x0F, 0x11, 0x12, 0x13,
               0x14, 0x15, 0x16, 0x17, 0x18)


def build_string_table(dec, off):
    """Scan the object once, in order, and collect all strings."""
    strings = []
    i = off
    while i < len(dec):
        t = dec[i]
        if t in (0x01, 0x02, 0x03, 0x04, 0x11, 0x12):
            i += 1
        elif t == 0x07 or t == 0x08:
            i += 5
        elif t == 0x09:
            i += 9
        elif t == 0x0E:
            i += 3
        elif t == 0x0F:
            i += 2
        elif t in (0x14, 0x17):
            i += 2
        elif t == 0x15:
            i += 3
        elif t == 0x18:
            ln = dec[i + 1]
            strings.append(dec[i + 2:i + 2 + ln].decode("utf-8", "replace"))
            i += 2 + ln
        elif t in (0x13, 0x16):
            ln = struct.unpack(">H", dec[i + 1:i + 3])[0]
            strings.append(dec[i + 3:i + 3 + ln].decode("utf-8", "replace"))
            i += 3 + ln
        else:
            break
    return strings


class Parser:
    """Recursive parser for tagged values, using a string table."""

    def __init__(self, dec, strings):
        self.dec = dec
        self.strings = strings

    def _str(self, idx):
        return self.strings[idx] if 0 <= idx < len(self.strings) else f"<str#{idx}>"

    def parse(self, i):
        dec = self.dec
        t = dec[i]
        if t == 0x01:  # array
            arr = []
            i += 1
            while dec[i] != 0x02:
                v, i = self.parse(i)
                arr.append(v)
            return arr, i + 1
        if t == 0x03:  # object
            obj = {}
            i += 1
            # Class marker? 03 14 <id> followed by a type string.
            if (dec[i] == 0x14 and i + 2 < len(dec)
                    and dec[i + 2] in (0x16, 0x17)):
                obj["_class_ref"] = self._str(dec[i + 1])
                i += 2
            while dec[i] != 0x04:
                if dec[i] in (0x16, 0x17, 0x18):
                    # Unnamed type value, e.g. a tree/road/building id.
                    v, i = self.parse(i)
                    obj["_type"] = v
                    continue
                if dec[i] == 0x13:
                    ln = struct.unpack(">H", dec[i + 1:i + 3])[0]
                    key = dec[i + 3:i + 3 + ln].decode("utf-8", "replace")
                    i += 3 + ln
                elif dec[i] == 0x14:
                    key = self._str(dec[i + 1])
                    i += 2
                elif dec[i] == 0x15:
                    key = self._str(struct.unpack(">H", dec[i + 1:i + 3])[0])
                    i += 3
                else:
                    raise ValueError(f"bad key tag {hex(dec[i])} at {i}")
                v, i = self.parse(i)
                obj[key] = v
            return obj, i + 1
        if t == 0x07:
            return struct.unpack(">f", dec[i + 1:i + 5])[0], i + 5
        if t == 0x08:
            return struct.unpack(">i", dec[i + 1:i + 5])[0], i + 5
        if t == 0x09:
            return struct.unpack(">q", dec[i + 1:i + 9])[0], i + 9
        if t == 0x0E:
            return struct.unpack(">h", dec[i + 1:i + 3])[0], i + 3
        if t == 0x0F:
            return s8(dec[i + 1]), i + 2
        if t == 0x11:
            return True, i + 1
        if t == 0x12:
            return False, i + 1
        if t in (0x13, 0x16):
            ln = struct.unpack(">H", dec[i + 1:i + 3])[0]
            return dec[i + 3:i + 3 + ln].decode("utf-8", "replace"), i + 3 + ln
        if t == 0x18:
            ln = dec[i + 1]
            return dec[i + 2:i + 2 + ln].decode("utf-8", "replace"), i + 2 + ln
        if t == 0x17:
            return self._str(dec[i + 1]), i + 2
        if t == 0x14:
            return {"$ref": self._str(dec[i + 1])}, i + 2
        if t == 0x15:
            idx = struct.unpack(">H", dec[i + 1:i + 3])[0]
            return {"$ref": self._str(idx)}, i + 3
        raise ValueError(f"bad value tag {hex(t)} at {i}")


def parse_section(dec, key, strings):
    """Parse one top-level section by key. Returns None if missing."""
    off = find_section(dec, key)
    if off < 0:
        return None
    parser = Parser(dec, strings)
    value, _ = parser.parse(off + 3 + len(key))
    return value


def _summarise(items):
    """Count objects by type and find their x/y range."""
    if not isinstance(items, list):
        return {"count": 0, "by_type": {}, "x_range": None, "y_range": None}
    by_type = Counter()
    xs, ys = [], []
    for it in items:
        if not isinstance(it, dict):
            continue
        by_type[it.get("_type", "<no type>")] += 1
        if isinstance(it.get("x"), int):
            xs.append(it["x"])
        if isinstance(it.get("y"), int):
            ys.append(it["y"])
    return {
        "count": len(items),
        "by_type": dict(by_type.most_common()),
        "x_range": [min(xs), max(xs)] if xs else None,
        "y_range": [min(ys), max(ys)] if ys else None,
    }


def parse_objects(dec, strings):
    """Parse the sections that hold things on the map.

    Returns a dict with the full lists for trees, roads, buildings,
    plus summaries, and the rail / bus-stop lists (rails may be a
    wrapper object {'rails': [...]} in some files).
    """
    trees = parse_section(dec, "trees", strings) or []
    roads = parse_section(dec, "roads", strings) or []
    buildings = parse_section(dec, "buildings", strings) or []
    bus_stops = parse_section(dec, "bus stops", strings) or []
    rails_raw = parse_section(dec, "rails", strings)
    if isinstance(rails_raw, dict):
        rails = rails_raw.get("rails", [])
    elif isinstance(rails_raw, list):
        rails = rails_raw
    else:
        rails = []
    return {
        "trees": trees,
        "trees_summary": _summarise(trees),
        "roads": roads,
        "roads_summary": _summarise(roads),
        "buildings": buildings,
        "buildings_summary": _summarise(buildings),
        "bus_stops": bus_stops,
        "bus_stops_summary": _summarise(bus_stops),
        "rails": rails,
        "rails_summary": _summarise(rails),
    }
