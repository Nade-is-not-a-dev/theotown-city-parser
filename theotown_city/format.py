"""File layout and low-level reading for TheoTown .city files.

A .city file is:
    [u16 BE header_len][JSON header][gzip stream]

The gzip payload is:
    [minimap pixels][preview size][preview pixels][main City object]

Pixel order is A,B,G,R (alpha first, then blue, green, red).
That is easy to get wrong: read as A,R,G,B and water looks yellow
and sand looks blue. See correct_rgba().
"""
import gzip
import json
import struct
from pathlib import Path


def s8(b):
    """One unsigned byte as a signed int8."""
    return b - 256 if b >= 128 else b


def correct_rgba(raw):
    """Swap R and B in A,B,G,R pixel bytes. Returns A,R,G,B bytes."""
    out = bytearray(len(raw))
    for i in range(0, len(raw), 4):
        a, b, g, r = raw[i], raw[i + 1], raw[i + 2], raw[i + 3]
        out[i], out[i + 1], out[i + 2], out[i + 3] = a, r, g, b
    return bytes(out)


def parse_header(data):
    """Return (header_len, header_dict) from the raw file bytes."""
    if len(data) < 2:
        raise ValueError("file too short")
    hlen = struct.unpack(">H", data[:2])[0]
    header = json.loads(data[2:2 + hlen])
    return hlen, header


def load_city(path):
    """Read a .city file. Returns a dict; the raw bytes are kept for analysis."""
    path = Path(path)
    raw = path.read_bytes()
    hlen, header = parse_header(raw)
    gz = raw[2 + hlen:]
    if gz[:3] != b"\x1f\x8b\x08":
        raise ValueError(f"{path}: expected gzip after header, got {gz[:3].hex()}")
    dec = gzip.decompress(gz)
    w = header.get("width", 256)
    h = header.get("height", 256)
    minimap_len = w * h * 4
    minimap = dec[:minimap_len]
    off = minimap_len
    pw, ph = struct.unpack(">II", dec[off:off + 8])
    off += 8
    preview_len = pw * ph * 4
    preview = dec[off:off + preview_len]
    return {
        "path": str(path),
        "file_size": len(raw),
        "header_len": hlen,
        "header": header,
        "gzip_len": len(gz),
        "decompressed_len": len(dec),
        "minimap": minimap,
        "minimap_size": (w, h),
        "preview": preview,
        "preview_size": (pw, ph),
        "object_offset": off + preview_len,
        "decompressed": dec,
    }


# Tagged binary values in the main City object.
# Tag bytes: 0x01 array start, 0x02 array end, 0x03 object start,
# 0x04 object end, 0x07 float32, 0x08 int32, 0x09 int64, 0x0e int16,
# 0x0f int8, 0x11 true (?), 0x12 false, 0x13 key string, 0x16 value string.
# 0x14 / 0x15 / 0x17 are reference ids; a full object-graph parse
# is not done here.
def find_key_value(dec, key, start=0):
    """Find one scalar field by key in the main object. None if not found."""
    pat = b"\x13" + struct.pack(">H", len(key)) + key.encode()
    i = dec.find(pat, start)
    if i < 0:
        return None
    vpos = i + len(pat)
    if vpos >= len(dec):
        return None
    tag = dec[vpos]
    try:
        if tag == 0x0F:
            return s8(dec[vpos + 1])
        if tag == 0x0E:
            return struct.unpack(">h", dec[vpos + 1:vpos + 3])[0]
        if tag == 0x08:
            return struct.unpack(">i", dec[vpos + 1:vpos + 5])[0]
        if tag == 0x09:
            return struct.unpack(">q", dec[vpos + 1:vpos + 9])[0]
        if tag == 0x07:
            return struct.unpack(">f", dec[vpos + 1:vpos + 5])[0]
        if tag == 0x12:
            return False
        if tag == 0x11:
            return True
        if tag == 0x16:
            ln = struct.unpack(">H", dec[vpos + 1:vpos + 3])[0]
            return dec[vpos + 3:vpos + 3 + ln].decode("utf-8", "replace")
        return None
    except Exception:
        return None


def find_section(dec, key):
    """Byte offset of a section key, or -1."""
    pat = b"\x13" + struct.pack(">H", len(key)) + key.encode()
    return dec.find(pat)


def parse_tagged_int_array(dec, key, count=65536):
    """Parse an array of tagged ints (0x0f int8 / 0x0e int16).

    Returns (values, n_int16, end_offset) or (None, 0, None).
    """
    i = find_section(dec, key)
    if i < 0:
        return None, 0, None
    idx = i + 3 + len(key)
    if idx >= len(dec) or dec[idx] != 0x01:
        return None, 0, None
    idx += 1
    vals = []
    n16 = 0
    while len(vals) < count and idx < len(dec):
        tag = dec[idx]
        if tag == 0x0F:
            vals.append(s8(dec[idx + 1]))
            idx += 2
        elif tag == 0x0E:
            vals.append(struct.unpack(">h", dec[idx + 1:idx + 3])[0])
            n16 += 1
            idx += 3
        else:
            break
    return vals, n16, idx
