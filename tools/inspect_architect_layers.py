"""Inspect effective CAD layers and render source-floor evidence before importing."""

import argparse
from collections import Counter
import json
from pathlib import Path

import ezdxf
from ezdxf import bbox, disassemble, path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from cad_text import decode_architect_text

LAYERS = ("AREA", "A17", "A34", "A24", "A49", "A16", "A12", "A14", "A13")
COLORS = dict(zip(LAYERS, ("#d62728", "#009ba4", "#2b9a38", "#96833e", "#777777", "#a322ae", "#dc9400", "#376fd0", "#ea7800")))


def inspect(source, output):
    output.mkdir(parents=True, exist_ok=True)
    doc = ezdxf.readfile(source)
    model = doc.modelspace()
    report = {"source": source.name, "units": doc.header.get("$INSUNITS"), "layers": {}}
    for layer in LAYERS:
        entities = [e for e in model if e.dxf.layer.upper() == layer]
        bounds = bbox.extents(entities)
        report["layers"][layer] = {
            "count": len(entities), "types": dict(Counter(e.dxftype() for e in entities)),
            "bounds": [list(bounds.extmin), list(bounds.extmax)] if bounds.has_data else None,
        }
    report["areaContours"] = [{"handle": e.dxf.handle, "closed": e.closed, "points": [[round(float(x), 4), round(float(y), 4)] for x, y in e.get_points("xy")]} for e in model.query('LWPOLYLINE[layer=="AREA"]')]
    report["labels"] = [{"handle": e.dxf.handle, "layer": e.dxf.layer, "text": decode_architect_text(e.dxf.text),
                         "position": list(e.dxf.insert)} for e in model.query('TEXT[layer=="A49"]')]
    (output / "layer-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    for ax, name in zip(axes.flat, ("SS01", "HARSA506", "WASH", "BLMLT", "BED", "CH", "SOFA-60", "sofa-crn")):
        block = doc.blocks.get(name)
        if block:
            for entity in disassemble.recursive_decompose(block):
                try:
                    points = list(path.make_path(entity).flattening(.1))
                    ax.plot([p.x for p in points], [p.y for p in points], linewidth=.7)
                except (TypeError, ValueError, AttributeError):
                    continue
        ax.set_title(name)
        ax.set_aspect("equal")
        ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(output / "blocks.png", dpi=125)
    plt.close(fig)
    # These bounds only select source drawing sheets; they do not position imported objects.
    sheets = {"basement-detailed": (-5000, -3950), "basement-area": (-2550, -1500), "ground": (-100, 1050), "living": (2800, 3950), "floor2": (5300, 6550)}
    for name, (bottom, top) in sheets.items():
        fig, ax = plt.subplots(figsize=(16, 11))
        for e in model:
            layer = e.dxf.layer.upper()
            if layer not in LAYERS:
                continue
            ext = bbox.extents([e])
            if not ext.has_data or ext.extmax.y < bottom or ext.extmin.y > top or ext.extmax.x < 12600 or ext.extmin.x > 14550:
                continue
            if e.dxftype() == "DIMENSION":
                p = e.dxf.text_midpoint
                value = e.dxf.get("actual_measurement", 0)
                ax.text(p.x, p.y, f"{value:g}", fontsize=5, color=COLORS[layer])
                continue
            if e.dxftype() in ("TEXT", "MTEXT"):
                continue
            for part in disassemble.recursive_decompose([e]):
                try:
                    paths = list(path.from_hatch(part)) if part.dxftype() == "HATCH" else [path.make_path(part)]
                    for p in paths:
                        pts = list(p.flattening(1))
                        if len(pts) < 2:
                            continue
                        xs, ys = [v.x for v in pts], [v.y for v in pts]
                        if layer == "A17":
                            ax.fill(xs, ys, color=COLORS[layer], alpha=0.25)
                        ax.plot(xs, ys, color=COLORS[layer], linewidth=1.4 if layer == "AREA" else 0.65)
                    if layer == "AREA" and part.dxftype() == "LWPOLYLINE":
                        center = bbox.extents([part]).center
                        ax.text(center.x, center.y, e.dxf.handle, color=COLORS[layer], fontsize=8)
                except (TypeError, ValueError, AttributeError):
                    continue
        ax.set(xlim=(12600, 14550), ylim=(bottom, top), title=f"Alt-4 {name}: AREA red, A17 cyan, A34 green, A14 blue, A13 stairs orange, A16 magenta")
        ax.set_aspect("equal")
        fig.tight_layout()
        fig.savefig(output / f"{name}.png", dpi=150)
        plt.close(fig)
    print(json.dumps(report["layers"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("pdf_renders/alt4-v2"))
    args = parser.parse_args()
    inspect(args.source, args.output_dir)
