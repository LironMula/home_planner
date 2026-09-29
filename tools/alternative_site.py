"""Place audited alternatives in the saved Alt-4 site without changing house dimensions."""

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'plans/ruchama-18-20-external.json'
DONOR = ROOT / 'plans/architect-alt-4-v2.json'
RECT_COLLECTIONS = ('rooms', 'walls', 'stairs', 'elements', 'roofs', 'boundaries')


def rotate_house(plan, tx, ty):
    """The half-turn is its own inverse. Nested holes/profile coordinates are world-space."""
    def rect(item):
        item['x'] = round(tx - item['x'] - item['w'], 6)
        item['y'] = round(ty - item['y'] - item['h'], 6)

    for collection in RECT_COLLECTIONS:
        # Split-level slabs can share nested hole dictionaries before JSON serialization.
        # Detach every object before mutating any of them, so each hole turns exactly once.
        plan[collection] = [copy.deepcopy(item) for item in plan[collection]]
        for item in plan[collection]:
            if item.get('context'):
                continue
            rect(item)
            if 'rotation' in item or collection in ('walls', 'stairs', 'elements'):
                item['rotation'] = round((item.get('rotation', 0) + 180) % 360, 6)
            for field in ('surfaceRects', 'floorHoles', 'ceilingHoles'):
                for piece in item.get(field, []):
                    rect(piece)
            if item.get('circularProfile'):
                profile = item['circularProfile']
                profile['centerX'] = round(tx - profile['centerX'], 6)
            if 'frontPlanner' in item:
                item['frontPlanner'] = [-value for value in item['frontPlanner']]
            # cadRuns/cadLanding are stair-local: the parent rotation carries them.
    for opening in plan['openings']:
        opening['x'] = round(tx - opening['x'], 6)
        opening['y'] = round(ty - opening['y'], 6)
        opening['rotation'] = round((opening.get('rotation', 0) + 180) % 360, 6)
    assert not plan.get('rulers'), 'Add ruler endpoint transforms before importing rulers'


def intersects(a, b):
    return (min(a['x'] + a['w'], b['x'] + b['w']) - max(a['x'], b['x']) > .001 and
            min(a['y'] + a['h'], b['y'] + b['h']) - max(a['y'], b['y']) > .001)


def subtract_rect(rect, hole):
    if not intersects(rect, hole):
        return [rect]
    x, y, right, bottom = rect['x'], rect['y'], rect['x'] + rect['w'], rect['y'] + rect['h']
    left, top = max(x, hole['x']), max(y, hole['y'])
    hr, hb = min(right, hole['x'] + hole['w']), min(bottom, hole['y'] + hole['h'])
    return [dict(x=round(a, 3), y=round(b, 3), w=round(c-a, 3), h=round(d-b, 3))
            for a, b, c, d in [(x,y,left,bottom), (hr,y,right,bottom),
                                (left,y,hr,top), (left,hb,hr,bottom)] if c-a > .001 and d-b > .001]


