import copy
import json
from pathlib import Path
import unittest

from door_finishes import EXTERIOR_DOORS, INTERIOR_DOOR_COLOR, apply_interior_door_finish


class DoorFinishesTest(unittest.TestCase):
    def test_plans_and_preserved_openings(self):
        root = Path(__file__).resolve().parents[1]
        for alternative, count in ((3, 10), (4, 9), (5, 18)):
            with self.subTest(alternative=alternative):
                plan = json.loads((root / f'plans/architect-alt-{alternative}-v2.json').read_text())
                before = copy.deepcopy(plan)
                ids = apply_interior_door_finish(plan)
                self.assertEqual(len(ids), count)
                self.assertEqual(plan, before, 'Saved finishes must match the generator')
                for opening in plan['openings']:
                    if opening['id'] in ids:
                        self.assertEqual(opening['color'], INTERIOR_DOOR_COLOR)
                        self.assertFalse(opening.get('glass'))
                        self.assertNotIn(opening['id'], EXTERIOR_DOORS)
                # Recoloring must change only the selected leaf colors.
                for opening in plan['openings']:
                    opening['color'] = '#123456'
                before = copy.deepcopy(plan)
                apply_interior_door_finish(plan)
                for opening in before['openings']:
                    if opening['id'] in ids:
                        opening['color'] = INTERIOR_DOOR_COLOR
                self.assertEqual(plan, before)


if __name__ == '__main__':
    unittest.main()
