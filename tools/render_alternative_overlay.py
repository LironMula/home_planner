"""Compare reconstructed source footprints against native DXF linework."""

import argparse
import json
from pathlib import Path

import ezdxf
from ezdxf import bbox, disassemble, path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as Patch

from build_alt4_v2 import item_polygon


def render(alternative, source):
    key=f'architect-alt-{alternative}-v2'
    plan=json.loads(Path(f'plans/{key}.json').read_text())
    recipe=json.loads(Path(f'tools/alt{alternative}_v2_source.json').read_text(encoding='utf-8'))
    doc=ezdxf.readfile(source)
    output=Path(f'pdf_renders/alt{alternative}-v2')
    for floor,spec in recipe['floors'].items():
        origin=spec['origin']
        crop=spec['crop']
        fig,axes=plt.subplots(1,2,figsize=(20,9),sharex=True,sharey=True)
        for ax in axes:
            ax.set_aspect('equal')
            ax.set_xlim((crop[0]-origin[0])/100,(crop[2]-origin[0])/100)
            ax.set_ylim((origin[1]-crop[1])/100,(origin[1]-crop[3])/100)
            ax.set_facecolor('#fafafa')
        for entity in doc.modelspace():
            if entity.dxf.layer.upper() not in ('A17','A34','A16','A12','A14','A13','H','AREA'):
                continue
            if entity.dxftype() in ('TEXT','DIMENSION','MTEXT'):
                continue
            ext=bbox.extents([entity])
            if not ext.has_data or ext.extmax.x<crop[0] or ext.extmin.x>crop[2] or ext.extmax.y<crop[1] or ext.extmin.y>crop[3]:
                continue
            color='#159899' if entity.dxf.layer.upper()=='A17' else '#929292'
            for part in disassemble.recursive_decompose([entity]):
                try:
                    curves=list(path.from_hatch(part)) if part.dxftype()=='HATCH' else [path.make_path(part)]
                    for curve in curves:
                        pts=[((p.x-origin[0])/100,(origin[1]-p.y)/100) for p in curve.flattening(1)]
                        if len(pts)>1:
                            for ax in axes:
                                ax.plot(*zip(*pts),color=color,linewidth=.5)
                except (TypeError,ValueError,AttributeError):
                    continue
        for collection,color in [('walls','#d82540'),('elements','#326cc1')]:
            for obj in plan[collection]:
                if obj['floorId']!=key+'-'+floor:
                    continue
                shape=item_polygon(obj)
                axes[1].add_patch(Patch(list(shape.exterior.coords),fill=False,edgecolor=color,linewidth=1))
        for stair in plan['stairs']:
            if stair['floorId']!=key+'-'+floor:
                continue
            for rect in [*stair.get('cadRuns',[]),stair.get('cadLanding')]:
                if not rect:
                    continue
                x,y=stair['x']+rect['x']*stair['w'],stair['y']+rect['y']*stair['h']
                w,h=rect['w']*stair['w'],rect['h']*stair['h']
                axes[1].add_patch(Patch([(x,y),(x+w,y),(x+w,y+h),(x,y+h)],fill=True,facecolor='#ef8e27',alpha=.35))
        axes[0].set_title(f'Alt {alternative} {floor}: source')
        axes[1].set_title('Model overlay: red walls / blue fixtures / orange departing stairs')
        fig.tight_layout()
        fig.savefig(output/f'overlay-{floor}.png',dpi=120)
        plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alternative',type=int,required=True)
    parser.add_argument('--source',type=Path,required=True)
    args=parser.parse_args()
    render(args.alternative,args.source)
