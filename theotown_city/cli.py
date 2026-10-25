"""Command-line interface: info, export-images, report."""
import argparse
import json
from pathlib import Path

from .analysis import analyse
from .images import export_images, export_overlay


def _print_info(r, f):
    hdr = r["header"]
    print(f"\n== {f} ==")
    print(f"  file {r['file_size']} bytes, header {r['header_len']} bytes JSON, "
          f"gzip {r['gzip_len']} -> decompressed {r['decompressed_len']}")
    print(f"  seed {hdr.get('seed')}  {hdr.get('width')}x{hdr.get('height')}  "
          f"version {hdr.get('version')}  gamemode {hdr.get('gamemode')}  "
          f"money {hdr.get('money')}  habitants {hdr.get('habitants')}  id {hdr.get('id')}")
    print(f"  minimap {r['minimap_size']}  preview {r['preview_size']}  "
          f"main object at decompressed offset {r['object_offset']}")
    print(f"  scalars: {r['main_object_scalars']}")
    print(f"  taxes: {r['taxes_0_to_8']}")
    print(f"  terrain: {r['minimap_stats']['terrain_classes_pct']}")
    print(f"  ground types: {r['ground_types_from_ground_arr']}")
    print(f"  heights (reconstructed from deltas): { {k: (v['count'], v['min'], v['max']) for k, v in r['heights_arrays'].items()} }")
    print(f"  approx: {r['approx_counts_heuristic']}")
    for name in ["trees", "roads", "buildings", "rails", "bus_stops"]:
        print(f"  {name}: {r['objects'][name + '_summary']}")


def _write_report(files, out):
    lines = ["# TheoTown .city — file breakdown\n",
             "Read-only prototype parser. See the README for the format and limits.\n"]
    for f in files:
        r = analyse(f)
        hdr = r["header"]
        lines.append(f"## {f}\n")
        lines.append(f"- File size: {r['file_size']} bytes, header JSON {r['header_len']} bytes, gzip {r['gzip_len']} bytes -> {r['decompressed_len']} bytes decompressed\n")
        lines.append(f"- Seed: `{hdr.get('seed')}`, size: {hdr.get('width')}x{hdr.get('height')}, version: {hdr.get('version')}, mode: {hdr.get('gamemode')}, money: {hdr.get('money')}, habitants: {hdr.get('habitants')}, id: `{hdr.get('id')}`\n")
        lines.append(f"- Minimap: {r['minimap_size']}, preview: {r['preview_size']}, main object at decompressed offset {r['object_offset']}\n")
        lines.append(f"- Main fields (binary object): `{r['main_object_scalars']}`\n")
        lines.append(f"- Taxes 0-8: `{r['taxes_0_to_8']}`\n")
        lines.append(f"- Terrain (true colours, A,B,G,R): `{r['minimap_stats']['terrain_classes_pct']}`\n")
        lines.append(f"- Ground types from ground arr: `{r['ground_types_from_ground_arr']}`\n")
        lines.append(f"- Heights (reconstructed from deltas): `{ {k: (v['count'], v['min'], v['max']) for k, v in r['heights_arrays'].items()} }`\n")
        lines.append(f"- Approx (heuristic): `{r['approx_counts_heuristic']}`\n")
        for name in ["trees", "roads", "buildings", "rails", "bus_stops"]:
            lines.append(f"- {name}: `{r['objects'][name + '_summary']}`\n")
        lines.append("")
    Path(out).write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="TheoTown .city parser (read-only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_info = sub.add_parser("info", help="print a summary for .city files")
    p_info.add_argument("files", nargs="+")
    p_info.add_argument("--json", action="store_true")
    p_exp = sub.add_parser("export-images", help="export minimap + preview PNGs")
    p_exp.add_argument("files", nargs="+")
    p_exp.add_argument("--out", default="out")
    p_rep = sub.add_parser("report", help="write a markdown report for .city files")
    p_rep.add_argument("files", nargs="+")
    p_rep.add_argument("--out", default="report.md")
    args = ap.parse_args(argv)
    if args.cmd == "info":
        for f in args.files:
            r = analyse(f)
            if args.json:
                print(json.dumps(r, indent=2, ensure_ascii=False))
            else:
                _print_info(r, f)
    elif args.cmd == "export-images":
        for f in args.files:
            mp, pp, mpg, ppg = export_images(f, args.out)
            ov = export_overlay(f, args.out)
            print(f"{f} -> {mp}, {pp}, {mpg}, {ppg}, {ov}")
    elif args.cmd == "report":
        _write_report(args.files, args.out)


if __name__ == "__main__":
    main()
