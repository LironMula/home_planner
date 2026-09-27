"""Build separately named Alt-3/Alt-5 plans from audited native CAD recipes.

Recipes use raw CAD centimetres. The shared extractor supplies wall tiling,
wall-gap alignment, INSERT transforms, and independent dimension checks.
"""

import argparse
from collections import Counter
import copy
import hashlib
import json
import math
from pathlib import Path

import ezdxf
from ezdxf import bbox
from shapely.geometry import Point, Polygon, LineString, box
from shapely.ops import unary_union

from build_alt4_v2 import Importer, LAYERS, item_polygon, polygons, rects, rounded
from cad_text import decode_architect_text


class AlternativeImporter(Importer):
    def __init__(self, source, recipe, alternative):
        self.doc = ezdxf.readfile(source)
        self.model = list(self.doc.modelspace())
        self.recipe = recipe
        self.alternative = alternative
        self.key = f'architect-alt-{alternative}-v2'
        self.source = source
        self.material_donor = json.loads(Path('plans/architect-alt-4-v2.json').read_text(encoding='utf-8'))
        self.plan = dict(version=1, projectName=f'Architect Alt {alternative} v2',
                         source=f'Alt-{alternative} DWG; source-verified reconstruction',
                         scale=45, wallHeight=2.79, splitRatio=.5,
                         activeFloorId=f'{self.key}-ground',viewFloor='all',
                         camera=dict(position=dict(x=22,y=14,z=22),yaw=3.9,pitch=-.38),
                         view={key:1 for key in ('floor','room','spaces','walls','stairs','windows','doors','elements','roof','boundary')},
                         **{key:[] for key in ('floors','rooms','boundaries','walls','openings','stairs','elements','roofs','rulers')})
        self.audit = dict(source=source.name, sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                          layers=dict(Counter(e.dxf.layer for e in self.model)),floors={},
                          coordinateContract='CAD centimetres to metres; common house X and registered per-sheet Y; Y inverted; no house-only rotation',
                          contourAuthority='User authorized A17 enclosures and A14/A13/H stair evidence where AREA is absent',
                          materialAuthority='Current Alt-4 v2 and subsequent user finish preferences')
        self.source_floor = {}
        self.wall_geometry = {}
        self.floor_specs = recipe['floors']

    def raw_polygon(self, points):
        return Polygon([self.pt(p) for p in points]).buffer(0)

    def raw_bounds(self, bounds):
        a,b=self.pt(bounds[:2]),self.pt(bounds[2:])
        return min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1])

    def geometry(self, spec):
        if isinstance(spec,list):
            return self.raw_polygon(spec)
        if 'points' in spec:
            return self.raw_polygon(spec['points'])
        if 'bounds' in spec:
            return box(*self.raw_bounds(spec['bounds']))
        if 'handle' in spec:
            return unary_union(self.geom(self.doc.entitydb[spec['handle']]))
        return unary_union([self.geometry(p) for p in spec['parts']])

    def slab(self, geometry, name, handle, outdoor=False, elevation=0):
        for index,bounds in enumerate(rects(geometry)):
            values=dict(structuralSlab=True,ceiling=not outdoor and self.floor_key!='top',outdoor=outdoor,
                        color='#d9dee5',opacity=.94,elevation=elevation,sourceLayer='A14/A17' if outdoor else 'AREA/A17',sourceHandle=handle)
            if outdoor:
                values['surfaceColor']='#d9dee5'
            self.item('rooms',f'{handle}-slab-{index}',name,bounds,**values)

    def window_boundary_support(self, segment, thickness):
        boundary=self.source_floor[self.floor_key][1].boundary
        return segment.intersection(boundary.buffer(thickness+.025)).length>=segment.length*.9

    def build_floor(self, key, spec):
        self.origin=spec['origin']
        self.floor_key,self.floor_id=key,f'{self.key}-{key}'
        self.height=spec.get('clearHeight',2.79)
        footprint=self.geometry(spec['enclosure'])
        self.source_floor[key]=(self.origin,footprint)
        self.floor_audit=dict(originCm=self.origin,enclosureAreaM2=rounded(footprint.area),dimensions=[],openingGaps=[])
        self.audit['floors'][key]=self.floor_audit
        self.plan['floors'].append(dict(id=self.floor_id,name=spec.get('name',key.title()),
                                       elevation=spec['elevation'],clearHeight=self.height,color={'basement':'#7c3aed','ground':'#0f766e','living':'#2563eb','top':'#b45309'}[key],
                                       finish='parquet' if key in ('living','top') else 'light-gray-granite' if key=='ground' else None))
        crop=box(*spec['crop'])
        self.entities=[]
        for e in self.model:
            if e.dxf.layer.upper() not in LAYERS:
                continue
            ext=bbox.extents([e])
            if ext.has_data and crop.covers(Point(ext.center.x,ext.center.y)):
                self.entities.append(e)
        self.floor_audit['labels']=[dict(handle=e.dxf.handle,text=decode_architect_text(e.dxf.text),position=self.pt(e.dxf.insert))
                                    for e in self.entities if e.dxftype()=='TEXT' and e.dxf.layer.upper()=='A49']
        x1,y1,x2,y2=footprint.bounds
        self.item('boundaries','boundary',spec.get('name',key.title())+' extent',(x1-1,y1-1,x2+1,y2+1),
                  type='boundary',color='#94a3b8',opacity=.1)
        self.slab(footprint,spec.get('name',key.title())+' floor','enclosure')
        terrace_geometry=[]
        for index,terrace in enumerate(spec.get('terraces',[])):
            shape=self.geometry(terrace).difference(footprint)
            terrace_geometry.append(shape)
            self.slab(shape,terrace.get('name','Terrace'),f'terrace-{index}',True,terrace.get('localElevation',0))
        self.floor_audit['terraceAreaM2']=rounded(sum(p.area for p in terrace_geometry))
        hatch_polys=[]
        for e in self.entities:
            if e.dxf.layer.upper()!='A17' or e.dxftype()!='HATCH' or e.dxf.handle in spec.get('excludeWallHandles',[]):
                continue
            for source_shape in self.geom(e):
              for p in polygons(source_shape.intersection(footprint)):
                if p.area<.003:
                    continue
                hatch_polys.append(p)
                for i,bounds in enumerate(rects(p)):
                    if min(bounds[2]-bounds[0],bounds[3]-bounds[1])<.035:
                        continue
                    self.item('walls',f'hatch-{e.dxf.handle}-{i}',f'Wall {e.dxf.handle}',bounds,
                              rotation=0,height=spec.get('wallHeights',{}).get(e.dxf.handle,self.height),
                              color='#fefdfa',opacity=1,sourceLayer='A17',sourceHandle=e.dxf.handle)
        walls=unary_union(hatch_polys)
        self.wall_geometry[key]=walls
        self.aligned_openings(walls)
        self.extra_openings(spec)
        self.furniture(footprint)
        self.dimensions()
        self.floor_audit['counts']={c:sum(v.get('floorId')==self.floor_id for v in self.plan[c]) for c in ('walls','openings','elements','rooms')}

    def extra_openings(self, spec):
        for opening in spec.get('openings',[]):
            start,end=[self.pt(p) for p in opening['endpoints']]
            mid=Point((start[0]+end[0])/2,(start[1]+end[1])/2)
            for existing in list(self.plan['openings']):
                if existing['floorId']==self.floor_id and mid.distance(Point(existing['x'],existing['y']))<.25:
                    self.plan['openings'].remove(existing)
                    self.plan['walls']=[w for w in self.plan['walls'] if w['id']!=existing['wallId']]
            values={k:v for k,v in opening.items() if k not in ('endpoints','handle','kind','thickness')}
            self.opening(opening['handle'],start,end,opening.get('kind','window'),'A14/A17 source-reviewed',
                         thickness=opening.get('thickness',.25),**values)

    def verified_furniture(self):
        spec=self.floor_specs[self.floor_key]
        for entry in [*spec.get('fixtures',[]),*spec.get('nativeFixtureCandidates',[])]:
            handles=entry.get('handles',[])
            replaced=set(entry.get('replaces',handles))
            self.plan['elements']=[e for e in self.plan['elements'] if e['floorId']!=self.floor_id or e.get('sourceHandle') not in replaced]
            bounds=self.raw_bounds(entry['bounds']) if 'bounds' in entry else None
            values={k:v for k,v in entry.items() if k not in ('name','kind','handles','bounds','rotation','replaces')}
            overrides={k:values.pop(k) for k in ('height','elevation') if k in values}
            fixture=self.fixture(entry['name'],entry['kind'],handles,entry.get('rotation',0),bounds,**values)
            fixture.update(overrides)

    def apply_materials(self):
        donors=self.material_donor['elements']
        preferred={'kitchen-work-surface':'Kitchen work surface','kitchen-island':'Kitchen island',
                   'closet':'Bedroom 1 closet','open-closet':'Master walk-in closet east bank',
                   'table':'Dining table','study-desk':'Bedroom 1 study desk','shower':'Floor 2 shower'}
        for item in self.plan['elements']:
            role=item.get('materialRole',preferred.get(item['elementKind']))
            donor=next((d for d in donors if d['name']==role),None)
            if donor is None:
                donor=next((d for d in donors if d['elementKind']==item['elementKind']),None)
            if donor is None:
                raise ValueError(f'Missing material profile: {item["elementKind"]}')
            item.update({k:donor[k] for k in ('color','opacity','type1','finish') if k in donor})
            item['materialSource']=donor['id']
            if item['elementKind']=='television':
                item['elevation']=.9
            if item['elementKind']=='sink':
                item['height']=.94 if item.get('countertopMounted') else .98
            if item['elementKind'] in ('closet','open-closet'):
                item['cabinetLayout']='solid'
        self.add_bathroom_mirrors()

    def add_bathroom_mirrors(self):
        for sink in list(self.plan['elements']):
            if sink['elementKind']!='sink' or sink.get('countertopMounted'):
                continue
            angle=math.radians(sink.get('rotation',0))
            forward=(-math.sin(angle),math.cos(angle))
            cx=sink['x']+sink['w']/2-forward[0]*(sink['h']/2-.02)
            cy=sink['y']+sink['h']/2-forward[1]*(sink['h']/2-.02)
            width=min(sink['w'],1.4)
            self.plan['elements'].append(dict(id=sink['id']+'-mirror',type='element',floorId=sink['floorId'],
                name=sink['name']+' mirror',elementKind='mirror',x=rounded(cx-width/2),y=rounded(cy-.015),w=width,h=.03,
                rotation=sink.get('rotation',0),elevation=1.15,height=.9,color='#b9d5df',opacity=1,
                sourceRole='Mirror above bathroom basin; user preference',sourceSinkId=sink['id']))

    def vertical_geometry(self):
        spec=self.floor_specs['top']
        if not spec.get('slabZones'):
            return
        self.origin=self.source_floor['top'][0]
        zones=[(self.geometry(z),z['localElevation']) for z in spec['slabZones']]
        top_id=self.key+'-top'
        living_id=self.key+'-living'
        top_elevation=spec['elevation']
        living_elevation=self.floor_specs['living']['elevation']
        upper_offset=max(offset for _,offset in zones)
        lower=unary_union([shape for shape,offset in zones if offset<upper_offset])

        def split_item(item, regions, default_values):
            shape=item_polygon(item)
            parts=[]
            for region,values in regions:
                intersection=shape.intersection(region)
                if intersection.area>.00001:
                    parts.append((intersection,values))
                    shape=shape.difference(region)
            if shape.area>.00001:
                parts.append((shape,default_values))
            result=[]
            for shape,values in parts:
                for bounds in rects(shape):
                    x,y,x2,y2=bounds
                    result.append(dict(item,id=item['id']+f'-zone-{len(result)}',x=rounded(x),y=rounded(y),
                                       w=rounded(x2-x),h=rounded(y2-y),rotation=0,**values))
            return result

        rooms=[]
        for room in self.plan['rooms']:
            if room['floorId']==top_id and not room.get('outdoor'):
                regions=[(shape,{'elevation':offset}) for shape,offset in zones]
                rooms.extend(split_item(room,regions,{'elevation':0}))
            elif room['floorId']==living_id and not room.get('outdoor'):
                def ceiling(offset):
                    level=top_elevation+offset
                    return dict(ceilingElevation=level,clearHeight=rounded(level-living_elevation-.35))
                rooms.extend(split_item(room,[(lower,ceiling(0))],ceiling(upper_offset)))
            else:
                rooms.append(room)
        self.plan['rooms']=rooms

        def local_offset(item):
            point=Point(item['x']+item.get('w',0)/2,item['y']+item.get('h',0)/2)
            return max((offset for shape,offset in zones if shape.buffer(.001).covers(point)),default=0)

        walls=[]
        for wall in self.plan['walls']:
            if wall['floorId']==top_id:
                # Full-height wall tops are clipped by the registered circular roof.
                crown=self.recipe['roof']['centerElevation']+self.recipe['roof']['innerRadius']
                if wall.get('sourceRole')=='gap-host':
                    offset=local_offset(wall)
                    wall.update(elevation=offset,height=rounded(crown-top_elevation-offset))
                    walls.append(wall)
                else:
                    regions=[(shape,dict(elevation=offset,height=rounded(crown-top_elevation-offset))) for shape,offset in zones]
                    walls.extend(split_item(wall,regions,dict(elevation=0,height=rounded(crown-top_elevation))))
            elif wall['floorId']==living_id:
                low=rounded(top_elevation-living_elevation-.35)
                high=rounded(top_elevation+upper_offset-living_elevation-.35)
                if wall.get('sourceRole')=='gap-host':
                    point=item_polygon(wall).centroid
                    wall['height']=low if lower.covers(point) else high
                    walls.append(wall)
                else:
                    walls.extend(split_item(wall,[(lower,{'height':low})],{'height':high}))
            else:
                walls.append(wall)
        self.plan['walls']=walls
        for opening in self.plan['openings']:
            if opening['floorId']==top_id:
                opening['floorOffset']=local_offset(opening)
        for element in self.plan['elements']:
            if element['floorId']==top_id:
                # Explicit localElevation is a CAD floor datum, not furniture mounting height.
                offset=element.get('localElevation',local_offset(element))
                base=.9 if element['elementKind']=='television' else 1.15 if element['elementKind']=='mirror' else 0
                element['elevation']=rounded(base+offset)
        local=self.recipe.get('localStairs',[])
        flights=local if isinstance(local,list) else [local]
        for index,step in enumerate(step for flight in flights for step in flight.get('steps',[])):
            if not step.get('treadBounds'):
                continue
            self.floor_key,self.floor_id='top',top_id
            self.slab(box(*self.raw_bounds(step['treadBounds'])),'Upper split-level step',f'local-step-{index}',
                      elevation=step['topLocalElevationM'])
        self.audit['splitLevels']=dict(zones=spec['slabZones'],steps=local,
                                      lowerElevation=top_elevation,upperElevation=top_elevation+upper_offset)

    def stair(self, entry):
        key=entry['sourceFloor']; self.origin=self.source_floor[key][0]
        runs=[]
        for run in entry['runs']:
            bounds=self.raw_bounds(run['bounds'])
            start,end=self.pt(run['start']),self.pt(run['end'])
            direction='x' if abs(end[0]-start[0])>abs(end[1]-start[1]) else 'z'
            reverse=end[0]<start[0] if direction=='x' else end[1]<start[1]
            runs.append(dict(bounds=bounds,dir=direction,reverse=reverse))
        landing=self.raw_bounds(entry['landing'])
        footprint=unary_union([box(*r['bounds']) for r in runs]+[box(*landing)])
        x1,y1,x2,y2=footprint.bounds
        w,h=x2-x1,y2-y1
        def relative(bounds):
            a,b,c,d=bounds
            return dict(x=round((a-x1)/w,8),y=round((b-y1)/h,8),w=round((c-a)/w,8),h=round((d-b)/h,8))
        self.plan['stairs'].append(dict(id=f'{self.key}-{key}-stair',type='stair',floorId=f'{self.key}-{key}',
            name=f'{self.floor_specs[key].get("name",key)} stairs',x=rounded(x1),y=rounded(y1),w=rounded(w),h=rounded(h),
            shape={'U':'uturn','L':'turned'}.get(entry.get('shape'),entry.get('shape','turned')),turn='right',landing=rounded(min(landing[2]-landing[0],landing[3]-landing[1])),
            rotation=0,level=0,height=rounded(self.floor_specs[entry['targetFloor']]['elevation']-self.floor_specs[key]['elevation']),
            color='#3d2418',opacity=1,type1='dark-wood',sourceLayer='A14/A13/H',sourceHandles=entry.get('handles',[]),
            cadRuns=[dict(**relative(r['bounds']),dir=r['dir'],reverse=r['reverse']) for r in runs],
            cadLanding=relative(landing)))
        self.audit.setdefault('stairs',[]).append(dict(sourceFloor=key,targetFloor=entry['targetFloor'],
            runs=runs,landing=landing,footprintAreaM2=rounded(footprint.area),sourceHandles=entry.get('handles',[])))

    def voids(self):
        for spec in self.recipe.get('voids',[]):
            self.origin=self.source_floor[spec['coordinateFloor']][0]
            shape=self.geometry(spec)
            holes=[dict(x=x1,y=y1,w=rounded(x2-x1),h=rounded(y2-y1),role=spec['role'],sourceHandles=spec.get('handles',[]))
                   for x1,y1,x2,y2 in rects(shape)]
            for room in self.plan['rooms']:
                if room.get('outdoor'):
                    continue
                key=room['floorId'].removeprefix(self.key+'-')
                if key in spec.get('floorHoles',[]):
                    room.setdefault('floorHoles',[]).extend(copy.deepcopy(holes))
                if key in spec.get('ceilingHoles',[]):
                    room.setdefault('ceilingHoles',[]).extend(copy.deepcopy(holes))
            self.audit.setdefault('voids',[]).append(dict(role=spec['role'],bounds=shape.bounds,areaM2=shape.area,
                floorHoles=spec.get('floorHoles',[]),ceilingHoles=spec.get('ceilingHoles',[]),handles=spec.get('handles',[])))

    def roof(self):
        spec=self.recipe['roof']
        if spec.get('ridgeX') is None:
            self.audit['roof']=dict(spec,pending=True)
            return
        self.floor_key,self.floor_id='top',self.key+'-top'
        self.origin=self.source_floor['top'][0]
        enclosure=self.source_floor['top'][1]
        footprint=enclosure.buffer(.1,join_style=2)
        profile={k:spec[k] for k in ('outerRadius','innerRadius','finishRadius','centerElevation')}
        profile['centerX']=self.pt([spec['ridgeX'],self.origin[1]])[0]
        roof=self.item('roofs','circular-roof','Circular tiled roof',footprint.bounds,type='roof',shape='barrel',axis='z',
                       circularProfile=profile,color='#ad5636',opacity=.9,sourceLayer='Section/A17',sourceHandles=spec.get('handles',[]))
        roof['surfaceRects']=[dict(x=x1,y=y1,w=rounded(x2-x1),h=rounded(y2-y1)) for x1,y1,x2,y2 in rects(footprint)]
        self.audit['roof']=dict(spec,footprintAreaM2=rounded(footprint.area),overhangM=.1)

    def fit_roof_openings(self):
        if not self.plan['roofs']:
            return
        profile=self.plan['roofs'][0]['circularProfile']
        for opening in self.plan['openings']:
            if opening['floorId']!=self.key+'-top':
                continue
            dx=math.cos(math.radians(opening.get('rotation',0)))*opening['width']/2
            clearances=[]
            for x in (opening['x']-dx,opening['x']+dx):
                rise=math.sqrt(max(0,profile['innerRadius']**2-(x-profile['centerX'])**2))
                clearances.append(profile['centerElevation']+rise-self.floor_specs['top']['elevation']-opening.get('floorOffset',0))
            maximum=min(clearances)-.04-opening.get('sill',0)
            if maximum<opening['height']:
                opening['height']=rounded(max(.3,maximum))
                opening['heightEvidence']='Inferred opening head limited by section-registered roof underside'
        roof_area=unary_union([box(r['x'],r['y'],r['x']+r['w'],r['y']+r['h']) for r in self.plan['roofs'][0]['surfaceRects']])
        for element in self.plan['elements']:
            if element['floorId']!=self.key+'-top' or element['elementKind'] not in ('closet','open-closet','shower','mirror','refrigerator'):
                continue
            footprint=item_polygon(element)
            if not roof_area.covers(footprint.centroid):
                continue
            headroom=min(profile['centerElevation']+math.sqrt(max(0,profile['innerRadius']**2-(x-profile['centerX'])**2))
                         for x in (footprint.bounds[0],footprint.bounds[2]))-self.floor_specs['top']['elevation']-element.get('elevation',0)-.03
            if element['height']>headroom:
                element['height']=rounded(max(.2,headroom))
                element['heightEvidence']='Undimensioned tall fixture limited by section-registered roof underside'

    def validate(self):
        ids=[item['id'] for col in ('floors','rooms','walls','openings','stairs','elements','roofs','boundaries') for item in self.plan[col]]
        assert len(ids)==len(set(ids)), 'Duplicate object IDs'
        for key,audit in self.audit['floors'].items():
            walls=unary_union([item_polygon(w) for w in self.plan['walls'] if w['floorId']==self.key+'-'+key and w.get('sourceLayer')=='A17'])
            error=walls.symmetric_difference(self.wall_geometry[key]).area
            audit['wallReconstructionDifferenceM2']=rounded(error)
            assert error<.01, f'{key}: wall tiling changed source geometry'
            for dimension in audit['dimensions']:
                offsets=[rounded(walls.boundary.distance(Point(p))) for p in dimension['endpoints']]
                dimension['generatedWallFaceOffsets']=offsets
                dimension['modelVerified']=max(offsets)<.015 and dimension['difference']<.01
            audit['modelVerifiedDimensionCount']=sum(d['modelVerified'] for d in audit['dimensions'])
        for col in ('rooms','walls','stairs','elements','roofs'):
            assert all(e['w']>0 and e['h']>0 for e in self.plan[col]), f'{col}: invalid dimensions'
        self.audit['validation']=dict(generatorChecksPassed=True,publicationReady=False,
                                      pending=['Source overlay and browser review'])

    def run(self):
        for key,spec in self.floor_specs.items():
            self.build_floor(key,spec)
        for entry in self.recipe['stairs']:
            self.stair(entry)
        self.voids()
        self.roof()
        self.apply_materials()
        self.vertical_geometry()
        self.fit_roof_openings()
        self.validate()
        for key,audit in self.audit['floors'].items():
            audit['counts']={c:sum(v.get('floorId')==self.key+'-'+key for v in self.plan[c]) for c in ('walls','openings','elements','rooms')}
        self.audit['sourceRecipe']=f'tools/alt{self.alternative}_v2_source.json'
        self.audit['sourceRecipeSha256']=hashlib.sha256(json.dumps(self.recipe,sort_keys=True).encode()).hexdigest()
        self.plan['importAudit']=f'docs/alt{self.alternative}-v2-layer-audit.json'
        Path(f'plans/{self.key}.json').write_text(json.dumps(self.plan,indent=2)+'\n',encoding='utf-8')
        Path(self.plan['importAudit']).write_text(json.dumps(self.audit,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        return self.plan


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alternative',type=int,choices=[3,5],required=True)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--recipe',type=Path)
    args=parser.parse_args()
    recipe=json.loads((args.recipe or Path(f'tools/alt{args.alternative}_v2_source.json')).read_text(encoding='utf-8'))
    importer=AlternativeImporter(args.source,recipe,args.alternative)
    importer.run()
    print(json.dumps({key:value['counts'] for key,value in importer.audit['floors'].items()},indent=2))
