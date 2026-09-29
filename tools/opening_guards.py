"""Generate landing-edge guards from actual holes, excluding walls and stair access."""
import json
import math
from pathlib import Path

from shapely import set_precision
from shapely.affinity import rotate
from shapely.geometry import box, LineString
from shapely.ops import unary_union


def rect(item):
    return rotate(box(item['x'],item['y'],item['x']+item['w'],item['y']+item['h']),
                  item.get('rotation',0),origin='center')


def stair_geometry(stair):
    """Match stairPlanRuns/stairLandingRect, including the pre-CAD Alt-4 stairs."""
    x,y,w,h= (stair[k] for k in ('x','y','w','h'))
    if stair.get('cadRuns'):
        def scaled(r):
            return dict(r,x=x+r['x']*w,y=y+r['y']*h,w=r['w']*w,h=r['h']*h)
        runs=[scaled(r) for r in stair['cadRuns']]
        landing=scaled(stair['cadLanding'])
    else:
        size=max(.6,min(stair.get('landing',1.2),max(.6,min(w,h))))
        left=stair.get('turn')=='left'
        if stair['shape']=='uturn':
            rw=max(.35,min(size,w/2)); rh=max(.4,h-size)
            runs=[dict(x=x+w-rw if left else x,y=y,w=rw,h=rh,dir='z'),
                  dict(x=x if left else x+w-rw,y=y,w=rw,h=rh,dir='z',reverse=True)]
            landing=dict(x=x,y=y+h-size,w=w,h=size)
        elif stair['shape']=='turned':
            runs=[dict(x=x if left else x+w-size,y=y,w=size,h=max(.4,h-size),dir='z'),
                  dict(x=x+size if left else x,y=y+h-size,w=max(.4,w-size),h=size,dir='x',reverse=not left)]
            landing=dict(x=x if left else x+w-size,y=y+h-size,w=size,h=size)
        else:
            runs=[dict(x=x,y=y,w=w,h=h,dir='z')]; landing=None
    center=(x+w/2,y+h/2)
    turn=lambda shape: set_precision(rotate(shape,stair.get('rotation',0),origin=center),.0001)
    footprint=unary_union([turn(rect(r)) for r in [*runs,*([landing] if landing else [])]])
    last=runs[-1]
    if last['dir']=='x':
        end=last['x']+(0 if last.get('reverse') else last['w'])
        access=LineString([(end,last['y']),(end,last['y']+last['h'])])
    else:
        end=last['y']+(0 if last.get('reverse') else last['h'])
        access=LineString([(last['x'],end),(last['x']+last['w'],end)])
    return footprint,turn(access)


def exposed_edges(plan,floor_index):
    floor=plan['floors'][floor_index]
    rooms=[r for r in plan['rooms'] if r['floorId']==floor['id'] and not r.get('outdoor')]
    slab=unary_union([rect(r) for r in rooms])
    incoming=[s for s in plan['stairs'] if s['floorId']==plan['floors'][floor_index-1]['id']]
    stairs=[stair_geometry(s) for s in incoming]
    holes=unary_union([*[p for p,a in stairs],*[rect(h) for r in rooms for h in r.get('floorHoles',[])]])
    walls=unary_union([rect(w) for w in plan['walls'] if w['floorId']==floor['id']
                      and not w.get('openingGuard') and w.get('height',2.8)>=.9])
    access=unary_union([a.buffer(.04,cap_style=3) for p,a in stairs])
    # A departing flight must remain traversable even when it borders an incoming hole.
    outgoing=unary_union([stair_geometry(s)[0] for s in plan['stairs'] if s['floorId']==floor['id']])
    edge=holes.boundary.intersection(slab.buffer(-.002)).difference(walls.buffer(.025,join_style=2))
    edge=edge.difference(access).difference(outgoing.buffer(.025,join_style=2))
    return edge,holes,access


def segments(geometry):
    if geometry.geom_type=='LineString':
        for a,b in zip(geometry.coords,list(geometry.coords)[1:]):
            if math.dist(a,b)>.08:
                yield tuple(sorted((a,b)))
    else:
        for part in getattr(geometry,'geoms',[]):
            yield from segments(part)


def add_opening_guards(plan):
    plan['walls']=[w for w in plan['walls'] if not w.get('openingGuard')]
    for i,floor in enumerate(plan['floors']):
        if not floor['id'].endswith(('-ground','-living')) or i==0:
            continue
        edges,_,_=exposed_edges(plan,i)
        for j,(a,b) in enumerate(sorted(set(segments(edges)))):
            length=math.dist(a,b); cx=(a[0]+b[0])/2; cy=(a[1]+b[1])/2
            plan['walls'].append(dict(id=f"{floor['id']}-opening-guard-{j}",floorId=floor['id'],
                type='glass-wall',name='Opening glass guard with wood handrail',openingGuard=True,
                x=round(cx-length/2,5),y=round(cy-.015,5),w=round(length,5),h=.03,
                rotation=round(math.degrees(math.atan2(b[1]-a[1],b[0]-a[0])),5),
                height=.9,color='#b9d9dc',opacity=.28,handrailColor='#a08060',
                sourceRole='User-requested guard on exposed floor-hole edge; stair arrivals remain open'))


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    for n in (3,4,5):
        path=root/f'plans/architect-alt-{n}-v2.json'
        plan=json.loads(path.read_text(encoding='utf-8'))
        add_opening_guards(plan)
        path.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
        print(n,sum(bool(w.get('openingGuard')) for w in plan['walls']))
