"""Independent serialized-plan checks for the two fresh CAD alternatives."""

import json
import math
from pathlib import Path
import unittest

from shapely.geometry import box
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]


class AlternativeTests(unittest.TestCase):
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
