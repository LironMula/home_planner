"""Rebuild, compare generated geometry to CAD, and render independent overlays."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf import bbox, disassemble, path
from shapely.geometry import Point
from build_alt4_v2 import Importer, FLOORS, KEY, item_polygon


def validate(source, output):
    output.mkdir(parents=True, exist_ok=True)
    importer = Importer(source)
    for spec in FLOORS:
        importer.build_floor(spec)
    importer.stairs()
    importer.apply_materials()
    importer.geometry_checks()
    report = {}
    for key, name, *_ in FLOORS:
        importer.origin, footprint = importer.source_floor[key]
        floor_id = KEY+'-'+key
        fig, axes = plt.subplots(1, 2, figsize=(22, 12))
        ax, generated = axes
        for e in importer.model:
            if e.dxf.layer.upper() not in ('AREA','A17','A34','A16','A12','A14','A13'):
                continue
            ext = bbox.extents([e])
            if not ext.has_data:
                continue
            cx, cy = importer.pt(ext.center)
            if not (-2 < cx < 19 and -2 < cy < 11):
                continue
            layer = e.dxf.layer.upper()
            color = {'AREA':'red','A17':'#007f8a','A34':'#42a344','A16':'#b521a1','A12':'#bf7d00'}.get(layer, '#9cabb9')
            for part in disassemble.recursive_decompose([e]):
                try:
                    paths = list(path.from_hatch(part)) if part.dxftype() == 'HATCH' else [path.make_path(part)]
                    for curve in paths:
                        pts = [importer.pt(p) for p in curve.flattening(.5)]
                        if len(pts)<2:
                            continue
                        xs, ys = zip(*pts)
                        ax.plot(xs,ys,color=color,lw=.7)
                except (TypeError, ValueError, AttributeError):
                    continue
        for collection in ('rooms','walls','elements'):
            for item in importer.plan[collection]:
                if item['floorId'] != floor_id:
                    continue
                poly = item_polygon(item)
                xs, ys = poly.exterior.xy
                color = item.get('color','#eeeeee')
                generated.fill(xs,ys,color=color,alpha=.5 if collection=='rooms' else .8)
                generated.plot(xs,ys,color='#444444',lw=.6)
                if collection == 'walls':
                    ax.plot(xs,ys,color='#e34444',lw=.55,ls=':')
                if collection == 'elements':
                    center = poly.centroid
                    generated.text(center.x,center.y,item['name'],fontsize=5,ha='center',wrap=True)
                    # Arrow points along the renderer's front axis.
                    import math
                    angle=math.radians(item.get('rotation',0))
                    generated.arrow(center.x,center.y,-.3*math.sin(angle),.3*math.cos(angle),head_width=.09,color='#333333')
                for hole in item.get('floorHoles',[]):
                    hx,hy=item_polygon(hole).exterior.xy
                    generated.fill(hx,hy,color='white',zorder=2)
        for opening in importer.plan['openings']:
            if opening['floorId'] != floor_id:
                continue
            import math
            angle=math.radians(opening['rotation'])
            dx,dy=opening['width']/2*math.cos(angle),opening['width']/2*math.sin(angle)
            generated.plot([opening['x']-dx,opening['x']+dx],[opening['y']-dy,opening['y']+dy],
                           color='#bb8800' if opening['type']=='door' else '#199bd5',lw=3)
        for axis in axes:
            axis.set(xlim=(-1.8,16.2),ylim=(9.6,-.6),aspect='equal')
            axis.grid(alpha=.15)
        ax.set_title(name+': CAD; generated walls dotted red')
        generated.set_title(name+': reconstructed geometry, arrows show furniture fronts')
        fig.tight_layout()
        fig.savefig(output/(key+'-overlay.png'),dpi=150)
        plt.close(fig)
        audit=importer.audit['floors'][key]
        report[key]={k:audit.get(k) for k in ('wallReconstructionDifferenceM2','modelVerifiedDimensionCount','clearAreaChecks','unresolvedDoors','unclassifiedBlocks')}
    # Pure geometric reconstruction is not a semantic or publication approval.
    (output/'geometry-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,default=Path('pdf_renders/alt4-v2'))
    args=parser.parse_args()
    validate(args.source,args.output)
