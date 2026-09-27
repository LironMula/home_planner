"""Independent serialized-plan checks for the two fresh CAD alternatives."""

import json
import math
import copy
from pathlib import Path
import unittest

from shapely.geometry import box
from shapely.ops import unary_union
from alternative_site import register_site, rotate_house

ROOT=Path(__file__).resolve().parents[1]


class AlternativeTests(unittest.TestCase):
    def test_shared_split_slab_holes_rotate_once(self):
        hole=dict(x=1,y=2,w=.8,h=1.2)
        slab=dict(x=0,y=0,w=4,h=5,floorHoles=[hole])
        plan={c:[] for c in ('rooms','walls','stairs','elements','roofs','boundaries','openings','rulers')}
        plan['rooms']=[dict(slab,id='a'),dict(slab,id='b')]
        rotate_house(plan,10,10)
        for room in plan['rooms']:
            self.assertEqual(room['floorHoles'],[dict(x=8.2,y=6.8,w=.8,h=1.2)])
        self.assertIsNot(plan['rooms'][0]['floorHoles'][0],plan['rooms'][1]['floorHoles'][0])

    def test_site_and_camera(self):
        donor=json.loads((ROOT/'plans/architect-alt-4-v2.json').read_text())
        exterior=json.loads((ROOT/'plans/ruchama-18-20-external.json').read_text())
        for alt in (3,5):
            with self.subTest(alternative=alt):
                key=f'architect-alt-{alt}-v2'
                plan=json.loads((ROOT/f'plans/{key}.json').read_text())
                audit=json.loads((ROOT/f'docs/alt{alt}-v2-layer-audit.json').read_text(encoding='utf-8'))
                site=plan['siteRegistration']
                tx,ty=site['xTranslation'],site['yTranslation']
                self.assertEqual(site,audit['siteRegistration'])
                self.assertEqual(site['rotationDegrees'],180)
                self.assertEqual(plan['cameraMode'],'35mm')
                snapshot=copy.deepcopy(plan)
                register_site(plan,donor,exterior)
                self.assertEqual(plan,snapshot,'Registration must not duplicate or rotate twice')
                reverse=copy.deepcopy(plan)
                rotate_house(reverse,tx,ty)
                rotate_house(reverse,tx,ty)
                self.assertEqual(reverse,plan,'All world-space geometry must round-trip together')
                ground=[r for r in plan['rooms'] if r['floorId']==key+'-ground']
                indoors=[r for r in ground if not r.get('outdoor')]
                self.assertAlmostEqual(max(r['x']+r['w'] for r in indoors),12.65)
                self.assertAlmostEqual(min(r['y'] for r in indoors),.5)
                footprint=unary_union([box(r['x'],r['y'],r['x']+r['w'],r['y']+r['h']) for r in ground])
                entrance=[o for o in plan['openings'] if o['id'] in site['entranceIds']]
                camera=plan['camera']; pos=camera['position']
                self.assertAlmostEqual(pos['x'],sum(o['x'] for o in entrance)/len(entrance))
                self.assertAlmostEqual(pos['z'],sum(o['y'] for o in entrance)/len(entrance)+4)
                self.assertEqual(pos['y'],1.6)
                self.assertAlmostEqual(camera['yaw'],math.pi)
                self.assertEqual(camera['pitch'],0)
                from shapely.geometry import Point
                self.assertFalse(footprint.contains(Point(pos['x'],pos['z'])))
                for collection in ('walls','elements'):
                    copied=[e for e in plan[collection] if e.get('context')]
                    self.assertEqual({e['sourceSiteId'] for e in copied},{e['id'] for e in exterior[collection]})
                    for source in exterior[collection]:
                        parts=[e for e in copied if e['sourceSiteId']==source['id']]
                        for part in parts:
                            self.assertEqual(part['floorId'],key+'-ground')
                            for field in ('color','opacity','height','rotation','elementKind','type1'):
                                self.assertEqual(part.get(field),source.get(field))
                        if source.get('elementKind')=='grass' and source.get('rotation',0)==0:
                            actual=unary_union([box(e['x'],e['y'],e['x']+e['w'],e['y']+e['h']) for e in parts])
                            expected=box(source['x'],source['y'],source['x']+source['w'],source['y']+source['h']).difference(footprint)
                            self.assertLess(actual.symmetric_difference(expected).area,.00001)
                        else:
                            self.assertEqual(len(parts),1)
                            delta=.55 if '-garden-' in source['id'] else 0
                            self.assertAlmostEqual(parts[0]['x'],source['x']+delta)
                            for field in ('y','w','h'):
                                self.assertEqual(parts[0][field],source[field])
                for entry in audit['stairs']:
                    stair=next(s for s in plan['stairs'] if s['floorId']==key+'-'+entry['sourceFloor'])
                    bounds=[r['bounds'] for r in entry['runs']]+[entry['landing']]
                    self.assertAlmostEqual(stair['x'],tx-max(b[2] for b in bounds),places=3)
                    self.assertAlmostEqual(stair['y'],ty-max(b[3] for b in bounds),places=3)
                    self.assertEqual(stair['rotation'],180)
                for room in plan['rooms']:
                    for field in ('floorHoles','ceilingHoles'):
                        for hole in room.get(field,[]):
                            source=next(v for v in audit['voids'] if v['role']==hole['role'])
                            source_piece=box(tx-hole['x']-hole['w'],ty-hole['y']-hole['h'],tx-hole['x'],ty-hole['y'])
                            self.assertTrue(box(*source['bounds']).buffer(.001).covers(source_piece))

    def test_saved_plans(self):
        for alt in (3,5):
            with self.subTest(alternative=alt):
                key=f'architect-alt-{alt}-v2'
                plan=json.loads((ROOT/f'plans/{key}.json').read_text())
                recipe=json.loads((ROOT/f'tools/alt{alt}_v2_source.json').read_text(encoding='utf-8'))
                audit=json.loads((ROOT/f'docs/alt{alt}-v2-layer-audit.json').read_text(encoding='utf-8'))
                self.assertEqual(len(plan['floors']),4)
                self.assertEqual([f['elevation'] for f in plan['floors']],[-2.75,0,3.14,5.724])
                all_objects=[o for c in ('floors','rooms','walls','stairs','elements','roofs','openings','boundaries') for o in plan[c]]
                self.assertEqual(len(all_objects),len({o['id'] for o in all_objects}))
                for obj in all_objects:
                    for prop in ('x','y','w','h','height','elevation','rotation'):
                        if prop in obj:
                            self.assertTrue(math.isfinite(obj[prop]),(obj['id'],prop))
                    for prop in ('w','h','height'):
                        if prop in obj:
                            self.assertGreater(obj[prop],0,(obj['id'],prop))
                walls={o['id']:o for o in plan['walls']}
                for opening in plan['openings']:
                    self.assertIn(opening['wallId'],walls)
                    wall=walls[opening['wallId']]
                    self.assertEqual(opening['floorId'],wall['floorId'])
                    self.assertAlmostEqual(wall['x']+wall['w']/2,opening['x'],places=3)
                    self.assertAlmostEqual(wall['y']+wall['h']/2,opening['y'],places=3)
                    self.assertAlmostEqual(wall['elevation'] if 'elevation' in wall else 0,opening.get('floorOffset',0),places=3)
                for floor in plan['floors']:
                    name=floor['id'].removeprefix(key+'-')
                    self.assertLess(audit['floors'][name]['wallReconstructionDifferenceM2'],.01)
                    self.assertGreater(audit['floors'][name]['modelVerifiedDimensionCount'],0)
                    if name in ('living','top'):
                        self.assertEqual(floor['finish'],'parquet')
                for room in plan['rooms']:
                    if room.get('outdoor'):
                        self.assertFalse(room['ceiling'])
                        self.assertEqual(room['surfaceColor'],'#d9dee5')
                    if room['floorId']==key+'-top':
                        self.assertFalse(room['ceiling'])
                for sink in (e for e in plan['elements'] if e['elementKind']=='sink'):
                    self.assertGreaterEqual(sink['height'],.94)
                    if not sink.get('countertopMounted'):
                        mirrors=[e for e in plan['elements'] if e.get('sourceSinkId')==sink['id']]
                        self.assertEqual(len(mirrors),1)
                        self.assertAlmostEqual(mirrors[0]['elevation']-sink.get('elevation',0),1.15,places=3)
                self.assertEqual(len(plan['stairs']),3)
                for stair in plan['stairs']:
                    self.assertIn(stair['shape'],('turned','uturn'))
                    self.assertEqual(len(stair['cadRuns']),2)
                    pieces=[*stair['cadRuns'],stair['cadLanding']]
                    shape=unary_union([box(r['x'],r['y'],r['x']+r['w'],r['y']+r['h']) for r in pieces])
                    self.assertLess(shape.area,.95,'Do not substitute a whole stair bounding box')
                self.assertEqual(len(plan['roofs']),1)
                roof=plan['roofs'][0]
                for radius in ('outerRadius','innerRadius','finishRadius'):
                    self.assertEqual(roof['circularProfile'][radius],recipe['roof'][radius])
                top=[r for r in plan['rooms'] if r['floorId']==key+'-top' and not r.get('outdoor')]
                self.assertIn(.516,{r.get('elevation',0) for r in top})
                self.assertIn(.172,{r.get('elevation',0) for r in top})
                self.assertIn(.344,{r.get('elevation',0) for r in top})
                self.assertTrue(any(e['elementKind']=='bed' for e in plan['elements'] if e['floorId']==key+'-living'))


if __name__=='__main__':
    unittest.main()
