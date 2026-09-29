import copy
import json
from pathlib import Path
import unittest
from shapely.geometry import LineString
from shapely.ops import unary_union
from opening_guards import add_opening_guards, exposed_edges, rect

ROOT=Path(__file__).resolve().parents[1]


class GuardTests(unittest.TestCase):
    def test_guards(self):
        for n in (3,4,5):
            with self.subTest(alternative=n):
                plan=json.loads((ROOT/f'plans/architect-alt-{n}-v2.json').read_text())
                original=copy.deepcopy(plan)
                add_opening_guards(plan)
                self.assertEqual(plan,original,'Regeneration must be idempotent')
                for i,floor in enumerate(plan['floors']):
                    guards=[w for w in plan['walls'] if w.get('openingGuard') and w['floorId']==floor['id']]
                    if not floor['id'].endswith(('-ground','-living')):
                        self.assertFalse(guards)
                        continue
                    self.assertTrue(guards)
                    edge,holes,access=exposed_edges(plan,i)
                    shapes=[]
                    for guard in guards:
                        self.assertEqual(guard['height'],.9)
                        shape=rect(guard); shapes.append(shape)
                        self.assertLess(shape.intersection(access).area,.0001,'Do not block stair arrival')
                        self.assertLess(shape.centroid.distance(holes.boundary),.0001)
                    coverage=unary_union(shapes).buffer(.03)
                    self.assertLess(edge.difference(coverage).length,.16,'Exposed edge left unguarded')


if __name__=='__main__':
    unittest.main()