def register_site(plan, donor, external):
    if plan.get('siteRegistration'):
        return plan['siteRegistration']
    ground = next(f['id'] for f in plan['floors'] if f['id'].endswith('-ground'))
    key = ground.removesuffix('-ground')
    source = [r for r in plan['rooms'] if r['floorId'] == ground and not r.get('outdoor')]
    target = [r for r in donor['rooms'] if r['floorId'].endswith('-ground') and not r.get('outdoor')]
    # Match Alt-4's garden-side facade and rear property-line setback, not its room sizes.
    tx = max(r['x'] + r['w'] for r in target) + min(r['x'] for r in source)
    ty = min(r['y'] for r in target) + max(r['y'] + r['h'] for r in source)
    rotate_house(plan, tx, ty)
    surfaces = [r for r in plan['rooms'] if r['floorId'] == ground]
    indoor = [r for r in surfaces if not r.get('outdoor')]
    entrances = [o for o in plan['openings'] if o['floorId'] == ground and
                 o['name'] in ('Entrance paired leaf', 'Main house entrance')]
    assert entrances, 'Identify the source-backed main entrance before placing the camera'
    adjustments = []
    garden = [e for e in external['elements'] if '-garden-' in e['id']]
    garden_dx = 0
    if any(intersects(e, r) for e in garden for r in indoor):
        garden_dx = round(max(r['x'] + r['w'] for r in indoor) + .15 - min(e['x'] for e in garden), 3)
        adjustments.append(dict(role='garden dining assembly', xTranslation=garden_dx,
                                reason='Keep all seven pieces together, clear of the house facade'))
    for collection in ('walls', 'elements'):
        for source_item in external[collection]:
            item = copy.deepcopy(source_item)
            item.update(id=key+'-external-'+source_item['id'], floorId=ground, context=True,
                        sourceSiteId=source_item['id'])
            if item.get('groupId'):
                item['groupId'] = key+'-external-'+item['groupId']
            if '-garden-' in source_item['id']:
                item['x'] = round(item['x'] + garden_dx, 3)
            pieces = [{field:item[field] for field in ('x','y','w','h')}]
            if item.get('elementKind') == 'grass' and item.get('rotation', 0) == 0:
                for surface in surfaces:
                    pieces = [part for piece in pieces for part in subtract_rect(piece, surface)]
                if pieces != [{field:item[field] for field in ('x','y','w','h')}]:
                    adjustments.append(dict(sourceId=source_item['id'], role='lawn',
                                            reason='Trim only where house slabs or terraces replace grass'))
            for index, piece in enumerate(pieces):
                part = dict(item, **piece)
                if len(pieces) > 1:
                    part['id'] += f'-part-{index}'
                plan[collection].append(part)
    boundary = next(b for b in plan['boundaries'] if b['floorId'] == ground)
    boundary.update({field:external['boundaries'][0][field] for field in ('x','y','w','h')})
    door_x = sum(o['x'] for o in entrances) / len(entrances)
    door_y = sum(o['y'] for o in entrances) / len(entrances)
    plan['camera'] = dict(position=dict(x=round(door_x,3), y=1.6, z=round(door_y+4,3)), yaw=math.pi, pitch=0)
    plan.pop('cameraMode', None)
    plan.update(activeFloorId=ground, viewFloor='all')
    registration = dict(rotationDegrees=180, xTranslation=round(tx,3), yTranslation=round(ty,3),
        anchors='Alt-4 garden-side facade X and rear setback Y; source front entrance now faces the approach',
        exteriorSave='plans/ruchama-18-20-external.json',
        exteriorSha256=hashlib.sha256(SITE.read_bytes()).hexdigest(),
        adjustments=adjustments, entranceIds=[o['id'] for o in entrances],
        defaultCamera='1.6 m eye height, 4 m outside the front entrance, looking straight at it; lens uses the system preference')
    plan['siteRegistration'] = registration
    return registration


def record_registration(audit, registration):
    audit['siteRegistration'] = copy.deepcopy(registration)
    audit['coordinateContract'] = ('CAD centimetres to registered source metres with Y inverted; '
        'then whole-house 180-degree site placement. Floor/dimension/stair/void audit coordinates remain '
        'in source metres; serialized plan geometry is in final site metres.')
    audit['validation'] = dict(generatorChecksPassed=True, publicationReady=False,
                               pending=['Site registration and browser review'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('alternatives', nargs='+', type=int, choices=[3,5])
    args = parser.parse_args()
    donor = json.loads(DONOR.read_text(encoding='utf-8'))
    external = json.loads(SITE.read_text(encoding='utf-8'))
    for alternative in args.alternatives:
        file = ROOT / f'plans/architect-alt-{alternative}-v2.json'
        plan = json.loads(file.read_text(encoding='utf-8'))
        if plan.get('siteRegistration'):
            print(f'Alt-{alternative}: already registered; no second rotation')
            continue
        registration = register_site(plan, donor, external)
        file.write_text(json.dumps(plan, indent=2)+'\n', encoding='utf-8')
        audit_file = ROOT / plan['importAudit']
        audit = json.loads(audit_file.read_text(encoding='utf-8'))
        record_registration(audit, registration)
        audit_file.write_text(json.dumps(audit, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        print(f'Alt-{alternative}: {json.dumps(registration)}')
