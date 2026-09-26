"""Extract the saved Alt-4 site without reinterpreting its geometry or colors."""

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plans/architect-alt-4-sheet-1.json"
KEY = "ruchama-18-20-external"
COLLECTIONS = ("boundaries", "rooms", "stairs", "walls", "openings", "elements", "rulers", "roofs")


def extract_external(source):
    ground = next(floor for floor in source["floors"] if floor["name"] == "Ground floor")
    source_key = source["projectName"]
    floor_id = KEY + "-ground"
    plan = copy.deepcopy(source)
    plan.update(projectName=KEY, source=f"Exterior extracted from {source_key}",
                activeFloorId=floor_id, viewFloor=floor_id, scale=14,
                camera={"position": {"x": 28, "y": 36, "z": 48}, "yaw": 3.79, "pitch": -.716})
    plan["floors"] = [{**copy.deepcopy(ground), "id": floor_id, "name": "External site", "exteriorOnly": True}]
    for collection in COLLECTIONS:
        plan[collection] = []

    # The source marks site/landscape objects as context, but not garden seating.
    garden_ids = {source_key + "-garden-dining-table"}
    garden_ids.update(f"{source_key}-garden-chair-{i}" for i in range(1, 7))
    source_ids = {item["id"] for item in source["elements"]}
    if not garden_ids <= source_ids:
        raise ValueError("Saved outdoor dining assembly changed; review the source before extracting")

    for collection in ("walls", "elements"):
        for item in source[collection]:
            if item.get("context") is not True and item["id"] not in garden_ids:
                continue
            if item["floorId"] != ground["id"]:
                raise ValueError(f"Exterior object on unexpected floor: {item['id']}")
            copied = copy.deepcopy(item)
            copied["id"] = KEY + item["id"].removeprefix(source_key)
            copied["floorId"] = floor_id
            plan[collection].append(copied)

    # Preserve the existing site guide; it is not a floor slab or house shell.
    boundary = copy.deepcopy(next(item for item in source["boundaries"] if item["floorId"] == ground["id"]))
    boundary.update(id=KEY + "-boundary", floorId=floor_id, name="External site boundary")
    plan["boundaries"] = [boundary]
    for field in ("selectedId", "selectedIds", "offset"):
        plan.pop(field, None)
    return plan


def validate_external(source, plan):
    original = {item["id"]: item for collection in ("walls", "elements") for item in source[collection]}
    objects = [item for collection in ("walls", "elements") for item in plan[collection]]
    assert len(objects) == len({item["id"] for item in objects})
    for item in objects:
        source_id = source["projectName"] + item["id"].removeprefix(KEY)
        source_item = original[source_id]
        # Compare every field except identity, not just the selected color fields.
        assert {k: v for k, v in item.items() if k not in ("id", "floorId")} == {
            k: v for k, v in source_item.items() if k not in ("id", "floorId")
        }, source_id
        assert item["floorId"] == plan["floors"][0]["id"]
    for collection in ("rooms", "stairs", "openings", "rulers", "roofs"):
        assert not plan[collection], f"House geometry leaked into {collection}"
    assert len(plan["walls"]) == sum(item.get("context") is True for item in source["walls"])
    assert len(plan["elements"]) == sum(item.get("context") is True for item in source["elements"]) + 7


if __name__ == "__main__":
    source_bytes = SOURCE.read_bytes()
    source = json.loads(source_bytes)
    result = extract_external(source)
    validate_external(source, result)
    result["sourceSha256"] = hashlib.sha256(source_bytes).hexdigest()
    target = ROOT / f"plans/{KEY}.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    assert SOURCE.read_bytes() == source_bytes, "Source save must remain unchanged"
    print(json.dumps({"path": str(target), "walls": len(result["walls"]),
                      "elements": dict(Counter(item["elementKind"] for item in result["elements"]))}, indent=2))
