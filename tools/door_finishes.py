"""User-selected interior door finish for the audited Alt-3/4/5 v2 plans."""

import json
from pathlib import Path

INTERIOR_DOOR_COLOR = '#a89b8c'  # Warm taupe / greige.
# Source-reviewed exterior solid doors; glass openings are excluded separately.
EXTERIOR_DOORS = {
    'architect-alt-3-v2-ground-door-1870-0',
    'architect-alt-3-v2-ground-door-18CF-1',
    'architect-alt-4-v2-ground-door-21D8-0',
    'architect-alt-4-v2-ground-door-221F-1',
    'architect-alt-4-v2-ground-door-2228-0',
    'architect-alt-5-v2-basement-audited-family-court-exit',
    'architect-alt-5-v2-ground-audited-main-entry',
    'architect-alt-5-v2-ground-audited-pantry-exterior-entry',
    'architect-alt-5-v2-top-audited-west-roof-terrace-door',
    'architect-alt-5-v2-top-audited-east-service-roof-door',
}


def apply_interior_door_finish(plan):
    changed = []
    for opening in plan['openings']:
        if (opening['type'] == 'door' and not opening.get('glass')
                and opening['id'] not in EXTERIOR_DOORS):
            opening['color'] = INTERIOR_DOOR_COLOR
            changed.append(opening['id'])
    return changed


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    for alternative in (3, 4, 5):
        path = root / f'plans/architect-alt-{alternative}-v2.json'
        plan = json.loads(path.read_text(encoding='utf-8'))
        changed = apply_interior_door_finish(plan)
        path.write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
        print(f'Alt-{alternative}: {len(changed)} interior doors')
