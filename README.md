# theotown-city-parser

A small read-only parser for TheoTown `.city` save files. It reads the
header, the minimap and preview images, and the main City object, and can
export the images as PNGs.

Tested on TheoTown 1.12.88 (version 11288), 256x256 maps.

## Install

Requires Python 3.9+ and Pillow (only for image export).

```bash
pip install -e .
# or, without installing:
pip install pillow
python -m theotown_city info your-city.city
```

## Usage

```bash
# Summary for one or more cities
python -m theotown_city info 0_0.city 0_4.city
python -m theotown_city info --json 0_0.city

# Export minimap + preview PNGs
python -m theotown_city export-images 0_0.city --out out/

# Write a markdown report
python -m theotown_city report *.city --out report.md
```

## File format (reverse-engineered)

```
.city file:
  [u16 BE header_len][JSON header][gzip stream]

gzip payload:
  [minimap: 256x256 px, 4 bytes/px]
  [preview size: u32 BE width, u32 BE height]
  [preview: 512x270 px, 4 bytes/px, isometric view]
  [main City object: custom tagged binary format]
```

The JSON header is plain text and holds the seed, size, version, game mode,
money, habitants, and the plugins used.

The main object uses the binary JSON of the game's own library,
`io.blueflower.stapel2d.util.json` (`BinaryJsonReader` /
`BinaryJsonWriter`), confirmed by decompiling TheoTown 1.12.88a.
Token table: 1 array start, 2 array end, 3 object start,
4 object end, 7 float32, 8 int32, 9 int64, 11 boolean (1 byte),
12 null, 14 int16, 15 int8, 16 float64, 17 true, 18 false.
Names use tokens 19 (new string), 20 (1-byte ref), 21 (2-byte
ref); string values use 22, 23, 24 the same way. Names and
values share one pool: every new string is stored once, in
order, and later uses are a reference. Tokens 0x80-0xff are
tiny ints (the byte itself is the value, -64..63). The parser
in `objects.py` first builds that string table, then reads
objects with it — that is how trees, roads and buildings are
decoded, and why reference ids differ between files.

Field meanings (from the game's loaders / object classes):
- Ground tile: `j` = index into `ground type arr` (omitted when
  0 = `$ground00`), `f` = frame. Heights are delta-encoded:
  each stored value is the difference from the previous tile.
- Tree: `id` (draft, omitted when it is the default `$tree00`),
  `f` = frame, `x`, `y`.
- Road: `id`, `f` = frame (frame % 64), `x`, `y`, `ta` = traffic
  amount / 100, `taa` = [traffic level 1/2/3] / 100, `ctr` = car
  counter, `cctr` = chargeable car counter, `lvl` = level,
  `dlvl` = dLevel. Other fields exist for bridges, traffic
  lights, decorations, etc. (see `Road.java` in the APK).
- The file is loaded by `CityKeeper`: header JSON, gzip,
  minimap, preview, then the main object, dispatched by section
  tag to one loader per section (`GroundLoader`, `TreeLoader`,
  `RoadLoader`, ...).

## Colour gotcha: pixels are A,B,G,R

Minimap and preview pixels are stored as **A,B,G,R** (alpha, blue, green,
red), not A,R,G,B. Reading them the usual way swaps water and sand:

- raw mustard yellow `(193,168,39)` is really cyan `(39,168,193)` = water
- raw pale blue `(160,192,210)` is really beige `(210,192,160)` = sand

Proof from the files themselves: in the `ground arr` section, the ground
type field `j == 31` (`$water00`) covers 40,322 tiles in one test map, and
99.9% of those tiles are the mustard-yellow pixels. The parser swaps R
and B (`format.correct_rgba`), so the exported PNGs match the game.
Water share from the corrected minimap also matches the `$water00`
tile count for every map tested.

## What it does (v1.3)

- Header JSON, money, seed, size, version, id, timestamps
- Minimap + preview PNG export, in true colours
- Scalar fields from the main object (width, height, xp, estate, taxes, ...)
- Heights / heightsDX / heightsDY arrays (raw tagged values)
- Ground-type counts from `ground arr` (independent terrain check)
- Trees, roads, buildings, rails and bus stops, fully parsed
  (type, x, y) via the string-table parser in `objects.py`
- Overlay map: trees, roads, buildings, rails and bus stops drawn
  on the minimap (`*_overlay.png`, trees green, roads black,
  buildings red, bus stops orange, rails purple)


## What it does not do

- No full recursive parse of ground / trees / buildings / roads / budget.
- No write-back. The tool is read-only by design and never writes a
  `.city` file. Editing is possible in principle (the header JSON money
  is plain text), but a round-trip writer has not been tested against
  the game. Always keep a backup of your originals.
- Heights look delta-encoded per row; the tool reports the raw values.

## License

MIT. See [LICENSE](LICENSE).
