"""Export minimap and preview images as PNGs (true colours)."""
from pathlib import Path

from .format import correct_rgba, load_city


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
