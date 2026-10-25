"""Object parsing for the main City object.

The binary format is the binary JSON of the game's own library,
``io.blueflower.stapel2d.util.json`` (BinaryJsonReader /
BinaryJsonWriter, confirmed by decompiling TheoTown 1.12.88a).
Token table (from BinaryJsonReader / BinaryJsonWriter):
- 1 array start, 2 array end, 3 object start, 4 object end
- 5 name (string() encoding), 6 string value (string() encoding)
- 7 float32, 8 int32, 9 int64, 11 boolean (1 byte), 12 null,
  14 int16, 15 int8, 16 float64, 17 true, 18 false
- 19 new name string (readUTF, added to the pool),
  20 name ref (1-byte index), 21 name ref (2-byte index)
- 22 new string value (readUTF, added to the pool),
  23 string ref (1-byte index), 24 string ref (2-byte index)
- 0x80-0xff tiny int: the token byte itself is the value,
  decodeTinyInt = ((byte)(token << 1)) >> 1, range -64..63
  (only when the writer's USE_TINY_INT_ENCODING flag is on)

Names and string values share one pool: every new string is
stored once, in order, and later uses are a reference. The writer
uses tokens 19-24 for strings, never 5/6, in the .city files seen
so far; 5/6 are handled anyway for completeness.

Objects are plain maps: fields are name + value. A tree / road /
building object has an ``id`` field first (the draft id, e.g.
``$road00``). Trees whose draft is the default ``$tree00`` have
no ``id`` field at all — the writer omits it (Tree.save) and the
reader defaults to ``$tree00``.
"""
import struct
from collections import Counter

from .format import find_section, s8


def _tiny(token):
    """Decode a tiny-int token byte to its value (-64..63)."""
    v = (token << 1) & 0xFF
    if v >= 128:
        v -= 256
    return v // 2


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
        elif t in (0x15, 0x18):
            i += 3
        elif t in (0x05, 0x06):
            # string(): 0 = new string (readUTF), else 2-byte index.
            if dec[i + 1] == 0:
                ln = struct.unpack(">H", dec[i + 2:i + 4])[0]
                strings.append(dec[i + 4:i + 4 + ln].decode("utf-8", "replace"))
                i += 4 + ln
            else:
                i += 3
        elif t in (0x13, 0x16):
            ln = struct.unpack(">H", dec[i + 1:i + 3])[0]
            strings.append(dec[i + 3:i + 3 + ln].decode("utf-8", "replace"))
            i += 3 + ln
        elif t >= 0x80:
            i += 1  # tiny int: the token byte is the whole value
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

    def _string_encoding(self, i):
        """Token 5/6: 0 = new readUTF string, else 2-byte pool index."""
        b = self.dec[i + 1]
        if b == 0:
            ln = struct.unpack(">H", self.dec[i + 2:i + 4])[0]
            s = self.dec[i + 4:i + 4 + ln].decode("utf-8", "replace")
            return s, i + 4 + ln
        idx = ((b - 1) * 256) + self.dec[i + 2]
        return self._str(idx), i + 3

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
        if t == 0x03:  # object: fields are name + value, until 0x04
            obj = {}
            i += 1
            while dec[i] != 0x04:
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
                elif dec[i] == 0x05:
                    key, i = self._string_encoding(i)
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
            return dec[i + 1] > 0, i + 2
        if t == 0x12:
            return None, i + 1
        if t in (0x13, 0x16):
            ln = struct.unpack(">H", dec[i + 1:i + 3])[0]
            return dec[i + 3:i + 3 + ln].decode("utf-8", "replace"), i + 3 + ln
        if t in (0x05, 0x06):
            return self._string_encoding(i)
        if t == 0x17:
            return self._str(dec[i + 1]), i + 2
        if t == 0x14:
            return {"$ref": self._str(dec[i + 1])}, i + 2
        if t == 0x15:
            idx = struct.unpack(">H", dec[i + 1:i + 3])[0]
            return {"$ref": self._str(idx)}, i + 3
        if t == 0x18:
            idx = struct.unpack(">H", dec[i + 1:i + 3])[0]
            return self._str(idx), i + 3
        if t == 0x10:
            # Not used by the binary writer; kept so a stray token
            # does not break the scan (treated as a 1-byte value).
            return dec[i + 1], i + 2
        if t >= 0x80:
            return _tiny(t), i + 1
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
    """Count objects by type (their 'id' field) and find x/y range.

    Objects with no 'id' are default trees ($tree00) — the writer
    omits the id for them, so they are counted as '<no id>'.
    """
    if not isinstance(items, list):
        return {"count": 0, "by_type": {}, "x_range": None, "y_range": None}
    by_type = Counter()
    xs, ys = [], []
    for it in items:
        if not isinstance(it, dict):
            continue
        by_type[it.get("id", "<no id>")] += 1
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


def parse_heights(dec, strings):
    """Reconstruct terrain heights from the delta-encoded arrays.

    The writer stores running differences (GroundLoader.saveTag):
    each stored value is height minus the previous height, in
    stored order, starting from 0. 'heights' and 'heightsDY' are
    stored row-major (y outer, x inner); 'heightsDX' is stored
    column-major (x outer, y inner). Summing in stored order gives
    the real heights back.
    Returns {name: {'count': n, 'min': m, 'max': m}}.
    """
    out = {}
    for name in ("heights", "heightsDX", "heightsDY"):
        vals = parse_section(dec, name, strings)
        if not isinstance(vals, list):
            continue
        total = 0
        lo = hi = None
        for v in vals:
            if not isinstance(v, int):
                continue
            total += v
            lo = total if lo is None or total < lo else lo
            hi = total if hi is None or total > hi else hi
        out[name] = {"count": len(vals), "min": lo, "max": hi}
    return out
