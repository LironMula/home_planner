"""Inventory and render Alt-3/Alt-5 source evidence before reconstruction."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import ezdxf
from ezdxf import bbox, disassemble, path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from cad_text import decode_architect_text

LAYERS = {"AREA", "A17", "A34", "A24", "A49", "A16", "A12", "A14", "A13", "H", "A10", "A11"}
COLORS = {"AREA":"#ff5050", "A17":"#39c5c8", "A34":"#58db50", "A24":"#938537", "A49":"#eeeeee",
          "A16":"#b6de48", "A12":"#ffdc35", "A14":"#ddbe42", "A13":"#caaa66", "H":"#f58a8a",
          "A10":"#50b1b5", "A11":"#508f92"}


def inspect(source, output, crop=None, name="overview", handles=False):
    output.mkdir(parents=True, exist_ok=True)
    doc = ezdxf.readfile(source)
    entities = list(doc.modelspace())
    records = []
    for e in entities:
        layer = e.dxf.layer.upper()
        if layer not in LAYERS:
            continue
        ext = bbox.extents([e])
        if not ext.has_data:
            continue
        record = dict(handle=e.dxf.handle, layer=layer, type=e.dxftype(),
                      bounds=[round(v,4) for v in (ext.extmin.x,ext.extmin.y,ext.extmax.x,ext.extmax.y)])
        if e.dxftype() == "TEXT":
            record.update(text=decode_architect_text(e.dxf.text), position=list(e.dxf.insert)[:2])
        elif e.dxftype() == "DIMENSION":
            record.update(measurement=e.dxf.get("actual_measurement"), text=e.dxf.get("text"),
                          defpoint2=list(e.dxf.get("defpoint2", (0,0,0)))[:2], defpoint3=list(e.dxf.get("defpoint3",(0,0,0)))[:2])
        elif e.dxftype() == "LWPOLYLINE":
            record.update(points=[list(p) for p in e.get_points("xy")], closed=e.closed)
        elif e.dxftype() == "LINE":
            record.update(points=[list(e.dxf.start)[:2],list(e.dxf.end)[:2]])
        elif e.dxftype() == "INSERT":
            record.update(block=e.dxf.name, rotation=e.dxf.rotation, scale=[e.dxf.xscale,e.dxf.yscale])
        elif e.dxftype() == "ARC":
            record.update(center=list(e.dxf.center)[:2],radius=e.dxf.radius,start=e.dxf.start_angle,end=e.dxf.end_angle)
        elif e.dxftype() == "HATCH":
            record['paths']=[list(p.vertices) for p in e.paths if hasattr(p,'vertices')]
        records.append(record)
    report = dict(source=source.name,sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  units=doc.header.get("$INSUNITS"), layers=dict(Counter(e.dxf.layer for e in entities)),
                  layerTable=[layer.dxf.name for layer in doc.layers], entities=records)
    (output/'source-inventory.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    fig, ax = plt.subplots(figsize=(18,12),facecolor='#202930')
    ax.set_facecolor('#202930')
    by_handle={r['handle']:r for r in records}
    for e in entities:
        record=by_handle.get(e.dxf.handle)
        if not record:
            continue
        layer=record['layer']
        x1,y1,x2,y2=record['bounds']
        if crop and (x2<crop[0] or x1>crop[2] or y2<crop[1] or y1>crop[3]):
            continue
        if e.dxftype() in ('TEXT','MTEXT'):
            if crop and e.dxftype()=='TEXT':
                text=record['text']
                ax.text(e.dxf.insert.x,e.dxf.insert.y,text,fontsize=5,color=COLORS[layer],clip_on=True)
            continue
        if e.dxftype()=='DIMENSION':
            if crop:
                p=e.dxf.text_midpoint
                ax.text(p.x,p.y,f"{e.dxf.get('actual_measurement',0):g}",fontsize=5,color='#ccc7a1',clip_on=True)
            continue
        for part in disassemble.recursive_decompose([e]):
            try:
                paths=list(path.from_hatch(part)) if part.dxftype()=='HATCH' else [path.make_path(part)]
                for curve in paths:
                    pts=list(curve.flattening(1))
                    if len(pts)<2:
                        continue
                    xs,ys=[p.x for p in pts],[p.y for p in pts]
                    if layer=='A17':
                        ax.fill(xs,ys,color=COLORS[layer],alpha=.2)
                    ax.plot(xs,ys,color=COLORS[layer],linewidth=1.1 if layer=='AREA' else .5)
                if handles and layer in ('AREA','H','A17','A16','A34','A12'):
                    ax.text((x1+x2)/2,(y1+y2)/2,e.dxf.handle,fontsize=5,color='white',clip_on=True)
            except (TypeError,ValueError,AttributeError):
                continue
    if crop:
        ax.set_xlim(crop[0],crop[2]); ax.set_ylim(crop[1],crop[3])
    ax.tick_params(colors='white')
    ax.set_aspect('equal')
    ax.set_title(f'{source.stem}: {name}',color='white')
    fig.tight_layout()
    fig.savefig(output/f'{name}.png',dpi=140,facecolor=fig.get_facecolor())
    plt.close(fig)
    print(json.dumps({'source':source.name,'layers':report['layers'],
                      'wallBounds':bbox.extents([e for e in entities if e.dxf.layer.upper()=='A17']).__str__()},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--crop',type=float,nargs=4)
    parser.add_argument('--name',default='overview')
    parser.add_argument('--handles',action='store_true')
    args=parser.parse_args()
    inspect(args.source,args.output_dir,args.crop,args.name,args.handles)
