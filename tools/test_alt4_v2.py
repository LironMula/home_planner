"""Serialized-plan regressions independent of the CAD reconstruction helpers."""

import json
import math
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


class Alt4V2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=json.loads((ROOT/'plans/architect-alt-4-v2.json').read_text(encoding='utf-8'))
        cls.audit=json.loads((ROOT/'docs/alt4-v2-layer-audit.json').read_text(encoding='utf-8'))
        cls.donor=json.loads((ROOT/'plans/architect-alt-4-sheet-1.json').read_text(encoding='utf-8'))

    def element(self,name):
        return next(e for e in self.plan['elements'] if e['name']==name)

    def test_selected_basement(self):
        self.assertEqual(self.audit['floors']['basement']['areaHandle'],'101E')

    def test_section_constraints(self):
        sections=self.audit['sections']
        self.assertEqual(sections['roof']['outerRadius'],5.86)
        self.assertEqual(sections['roof']['innerRadius'],5.66)
        self.assertEqual(sections['roof']['shellRadialThickness'],.2)
        self.assertEqual(sections['roof']['structuralCrownElevation'],9)
        self.assertEqual(sections['floorToFloor']['groundToLiving'],3.14)
        self.assertEqual(sections['clearHeights']['ground'],2.79)
        self.assertEqual(sections['topLevelDifference'],.516)
        elevations={f['id'].rsplit('-',1)[-1]:f['elevation'] for f in self.plan['floors']}
        self.assertEqual(elevations,{'basement':-2.75,'ground':0,'living':3.14,'floor2':5.724})
        stairs={s['floorId'].rsplit('-',1)[-1]:s['height'] for s in self.plan['stairs']}
        self.assertEqual(stairs,{'basement':2.75,'ground':3.14,'living':2.584})

    def test_source_wall_reconstruction(self):
        for key,audit in self.audit['floors'].items():
            self.assertLessEqual(audit['wallReconstructionDifferenceM2'],.01,key)
            self.assertGreater(audit['modelVerifiedDimensionCount'],0,key)
        for child in self.audit['floors']['living']['clearAreaChecks']:
            self.assertEqual((child['width'],child['depth']),(2.85,4.1))

    def test_ids_hosts_and_finite_dimensions(self):
        objects=[o for collection in ('walls','rooms','stairs','elements','openings') for o in self.plan[collection]]
        self.assertEqual(len(objects),len({o['id'] for o in objects}))
        walls={w['id']:w for w in self.plan['walls']}
        for o in objects:
            for k in ('x','y','w','h','width','height','rotation'):
                if k in o:
                    self.assertTrue(math.isfinite(o[k]),(o['id'],k))
        for opening in self.plan['openings']:
            host=walls[opening['wallId']]
            self.assertEqual(host['floorId'],opening['floorId'])
            self.assertAlmostEqual(host['x']+host['w']/2,opening['x'],places=3)
            self.assertAlmostEqual(host['y']+host['h']/2,opening['y'],places=3)
            self.assertAlmostEqual(host['w'],opening['width'],places=3)
            self.assertAlmostEqual(host['rotation'],opening['rotation'],places=3)

    def test_appearance_authority(self):
        donors={e['id']:e for e in self.donor['elements']}
        for element in self.plan['elements']:
            if element.get('context'):
                continue
            donor=donors[element['materialSource']]
            for field in ('color','opacity','type1','finish'):
                self.assertEqual(element.get(field),donor.get(field),(element['name'],field))
        self.assertEqual(self.element('Basement bedroom closet')['color'],'#8b6145')
        self.assertNotIn('type1',self.element('Basement bedroom closet'))

    def test_external_geometry_unchanged(self):
        external=json.loads((ROOT/'plans/ruchama-18-20-external.json').read_text(encoding='utf-8'))
        for collection in ('walls','elements'):
            generated=[e for e in self.plan[collection] if e.get('context')]
            self.assertEqual(len(generated),len(external[collection]))
            for donor in external[collection]:
                item=next(e for e in generated if e['id'].endswith('-external-'+donor['id']))
                for key,value in donor.items():
                    if key not in ('id','floorId','context'):
                        self.assertEqual(item.get(key),value,(donor['id'],key))

    def test_void_and_terrace_ownership(self):
        living=[r for r in self.plan['rooms'] if r['floorId'].endswith('-living') and not r.get('outdoor')]
        ground=[r for r in self.plan['rooms'] if r['floorId'].endswith('-ground') and not r.get('outdoor')]
        self.assertTrue(all(r.get('floorHoles') for r in living))
        self.assertTrue(all(r.get('ceilingHoles') for r in ground))
        for slab in self.plan['rooms']:
            if slab.get('outdoor'):
                self.assertFalse(slab['ceiling'])

    def test_top_enclosure_covers_east_bay_and_bridge(self):
        from shapely.geometry import Point, box
        from shapely.ops import unary_union
        top=[r for r in self.plan['rooms'] if r['floorId'].endswith('-floor2') and not r.get('outdoor')]
        roof=[r for r in self.plan['roofs'] if r['floorId'].endswith('-floor2')]
        slabs=unary_union([box(r['x'],r['y'],r['x']+r['w'],r['y']+r['h']) for r in top])
        cover=unary_union([box(r['x'],r['y'],r['x']+r['w'],r['y']+r['h']) for r in roof])
        self.assertLess(slabs.symmetric_difference(cover).area,.01)
        tx=self.audit['siteRegistration']['xTranslation']
        ty=self.audit['siteRegistration']['yTranslation']
        for source_x,source_y in ((13.9,2.8),(12,5.1),(7,7.2)):
            self.assertTrue(slabs.covers(Point(tx-source_x,ty-source_y)),(source_x,source_y))

    def test_kitchen_and_closet_assemblies(self):
        for name in ('Kitchen oven','Kitchen pantry refrigerator','Kitchen tall storage left','Kitchen tall storage right'):
            self.assertTrue(self.element(name)['sourceHandles'])
        patio=next(o for o in self.plan['openings'] if o['name']=='Kitchen exterior sliding glass door')
        self.assertEqual((patio['type'],patio['sill'],patio['openingStyle']),('door',0,'sliding'))
        west=self.element('Master walk-in closet west bank')
        east=self.element('Master walk-in closet east bank')
        self.assertEqual((east['rotation']-west['rotation'])%360,180)
        self.assertAlmostEqual(west['w'],3.25)
        self.assertAlmostEqual(east['w'],3.25)
        self.assertAlmostEqual(west['h'],.45)
        self.assertAlmostEqual(east['h'],.6)
        self.assertEqual(self.element('Living bathroom laundry closet')['applianceLayout'],'stacked')

    def test_publication_gate_is_honest(self):
        validation=self.audit['validation']
        if validation['publicationReady']:
            self.assertFalse(validation.get('pending'))
            self.assertTrue(self.plan['roofs'],'A finished import must resolve roof geometry')
        else:
            self.assertEqual(validation['status'],'draft')
            self.assertTrue(validation['pending'])


if __name__=='__main__':
    unittest.main()
