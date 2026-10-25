"""Export minimap and preview images as PNGs (true colours)."""
from pathlib import Path

from .format import correct_rgba, load_city

# Marker colours for the overlay map.
TREE_COLOUR = (0, 128, 0)        # dark green dot
ROAD_COLOUR = (40, 40, 40)       # near-black
BUILDING_COLOUR = (255, 0, 0)    # red
BUS_STOP_COLOUR = (255, 165, 0)  # orange
RAIL_COLOUR = (128, 0, 128)      # purple


def _image_from_raw(raw, w, h, white_bg=False):
    from PIL import Image
    corr = correct_rgba(raw)
    img = Image.new("RGBA", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            o = (y * w + x) * 4
            a, r, g, b = corr[o], corr[o + 1], corr[o + 2], corr[o + 3]
            px[x, y] = (r, g, b, a)
    if white_bg:
        bg = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        bg.alpha_composite(img)
        return bg.convert("RGB")
    return img


def export_images(path, outdir):
    """Write *_minimap.png and *_preview.png (plus *_game.png copies).

    The *_game.png files are the same true-colour images, kept so the
    filenames from v1.0 still work.
    """
    c = load_city(path)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = Path(path).stem
    w, h = c["minimap_size"]
    img = _image_from_raw(c["minimap"], w, h)
    mp = outdir / f"{stem}_minimap.png"
    img.save(mp)
    mpg = outdir / f"{stem}_minimap_game.png"
    img.save(mpg)
    pw, ph = c["preview_size"]
    imgp = _image_from_raw(c["preview"], pw, ph, white_bg=True)
    pp = outdir / f"{stem}_preview.png"
    imgp.save(pp)
    ppg = outdir / f"{stem}_preview_game.png"
    imgp.save(ppg)
    return str(mp), str(pp), str(mpg), str(ppg)


def export_overlay(path, outdir, scale=4):
    """Draw trees, roads, buildings, rails and bus stops on the minimap.

    The minimap is scaled up (default 4x, so 256 -> 1024) and each
    object is drawn as a small square at its (x, y) tile:
    trees dark green, roads near-black, buildings red,
    bus stops orange, rails purple. Returns the overlay file path.
    """
    from .analysis import analyse
    from PIL import Image, ImageDraw
    r = analyse(path)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = Path(path).stem
    w, h = r["minimap_size"]
    c = load_city(path)
    img = _image_from_raw(c["minimap"], w, h).convert("RGB")
    img = img.resize((w * scale, h * scale), Image.NEAREST)
    draw = ImageDraw.Draw(img)
    objs = r["objects"]

    def mark(items, colour, size=3):
        for it in items:
            if not isinstance(it, dict):
                continue
            x, y = it.get("x"), it.get("y")
            if not isinstance(x, int) or not isinstance(y, int):
                continue
            px, py = x * scale, y * scale
            draw.rectangle([px, py, px + size - 1, py + size - 1], fill=colour)

    mark(objs["roads"], ROAD_COLOUR, size=scale)
    mark(objs["rails"], RAIL_COLOUR, size=scale)
    mark(objs["trees"], TREE_COLOUR, size=2)
    mark(objs["bus_stops"], BUS_STOP_COLOUR, size=scale)
    mark(objs["buildings"], BUILDING_COLOUR, size=scale)
    out = outdir / f"{stem}_overlay.png"
    img.save(out)
    return str(out)
