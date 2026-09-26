"""Render the registered CAD stair/elevator cores with source-handle evidence."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf import bbox, path
from build_alt4_v2 import Importer
from cad_text import decode_architect_text


def inspect(source, output):
    importer = Importer(source)
    audit = json.loads(Path('docs/alt4-v2-layer-audit.json').read_text())
    output.mkdir(parents=True, exist_ok=True)
    records = {}
    for key, floor in audit['floors'].items():
        importer.origin = floor['originCm']
        fig, ax = plt.subplots(figsize=(13, 8))
        records[key] = []
        for entity in importer.model:
            layer = entity.dxf.layer.upper()
            if layer not in ('AREA', 'A13', 'A14', 'A17', 'A49', 'A24', 'H'):
                continue
            extent = bbox.extents([entity])
            if not extent.has_data:
                continue
            cx, cy = importer.pt(extent.center)
            if not (3.8 < cx < 12 and 4.8 < cy < 9.5):
                continue
            record = {'handle': entity.dxf.handle, 'layer': layer, 'type': entity.dxftype(),
                      'bounds': [importer.pt(extent.extmin), importer.pt(extent.extmax)]}
            color = {'AREA': '#d62828', 'A13': '#ab8a00', 'A14': '#998000',
                     'A17': '#00848b', 'A49': '#444444', 'A24': '#aaaaaa', 'H': '#e04a2b'}[layer]
            if entity.dxftype() == 'TEXT':
                record['text'] = decode_architect_text(entity.dxf.text)
                ax.text(cx, cy, record['text'], fontsize=7)
            elif entity.dxftype() in ('LINE', 'LWPOLYLINE', 'ARC'):
                points = [importer.pt(p) for p in path.make_path(entity).flattening(.5)]
                record['points'] = points
                ax.plot(*zip(*points), color=color, linewidth=1)
                if layer in ('AREA', 'A13', 'H'):
                    ax.text(cx, cy, entity.dxf.handle, color=color, fontsize=7)
            elif entity.dxftype() == 'HATCH':
                for polygon in importer.geom(entity):
                    ax.fill(*polygon.exterior.xy, color=color, alpha=.3)
                    ax.text(polygon.centroid.x, polygon.centroid.y, entity.dxf.handle, fontsize=6)
            records[key].append(record)
        ax.set(xlim=(3.8, 12), ylim=(9.5, 4.8), title=key+' source stair/elevator core', aspect='equal')
        ax.grid(alpha=.15)
        fig.tight_layout()
        fig.savefig(output/f'{key}-stair-source.png', dpi=150)
        plt.close(fig)
    (output/'stair-source.json').write_text(json.dumps(records, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=Path('pdf_renders/alt4-v2'))
    args = parser.parse_args()
    inspect(args.source, args.output)
