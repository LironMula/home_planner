"""Inspect the two roof sections independently of the plan-layer contract."""
import argparse
import json
from pathlib import Path
import ezdxf
from ezdxf import bbox, disassemble, path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from cad_text import decode_architect_text


def inspect(source,output):
    output.mkdir(parents=True,exist_ok=True)
    doc=ezdxf.readfile(source)
    report=[]
    for name,bottom,top in (('section-upper',10500,12000),('section-lower',7900,9500)):
        fig,ax=plt.subplots(figsize=(16,11))
        section={'name':name,'curves':[],'labels':[],'layers':{}}
        for entity in doc.modelspace():
            ex=bbox.extents([entity])
            if not ex.has_data or not (bottom<ex.center.y<top and 12000<ex.center.x<14800):
                continue
            layer=entity.dxf.layer
            section['layers'][layer]=section['layers'].get(layer,0)+1
            if entity.dxftype()=='TEXT':
                section['labels'].append({'handle':entity.dxf.handle,'text':decode_architect_text(entity.dxf.text),
                                          'position':list(entity.dxf.insert)})
            if entity.dxftype()=='ARC' and entity.dxf.radius>400:
                section['curves'].append({'handle':entity.dxf.handle,'layer':layer,'center':list(entity.dxf.center),
                                         'radius':entity.dxf.radius,'start':list(entity.start_point),'end':list(entity.end_point)})
            for part in disassemble.recursive_decompose([entity]):
                try:
                    curves=list(path.from_hatch(part)) if part.dxftype()=='HATCH' else [path.make_path(part)]
                    for curve in curves:
                        points=list(curve.flattening(.5))
                        xs,ys=[p.x for p in points],[p.y for p in points]
                        color={'A10':'#18878d','A13':'#bc7600','A14':'#365dcc','A34':'#479c41'}.get(layer,'#777777')
                        if part.dxftype()=='HATCH': ax.fill(xs,ys,color=color,alpha=.2)
                        ax.plot(xs,ys,color=color,lw=.8)
                except (TypeError,ValueError,AttributeError):
                    continue
        ax.set(xlim=(12200,14400),ylim=(bottom,top),aspect='equal',title=name+': native CAD coordinates (cm)')
        ax.grid(alpha=.25)
        fig.tight_layout()
        fig.savefig(output/(name+'.png'),dpi=150)
        plt.close(fig)
        report.append(section)
    (output/'sections.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,default=Path('pdf_renders/alt4-v2'))
    args=parser.parse_args()
    inspect(args.source,args.output)
