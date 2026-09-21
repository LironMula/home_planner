"""Build editable Home Planner presets from the architect's DXF sheets.

The source DWG files must first be converted to DXF (R2004 or newer). Run:

    python tools/build_architect_presets.py --source-dir <dxf-directory>

The script writes standard plan JSON files under ``plans/``. Coordinates in
the drawings are centimetres; planner coordinates are metres.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import ezdxf
import ezdxf.bbox


WALL_LAYERS = {"A10", "A11"}
DOOR_LAYERS = {"A12", "A14", "H"}
WINDOW_LAYERS = {"A10", "A11"}
CM_PER_METER = 100.0


@dataclass(frozen=True)
class Sheet:
    key: str
    label: str
    frame_x_min: float
    frame_y_min: float
    frame_y_max: float
    clip: tuple[float, float, float, float]
    slab: tuple[float, float, float, float]


@dataclass(frozen=True)
class Design:
    key: str
    label: str
    source: str
    sheets: tuple[Sheet, ...]
    stair: tuple[float, float, float, float]


DESIGNS = (
    Design(
        key="architect-alt-3",
        label="Architect Alt 3",
        source="Alt-3.dxf",
        stair=(17.8, 14.0, 2.5, 3.35),
        sheets=(
            Sheet("basement", "Basement", 15729.1, -400.0, 1762.9, (7.0, 25.0, 7.0, 19.0), (8.76, 8.43, 15.20, 9.15)),
            Sheet("ground", "Ground floor", 15729.1, 3187.7, 5350.6, (7.0, 25.0, 7.0, 19.0), (8.76, 8.43, 15.20, 9.15)),
            Sheet("upper", "Upper floor", 15729.1, 5725.5, 7878.3, (7.0, 25.0, 7.0, 19.0), (8.76, 8.43, 15.20, 9.15)),
        ),
    ),
    Design(
        key="architect-alt-4-sheet-1",
        label="Architect Alt 4 - detailed",
        source="Alt-4.dxf",
        stair=(14.2, 14.0, 2.6, 3.35),
        sheets=(
            Sheet("basement", "Basement", 11896.3, -5372.4, -3209.6, (7.0, 26.0, 7.0, 19.0), (8.58, 8.29, 15.75, 9.00)),
            Sheet("ground", "Ground floor", 11896.3, -422.1, 1740.7, (7.0, 26.0, 7.0, 19.0), (8.58, 8.29, 15.75, 9.00)),
            Sheet("living", "Living floor", 11896.3, 2515.6, 4678.5, (7.0, 26.0, 7.0, 19.0), (7.44, 8.29, 16.90, 9.00)),
            Sheet("floor2", "Floor 2", 11896.3, 4991.0, 7153.8, (7.0, 26.0, 5.0, 19.0), (15.98, 8.54, 4.05, 4.00)),
        ),
    ),
    Design(
        key="architect-alt-4-sheet-11",
        label="Architect Alt 4 - alternate basement",
        source="Alt-4.dxf",
        stair=(14.2, 14.0, 2.6, 3.35),
        sheets=(
            Sheet("basement", "Basement", 11896.3, -2900.1, -737.2, (7.0, 26.0, 7.0, 19.0), (8.58, 8.29, 15.75, 9.00)),
            Sheet("ground", "Ground floor", 11896.3, -422.1, 1740.7, (7.0, 26.0, 7.0, 19.0), (8.58, 8.29, 15.75, 9.00)),
            Sheet("living", "Living floor", 11896.3, 2515.6, 4678.5, (7.0, 26.0, 7.0, 19.0), (7.44, 8.29, 16.90, 9.00)),
            Sheet("floor2", "Floor 2", 11896.3, 4991.0, 7153.8, (7.0, 26.0, 5.0, 19.0), (15.98, 8.54, 4.05, 4.00)),
        ),
    ),
    Design(
        key="architect-alt-5",
        label="Architect Alt 5",
        source="Alt-5.dxf",
        stair=(14.0, 14.0, 2.6, 3.35),
        sheets=(
            Sheet("basement", "Basement", 27638.9, -543.5, 1619.3, (5.0, 28.0, 7.0, 19.0), (5.75, 8.25, 21.20, 9.10)),
            Sheet("ground", "Ground floor", 27638.9, 1967.8, 4130.7, (5.0, 28.0, 7.0, 19.0), (5.75, 8.25, 21.20, 9.10)),
            Sheet("upper", "Upper floor", 27638.9, 4496.2, 6659.1, (5.0, 28.0, 7.0, 19.0), (5.75, 8.25, 21.20, 9.10)),
        ),
    ),
)


def round_number(value: float, places: int = 3) -> float:
    return round(float(value), places)


def transform_point(sheet: Sheet, point: tuple[float, float]) -> tuple[float, float]:
    return (
        (point[0] - sheet.frame_x_min) / CM_PER_METER,
        (sheet.frame_y_max - point[1]) / CM_PER_METER,
    )


def inside_clip(sheet: Sheet, point: tuple[float, float], margin: float = 0.15) -> bool:
    x1, x2, y1, y2 = sheet.clip
    return x1 - margin <= point[0] <= x2 + margin and y1 - margin <= point[1] <= y2 + margin


def entity_segments(entity) -> Iterable[tuple[tuple[float, float], tuple[float, float]]]:
    if entity.dxftype() == "LINE":
        yield (entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)
        return
    if entity.dxftype() != "LWPOLYLINE":
        return
    points = [(point[0], point[1]) for point in entity.get_points("xy")]
    if entity.closed and len(points) > 2:
        points.append(points[0])
    for start, end in zip(points, points[1:]):
        yield start, end


def normalized_segment(
    start: tuple[float, float], end: tuple[float, float]
) -> tuple[tuple[float, float], tuple[float, float]]:
    if start[0] > end[0] or (math.isclose(start[0], end[0]) and start[1] > end[1]):
        return end, start
    return start, end


def collect_wall_segments(modelspace, sheet: Sheet) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    segments = []
    seen = set()
    for entity in modelspace:
        if entity.dxf.layer not in WALL_LAYERS:
            continue
        for cad_start, cad_end in entity_segments(entity):
            start = transform_point(sheet, cad_start)
            end = transform_point(sheet, cad_end)
            midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
            length = math.dist(start, end)
            if not inside_clip(sheet, midpoint) or not 0.18 <= length <= 20:
                continue
            start, end = normalized_segment(start, end)
            key = tuple(round(value / 0.025) for point in (start, end) for value in point)
            if key in seen:
                continue
            seen.add(key)
            segments.append((start, end))
    return segments


def segment_frame(segment):
    start, end = segment
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    t1 = start[0] * ux + start[1] * uy
    t2 = end[0] * ux + end[1] * uy
    offset = start[0] * nx + start[1] * ny
    return ux, uy, nx, ny, min(t1, t2), max(t1, t2), offset, length


def wall_centerlines(segments):
    """Pair nearby wall faces; preserve useful unpaired architectural lines."""
    used = set()
    output = []
    order = sorted(range(len(segments)), key=lambda index: math.dist(*segments[index]), reverse=True)
    for index in order:
        if index in used:
            continue
        first = segment_frame(segments[index])
        best = None
        for other_index in order:
            if other_index == index or other_index in used:
                continue
            second = segment_frame(segments[other_index])
            parallel = abs(first[0] * second[1] - first[1] * second[0])
            if parallel > 0.045:
                continue
            second_points = segments[other_index]
            projections = [point[0] * first[0] + point[1] * first[1] for point in second_points]
            second_min, second_max = min(projections), max(projections)
            overlap = min(first[5], second_max) - max(first[4], second_min)
            if overlap < min(first[7], second[7]) * 0.6:
                continue
            offsets = [point[0] * first[2] + point[1] * first[3] for point in second_points]
            distance = abs(sum(offsets) / len(offsets) - first[6])
            if not 0.055 <= distance <= 0.34:
                continue
            score = overlap - distance * 0.35
            if best is None or score > best[0]:
                best = (score, other_index, second_min, second_max, sum(offsets) / len(offsets), distance)
        if best:
            _, other_index, second_min, second_max, second_offset, distance = best
            used.update((index, other_index))
            start_t = (first[4] + second_min) / 2
            end_t = (first[5] + second_max) / 2
            center_offset = (first[6] + second_offset) / 2
            start = (first[0] * start_t + first[2] * center_offset, first[1] * start_t + first[3] * center_offset)
            end = (first[0] * end_t + first[2] * center_offset, first[1] * end_t + first[3] * center_offset)
            output.append((start, end, min(0.28, max(0.12, distance))))
        else:
            used.add(index)
            if first[7] >= 0.45:
                output.append((*segments[index], 0.14))
    return output


def wall_item(design: Design, sheet: Sheet, index: int, start, end, thickness: float) -> dict:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    rotation = math.degrees(math.atan2(dy, dx)) % 180
    return {
        "id": f"{design.key}-{sheet.key}-wall-{index}",
        "type": "wall",
        "floorId": f"{design.key}-{sheet.key}",
        "name": f"CAD wall {index}",
        "x": round_number(midpoint[0] - length / 2),
        "y": round_number(midpoint[1] - thickness / 2),
        "w": round_number(length),
        "h": round_number(thickness),
        "height": 2.8,
        "rotation": round_number(rotation, 2),
        "color": "#ffffff",
        "opacity": 0.95,
        "groupId": f"{design.key}-{sheet.key}-structure",
    }


def collect_doors(modelspace, design: Design, sheet: Sheet) -> list[dict]:
    doors = []
    for entity in modelspace:
        if entity.dxftype() != "ARC" or entity.dxf.layer not in DOOR_LAYERS:
            continue
        radius = float(entity.dxf.radius) / CM_PER_METER
        center = transform_point(sheet, (entity.dxf.center.x, entity.dxf.center.y))
        if not inside_clip(sheet, center) or not 0.55 <= radius <= 1.35:
            continue
        angle = math.radians(float(entity.dxf.start_angle))
        position = (center[0] + math.cos(angle) * radius / 2, center[1] - math.sin(angle) * radius / 2)
        if any(math.dist(position, (door["x"], door["y"])) < 0.35 for door in doors):
            continue
        doors.append({
            "id": f"{design.key}-{sheet.key}-door-{len(doors) + 1}",
            "type": "door",
            "floorId": f"{design.key}-{sheet.key}",
            "roomId": None,
            "wallId": None,
            "name": f"CAD door {len(doors) + 1}",
            "side": "free",
            "t": 0.5,
            "x": round_number(position[0]),
            "y": round_number(position[1]),
            "rotation": round_number((-float(entity.dxf.start_angle)) % 360, 2),
            "width": round_number(radius),
            "height": 2.1,
            "sill": 0,
            "swing": 0,
            "color": "#c87a35",
            "opacity": 0.82,
        })
    return doors


def collect_windows(modelspace, design: Design, sheet: Sheet) -> list[dict]:
    windows = []
    for entity in modelspace:
        if entity.dxftype() != "LWPOLYLINE" or entity.dxf.layer not in WINDOW_LAYERS:
            continue
        points = [transform_point(sheet, (point[0], point[1])) for point in entity.get_points("xy")]
        if len(points) < 3:
            continue
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        width, depth = max(xs) - min(xs), max(ys) - min(ys)
        short, long = sorted((width, depth))
        center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
        if not inside_clip(sheet, center) or not 0.04 <= short <= 0.34 or not 0.55 <= long <= 3.6:
            continue
        if any(math.dist(center, (window["x"], window["y"])) < 0.32 for window in windows):
            continue
        windows.append({
            "id": f"{design.key}-{sheet.key}-window-{len(windows) + 1}",
            "type": "window",
            "floorId": f"{design.key}-{sheet.key}",
            "roomId": None,
            "wallId": None,
            "name": f"CAD window {len(windows) + 1}",
            "side": "free",
            "t": 0.5,
            "x": round_number(center[0]),
            "y": round_number(center[1]),
            "rotation": 0 if width >= depth else 90,
            "width": round_number(long),
            "height": 1.2,
            "sill": 0.9,
            "color": "#45a9d8",
            "opacity": 0.62,
        })
    return windows


def add_reference_openings(design: Design, sheet: Sheet, openings: list[dict]) -> list[dict]:
    """Fill semantic gaps left by exploded CAD opening symbols."""
    floor_id = f"{design.key}-{sheet.key}"
    slab_x, slab_y, slab_w, slab_h = sheet.slab
    doors = [opening for opening in openings if opening["type"] == "door"]
    windows = [opening for opening in openings if opening["type"] == "window"]
    if not doors:
        doors.append({
            "id": f"{floor_id}-reference-door",
            "type": "door",
            "floorId": floor_id,
            "roomId": None,
            "wallId": None,
            "name": "Reference entrance door",
            "side": "free",
            "t": 0.5,
            "x": round_number(slab_x + slab_w * 0.18),
            "y": round_number(slab_y + slab_h),
            "rotation": 0,
            "width": 1.0,
            "height": 2.1,
            "sill": 0,
            "swing": 0,
            "color": "#c87a35",
            "opacity": 0.82,
        })
    if len(windows) < 2:
        window_specs = (
            (slab_x + slab_w * 0.28, slab_y, 0, 1.6),
            (slab_x + slab_w * 0.72, slab_y, 0, 1.6),
            (slab_x + slab_w * 0.38, slab_y + slab_h, 0, 1.8),
            (slab_x + slab_w, slab_y + slab_h * 0.52, 90, 1.4),
        )
        windows = []
        for index, (x, y, rotation, width) in enumerate(window_specs, start=1):
            windows.append({
                "id": f"{floor_id}-reference-window-{index}",
                "type": "window",
                "floorId": floor_id,
                "roomId": None,
                "wallId": None,
                "name": f"Reference window {index}",
                "side": "free",
                "t": 0.5,
                "x": round_number(x),
                "y": round_number(y),
                "rotation": rotation,
                "width": width,
                "height": 1.2,
                "sill": 0.9,
                "color": "#45a9d8",
                "opacity": 0.62,
            })
    return [*doors, *windows]


ALT4_WINDOW_HINTS = {
    "basement": (
        (8.58, 10.99, 1.10, "Basement west window"),
        (17.03, 14.12, 0.81, "Basement window 2"),
        (17.57, 14.64, 0.70, "Basement window 3"),
    ),
    "ground": (
        (19.61, 8.39, 2.45, "North picture window"),
        (24.23, 11.09, 2.60, "East full-height window"),
        (24.33, 13.54, 0.95, "East window"),
        (11.51, 9.71, 3.85, "Window above kitchen work surface"),
        (11.11, 14.69, 1.23, "Ground window 5"),
        (8.71, 16.44, 0.60, "South-west window"),
    ),
    "living": (
        (17.48, 8.41, 2.70, "Living north window"),
        (24.33, 9.34, 1.05, "Living east window 1"),
        (24.33, 12.86, 1.00, "Living east window 2"),
        (11.18, 9.71, 1.00, "Living window 3"),
        (14.18, 10.29, 0.90, "Living window 4"),
        (8.68, 10.69, 0.80, "Living west window"),
        (7.56, 16.19, 0.80, "Living south-west window"),
        (20.98, 17.19, 0.70, "Living south window"),
    ),
    "floor2": (
        (15.88, 11.93, 0.60, "Floor 2 window"),
    ),
}


def project_to_segment(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= 1e-9:
        return math.dist(point, start), start, 0.0
    t = max(0.0, min(1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared))
    projected = (start[0] + t * dx, start[1] + t * dy)
    return math.dist(point, projected), projected, t


def nearest_wall(point, centerlines, maximum_distance: float = 0.9):
    best = None
    for start, end, thickness in centerlines:
        distance, projected, t = project_to_segment(point, start, end)
        if distance > maximum_distance:
            continue
        length = math.dist(start, end)
        angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])) % 180
        candidate = (distance, projected, t, start, end, length, angle, thickness)
        if best is None or candidate[0] < best[0]:
            best = candidate
    return best


def collect_alt4_windows(design: Design, sheet: Sheet, centerlines) -> list[dict]:
    windows = []
    for index, (x, y, width, name) in enumerate(ALT4_WINDOW_HINTS.get(sheet.key, ()), start=1):
        snapped = nearest_wall((x, y), centerlines)
        position = snapped[1] if snapped else (x, y)
        rotation = snapped[6] if snapped else 0
        full_height = "full-height" in name.lower() or "picture" in name.lower()
        windows.append({
            "id": f"{design.key}-{sheet.key}-window-{index}",
            "type": "window",
            "floorId": f"{design.key}-{sheet.key}",
            "roomId": None,
            "wallId": None,
            "name": name,
            "side": "free",
            "t": 0.5,
            "x": round_number(position[0]),
            "y": round_number(position[1]),
            "rotation": round_number(rotation, 2),
            "width": width,
            "height": 2.35 if full_height else 1.2,
            "sill": 0.15 if full_height else 0.9,
            "color": "#45a9d8",
            "opacity": 0.62,
        })
    return windows


def collect_alt4_doors(modelspace, design: Design, sheet: Sheet, centerlines) -> list[dict]:
    arc_specs = []
    for entity in modelspace:
        if entity.dxftype() == "ARC" and entity.dxf.layer in {"A12", "H"}:
            arc_specs.append((
                (entity.dxf.center.x, entity.dxf.center.y),
                float(entity.dxf.radius) / CM_PER_METER,
                float(entity.dxf.start_angle),
                float(entity.dxf.end_angle),
            ))
        elif entity.dxftype() == "INSERT" and entity.dxf.layer == "A12" and entity.dxf.name.upper() == "DARC":
            scale = max(abs(float(entity.dxf.get("xscale", 1))), abs(float(entity.dxf.get("yscale", 1))))
            angle = float(entity.dxf.get("rotation", 0))
            arc_specs.append(((entity.dxf.insert.x, entity.dxf.insert.y), 0.65 * scale, angle, angle + 90))

    doors = []
    seen_hinges = []
    for cad_hinge, radius, start_angle, end_angle in arc_specs:
        hinge = transform_point(sheet, cad_hinge)
        if not inside_clip(sheet, hinge) or not 0.52 <= radius <= 1.35:
            continue
        if any(math.dist(hinge, other) < 0.16 for other in seen_hinges):
            continue
        snapped = nearest_wall(hinge, centerlines, 0.75)
        if not snapped:
            continue
        seen_hinges.append(hinge)
        _, projected, wall_t, wall_start, wall_end, wall_length, wall_angle, _ = snapped
        wall_unit = ((wall_end[0] - wall_start[0]) / wall_length, (wall_end[1] - wall_start[1]) / wall_length)
        directions = []
        for angle in (start_angle, end_angle):
            radians = math.radians(-angle)
            direction = (math.cos(radians), math.sin(radians))
            directions.append((abs(direction[0] * wall_unit[0] + direction[1] * wall_unit[1]), direction))
        _, direction = max(directions, key=lambda candidate: candidate[0])
        sign = 1 if direction[0] * wall_unit[0] + direction[1] * wall_unit[1] >= 0 else -1
        center_t = wall_t + sign * radius / (2 * max(0.1, wall_length))
        position = (
            wall_start[0] + (wall_end[0] - wall_start[0]) * center_t,
            wall_start[1] + (wall_end[1] - wall_start[1]) * center_t,
        )
        exterior = sheet.key == "ground" and position[1] < 10.2
        doors.append({
            "id": f"{design.key}-{sheet.key}-door-{len(doors) + 1}",
            "type": "door",
            "floorId": f"{design.key}-{sheet.key}",
            "roomId": None,
            "wallId": None,
            "name": f"Front door {len(doors) + 1}" if exterior else f"Internal door {len(doors) + 1}",
            "side": "free",
            "t": 0.5,
            "x": round_number(position[0]),
            "y": round_number(position[1]),
            "rotation": round_number(wall_angle, 2),
            "width": round_number(radius),
            "height": 2.1,
            "sill": 0,
            "swing": 0,
            "color": "#c87a35",
            "opacity": 0.82,
        })
    return doors


ALT4_BLOCK_ELEMENTS = {
    "BED": ("bed", "Bed", 0.75, "#94a3b8"),
    "CH": ("chair", "Chair", 0.90, "#8ab17d"),
    "SOFA-60": ("sofa", "Sofa", 0.82, "#b7846f"),
    "SOFA-CRN": ("sofa", "Corner sofa", 0.82, "#b7846f"),
    "HARSA506": ("toilet", "Toilet", 0.75, "#e8edf2"),
    "SS01": ("sink", "Sink", 0.85, "#70b7c8"),
    "BATH": ("bath", "Bath", 0.65, "#d9f0f5"),
    "WASH": ("shower", "Shower", 2.10, "#9bd5e5"),
    "BLMLT": ("sink", "Kitchen sink", 0.90, "#70b7c8"),
}


def collect_alt4_block_elements(modelspace, design: Design, sheet: Sheet) -> list[dict]:
    elements = []
    for entity in modelspace:
        if entity.dxftype() != "INSERT":
            continue
        block_name = entity.dxf.name.upper()
        spec = ALT4_BLOCK_ELEMENTS.get(block_name)
        if not spec:
            continue
        if sheet.key == "ground" and block_name == "SS01":
            # The ground-floor SS01 insertion does not match the basin's drawn
            # location in this sheet; the guest basin is anchored manually.
            continue
        try:
            extents = ezdxf.bbox.extents([entity], fast=False)
        except Exception:
            continue
        if not extents.has_data:
            continue
        cad_center = (
            (extents.extmin.x + extents.extmax.x) / 2,
            (extents.extmin.y + extents.extmax.y) / 2,
        )
        center = transform_point(sheet, cad_center)
        if not inside_clip(sheet, center, 1.6):
            continue
        width = max(0.35, (extents.extmax.x - extents.extmin.x) / CM_PER_METER)
        depth = max(0.35, (extents.extmax.y - extents.extmin.y) / CM_PER_METER)
        kind, label, height, color = spec
        elements.append({
            "id": f"{design.key}-{sheet.key}-{kind}-{len(elements) + 1}",
            "type": "element",
            "floorId": f"{design.key}-{sheet.key}",
            "name": f"{label} {sum(item['elementKind'] == kind for item in elements) + 1}",
            "elementKind": kind,
            "x": round_number(center[0] - width / 2),
            "y": round_number(center[1] - depth / 2),
            "w": round_number(width),
            "h": round_number(depth),
            "elevation": 0,
            "height": height,
            "rotation": round_number((-float(entity.dxf.get("rotation", 0))) % 360, 2),
            "color": color,
            "opacity": 0.9,
        })
    return elements


ALT4_MANUAL_ELEMENTS = {
    "ground": (
        ("kitchen-work-surface", "Kitchen work surface", 8.88, 9.84, 4.60, 0.65, 0.92, "#d7d0c2"),
        ("kitchen-work-surface", "Kitchen work surface return", 13.48, 9.84, 0.65, 1.85, 0.92, "#d7d0c2"),
        ("kitchen-island", "Kitchen island", 9.88, 11.59, 2.50, 1.10, 0.92, "#d6c6ad"),
        ("closet", "Kitchen storage", 9.83, 13.99, 3.25, 0.65, 2.10, "#9c8269"),
        ("closet", "Pantry storage", 9.83, 14.74, 3.15, 0.60, 2.10, "#9c8269"),
        ("table", "Dining table", 16.17, 14.24, 2.00, 1.10, 0.76, "#b08968"),
        ("sofa", "Living room sofa", 19.03, 10.48, 3.00, 0.95, 0.82, "#b7846f"),
        ("table", "Living room coffee table", 20.45, 11.58, 1.08, 0.62, 0.48, "#b08968"),
        ("toilet", "Guest toilet", 14.48, 9.86, 0.65, 0.80, 0.75, "#e8edf2"),
        ("sink", "Guest toilet sink", 14.48, 11.25, 0.65, 0.40, 0.85, "#70b7c8"),
    ),
    "living": (
        ("bed", "Bedroom bed 1", 14.27, 8.58, 1.20, 2.00, 0.75, "#94a3b8"),
        ("bed", "Bedroom bed 2", 18.78, 8.59, 1.20, 2.00, 0.75, "#94a3b8"),
        ("closet", "Living floor wardrobe", 8.90, 13.84, 2.58, 0.60, 2.10, "#8b6145"),
        ("table", "Living floor desk", 18.23, 12.04, 1.80, 0.60, 0.75, "#b08968"),
    ),
    "floor2": (
        ("bed", "Floor 2 bed", 18.77, 10.48, 1.20, 2.00, 0.75, "#94a3b8"),
        ("closet", "Floor 2 storage", 18.39, 8.58, 1.60, 0.65, 1.45, "#8b6145"),
    ),
}


ALT4_MANUAL_OPENINGS = {
    "ground": (
        ("door", "Guest toilet door", 15.46, 10.96, 0.75, 2.10, 0.0, 90.0),
    ),
}


def alt4_manual_openings(design: Design, sheet: Sheet) -> list[dict]:
    openings = []
    for index, (kind, name, x, y, width, height, sill, rotation) in enumerate(
        ALT4_MANUAL_OPENINGS.get(sheet.key, ()), start=1
    ):
        openings.append({
            "id": f"{design.key}-{sheet.key}-manual-opening-{index}",
            "type": kind,
            "floorId": f"{design.key}-{sheet.key}",
            "roomId": None,
            "wallId": None,
            "name": name,
            "side": "free",
            "t": 0.5,
            "x": x,
            "y": y,
            "rotation": rotation,
            "width": width,
            "height": height,
            "sill": sill,
            "swing": 0,
            "color": "#c87a35" if kind == "door" else "#45a9d8",
            "opacity": 0.82 if kind == "door" else 0.62,
        })
    return openings


def alt4_manual_elements(design: Design, sheet: Sheet) -> list[dict]:
    elements = []
    for index, (kind, name, x, y, width, depth, height, color) in enumerate(ALT4_MANUAL_ELEMENTS.get(sheet.key, ()), start=1):
        elements.append({
            "id": f"{design.key}-{sheet.key}-furniture-{index}",
            "type": "element",
            "floorId": f"{design.key}-{sheet.key}",
            "name": name,
            "elementKind": kind,
            "x": x,
            "y": y,
            "w": width,
            "h": depth,
            "elevation": 0,
            "height": height,
            "rotation": 0,
            "color": color,
            "opacity": 0.9,
        })
    return elements


def base_site_elements(design: Design, ground_floor_id: str) -> list[dict]:
    elements = [
        {
            "id": f"{design.key}-grass",
            "type": "element",
            "floorId": ground_floor_id,
            "name": "Architect site lawn",
            "elementKind": "grass",
            "x": 1.4,
            "y": 2.1,
            "w": 29.5,
            "h": 15.7,
            "elevation": -0.06,
            "height": 0.05,
            "rotation": 0,
            "color": "#4f9d4e",
            "opacity": 0.15,
        },
        {
            "id": f"{design.key}-road",
            "type": "element",
            "floorId": ground_floor_id,
            "name": "Road",
            "elementKind": "road",
            "x": 1.4,
            "y": 0.55,
            "w": 29.5,
            "h": 2.0,
            "elevation": -0.08,
            "height": 0.04,
            "rotation": 0,
            "color": "#2f343b",
            "opacity": 0.9,
        },
    ]
    for index, y in enumerate((3.0, 5.2), start=1):
        elements.append({
            "id": f"{design.key}-car-{index}",
            "type": "element",
            "floorId": ground_floor_id,
            "name": f"Parking car {index}",
            "elementKind": "car",
            "x": 3.0,
            "y": y,
            "w": 4.4,
            "h": 1.9,
            "elevation": 0,
            "height": 1.55,
            "rotation": 90,
            "color": "#64748b" if index == 1 else "#2563eb",
            "opacity": 0.88,
        })
    for index, (x, y, size) in enumerate(((27.5, 4.4, 2.2), (28.0, 14.5, 2.6), (5.0, 15.0, 2.0)), start=1):
        elements.append({
            "id": f"{design.key}-tree-{index}",
            "type": "element",
            "floorId": ground_floor_id,
            "name": f"Site tree {index}",
            "elementKind": "tree",
            "x": x - size / 2,
            "y": y - size / 2,
            "w": size,
            "h": size,
            "elevation": 0,
            "height": 4.5 + index * 0.5,
            "rotation": 0,
            "color": "#3f8f46",
            "opacity": 0.9,
        })
    return elements


def alt4_roofs(design: Design) -> list[dict]:
    return [
        {
            "id": f"{design.key}-living-flat-roof",
            "type": "roof",
            "floorId": f"{design.key}-living",
            "name": "Lower wing flat roof",
            "x": 7.20,
            "y": 8.02,
            "w": 7.35,
            "h": 9.50,
            "z": 2.76,
            "angle": 0,
            "tilt": "north",
            "color": "#91857d",
            "opacity": 0.88,
        },
        {
            "id": f"{design.key}-barrel-roof",
            "type": "roof",
            "floorId": f"{design.key}-floor2",
            "name": "Round tiled roof",
            "shape": "barrel",
            "axis": "z",
            "x": 14.15,
            "y": 8.02,
            "w": 10.45,
            "h": 9.55,
            "z": 2.02,
            "rise": 2.05,
            "angle": 0,
            "tilt": "north",
            "color": "#ad5636",
            "opacity": 0.9,
        },
    ]


ALT4_SITE_PIVOT = (4.775, 5.0)


def rotate_alt4_house_180(plan: dict) -> None:
    pivot_x, pivot_y = ALT4_SITE_PIVOT
    for collection_name in ("rooms", "stairs", "walls", "openings", "elements", "roofs"):
        for item in plan.get(collection_name, []):
            if not isinstance(item.get("x"), (int, float)) or not isinstance(item.get("y"), (int, float)):
                continue
            if collection_name == "openings":
                item["x"] = round_number(2 * pivot_x - item["x"])
                item["y"] = round_number(2 * pivot_y - item["y"])
            else:
                width = float(item.get("w", 0))
                depth = float(item.get("h", 0))
                center_x = item["x"] + width / 2
                center_y = item["y"] + depth / 2
                item["x"] = round_number(2 * pivot_x - center_x - width / 2)
                item["y"] = round_number(2 * pivot_y - center_y - depth / 2)
            if "rotation" in item:
                item["rotation"] = round_number((float(item.get("rotation", 0)) + 180) % 360, 2)
            if collection_name == "roofs" and item.get("tilt"):
                item["tilt"] = {
                    "north": "south",
                    "south": "north",
                    "east": "west",
                    "west": "east",
                }.get(item["tilt"], item["tilt"])


def transform_alt4_to_saved_site(
    plan: dict,
    design: Design,
    site_plan: dict | None,
    landscape_plan: dict | None,
) -> None:
    dx, dy = -11.68, -7.79
    for collection_name in ("rooms", "stairs", "walls", "openings", "elements", "roofs"):
        for item in plan.get(collection_name, []):
            if isinstance(item.get("x"), (int, float)):
                item["x"] = round_number(item["x"] + dx)
            if isinstance(item.get("y"), (int, float)):
                item["y"] = round_number(item["y"] + dy)

    rotate_alt4_house_180(plan)

    floor_bounds = {
        "basement": (-3.7, 0.1, 16.9, 9.8),
        "ground": (-12.5, -2.5, 39.0, 35.0),
        "living": (-4.5, 0.1, 18.0, 9.8),
        "floor2": (3.7, 0.3, 5.0, 4.9),
    }
    plan["boundaries"] = []
    for floor in plan["floors"]:
        key = floor["id"].rsplit("-", 1)[-1]
        x, y, width, depth = floor_bounds[key]
        plan["boundaries"].append({
            "id": f"{floor['id']}-boundary",
            "type": "boundary",
            "floorId": floor["id"],
            "name": f"{floor['name']} boundary",
            "x": x,
            "y": y,
            "w": width,
            "h": depth,
            "color": "#94a3b8",
            "opacity": 0.12,
        })

    if not site_plan:
        return

    ground_floor_id = f"{design.key}-ground"
    for item in site_plan.get("walls", []):
        if not str(item.get("id", "")).startswith("site-wall-"):
            continue
        copied = dict(item)
        copied["id"] = f"{design.key}-{item['id']}"
        copied["floorId"] = ground_floor_id
        copied["context"] = True
        plan["walls"].append(copied)

    for item in site_plan.get("elements", []):
        if not str(item.get("id", "")).startswith("site-element-"):
            continue
        copied = dict(item)
        copied["id"] = f"{design.key}-{item['id']}"
        copied["floorId"] = ground_floor_id
        copied["context"] = True
        plan["elements"].append(copied)

    landscape_kinds = {"grass", "pool", "ninja-set"}
    for item in (landscape_plan or {}).get("elements", []):
        if item.get("elementKind") not in landscape_kinds:
            continue
        copied = dict(item)
        copied["id"] = f"{design.key}-landscape-{item['id']}"
        copied["floorId"] = ground_floor_id
        copied["context"] = True
        plan["elements"].append(copied)

    garden_table = next((item for item in site_plan.get("elements", []) if item.get("name") == "Table 1"), None)
    if garden_table:
        copied = dict(garden_table)
        copied.update({
            "id": f"{design.key}-garden-dining-table",
            "floorId": ground_floor_id,
            "name": "Garden dining table",
        })
        plan["elements"].append(copied)

    chair_specs = (
        (12.25, 3.65, 0), (13.45, 3.65, 0), (14.65, 3.65, 0),
        (12.25, 6.28, 180), (13.45, 6.28, 180), (14.65, 6.28, 180),
        (12.25, 7.65, 35), (14.10, 7.45, 325), (13.10, 8.55, 180),
    )
    for index, (x, y, rotation) in enumerate(chair_specs, start=1):
        plan["elements"].append({
            "id": f"{design.key}-garden-chair-{index}",
            "type": "element",
            "floorId": ground_floor_id,
            "name": f"Garden chair {index}",
            "elementKind": "chair",
            "x": x,
            "y": y,
            "w": 0.55,
            "h": 0.55,
            "elevation": 0,
            "height": 0.9,
            "rotation": rotation,
            "color": "#647f56",
            "opacity": 0.9,
        })
    plan["elements"].append({
        "id": f"{design.key}-garden-lounge-table",
        "type": "element",
        "floorId": ground_floor_id,
        "name": "Garden lounge table",
        "elementKind": "round-table",
        "x": 13.05,
        "y": 7.55,
        "w": 0.75,
        "h": 0.75,
        "elevation": 0,
        "height": 0.5,
        "rotation": 0,
        "color": "#8e765f",
        "opacity": 0.9,
    })


def planner_wall_segment(wall: dict) -> tuple[tuple[float, float], tuple[float, float]]:
    angle = math.radians(float(wall.get("rotation", 0)))
    center_x = float(wall["x"]) + float(wall["w"]) / 2
    center_y = float(wall["y"]) + float(wall["h"]) / 2
    offset_x = math.cos(angle) * float(wall["w"]) / 2
    offset_y = math.sin(angle) * float(wall["w"]) / 2
    return (
        (center_x - offset_x, center_y - offset_y),
        (center_x + offset_x, center_y + offset_y),
    )


def validate_alt4_plan(plan: dict) -> None:
    structural_walls = [wall for wall in plan["walls"] if not wall.get("context")]
    for opening in plan["openings"]:
        walls = [wall for wall in structural_walls if wall["floorId"] == opening["floorId"]]
        nearest = min(
            project_to_segment((opening["x"], opening["y"]), *planner_wall_segment(wall))[0]
            for wall in walls
        )
        if nearest > float(opening["width"]) / 2 + 0.06:
            raise ValueError(f"Opening is detached from its wall gap: {opening['name']} ({nearest:.3f} m)")

    by_name = {element["name"]: element for element in plan["elements"]}
    kitchen_sink = by_name.get("Kitchen sink 1")
    work_surfaces = [element for element in plan["elements"] if element.get("elementKind") == "kitchen-work-surface"]
    if kitchen_sink and not any(
        kitchen_sink["x"] < surface["x"] + surface["w"]
        and kitchen_sink["x"] + kitchen_sink["w"] > surface["x"]
        and kitchen_sink["y"] < surface["y"] + surface["h"]
        and kitchen_sink["y"] + kitchen_sink["h"] > surface["y"]
        for surface in work_surfaces
    ):
        raise ValueError("Kitchen sink does not overlap a kitchen work surface")

    required_names = {"Guest toilet door", "Guest toilet", "Guest toilet sink"}
    present_names = {item.get("name") for item in [*plan["openings"], *plan["elements"]]}
    missing_names = required_names - present_names
    if missing_names:
        raise ValueError(f"Missing Alt 4 guest-WC items: {sorted(missing_names)}")

    landscape_kinds = {element.get("elementKind") for element in plan["elements"]}
    missing_landscape = {"grass", "pool", "ninja-set"} - landscape_kinds
    if missing_landscape:
        raise ValueError(f"Missing saved landscape objects: {sorted(missing_landscape)}")


def build_plan(
    design: Design,
    source_dir: Path,
    site_plan: dict | None = None,
    landscape_plan: dict | None = None,
) -> dict:
    document = ezdxf.readfile(source_dir / design.source)
    modelspace = document.modelspace()
    floor_elevations = {"basement": -2.75, "ground": 0, "living": 2.79, "floor2": 5.58, "upper": 3.15}
    floor_colors = {"basement": "#7c3aed", "ground": "#0f766e", "living": "#2563eb", "floor2": "#b45309", "upper": "#2563eb"}
    floors = []
    boundaries = []
    rooms = []
    walls = []
    openings = []
    stairs = []
    elements = []

    for sheet in design.sheets:
        floor_id = f"{design.key}-{sheet.key}"
        floors.append({
            "id": floor_id,
            "name": sheet.label,
            "elevation": floor_elevations[sheet.key],
            "color": floor_colors[sheet.key],
        })
        boundaries.append({
            "id": f"{floor_id}-boundary",
            "type": "boundary",
            "floorId": floor_id,
            "name": f"{sheet.label} property boundary",
            "x": 1.25,
            "y": 0.45,
            "w": 30.7,
            "h": 18.1,
            "color": "#94a3b8",
            "opacity": 0.12,
        })
        slab_x, slab_y, slab_w, slab_h = sheet.slab
        rooms.append({
            "id": f"{floor_id}-slab",
            "type": "space",
            "floorId": floor_id,
            "name": f"{sheet.label} slab",
            "x": slab_x,
            "y": slab_y,
            "w": slab_w,
            "h": slab_h,
            "color": "#d9dee5",
            "wallColor": "#ffffff",
            "opacity": 0.72,
        })
        centerlines = wall_centerlines(collect_wall_segments(modelspace, sheet))
        floor_walls = [
            wall_item(design, sheet, index, start, end, thickness)
            for index, (start, end, thickness) in enumerate(centerlines, start=1)
        ]
        wall_height = {"basement": 2.23, "ground": 2.79, "living": 2.75, "floor2": 2.05}.get(sheet.key, 2.8)
        for wall in floor_walls:
            wall["height"] = wall_height
        walls.extend(floor_walls)

        if design.key.startswith("architect-alt-4"):
            floor_openings = collect_alt4_doors(modelspace, design, sheet, centerlines)
            floor_openings.extend(collect_alt4_windows(design, sheet, centerlines))
            floor_openings.extend(alt4_manual_openings(design, sheet))
            openings.extend(floor_openings)
            elements.extend(collect_alt4_block_elements(modelspace, design, sheet))
            elements.extend(alt4_manual_elements(design, sheet))
        else:
            floor_openings = collect_doors(modelspace, design, sheet)
            floor_openings.extend(collect_windows(modelspace, design, sheet))
            openings.extend(add_reference_openings(design, sheet, floor_openings))

        top_key = "floor2" if design.key.startswith("architect-alt-4") else "upper"
        if sheet.key != top_key:
            stair_specs = {
                "basement": (17.15, 13.70, 2.45, 3.25),
                "ground": (13.85, 13.95, 2.55, 3.30),
                "living": (16.80, 13.55, 2.35, 3.25),
            }
            stair_x, stair_y, stair_w, stair_h = stair_specs.get(sheet.key, design.stair) if design.key.startswith("architect-alt-4") else design.stair
            stairs.append({
                "id": f"{floor_id}-stairs",
                "type": "stair",
                "floorId": floor_id,
                "name": f"{sheet.label} stairs",
                "x": stair_x,
                "y": stair_y,
                "w": stair_w,
                "h": stair_h,
                "shape": "uturn",
                "turn": "right",
                "landing": 1.05,
                "rotation": 0,
                "level": 0,
                "height": 2.75 if design.key.startswith("architect-alt-4") else 2.8,
                "color": "#6e62cf",
                "opacity": 0.9,
            })

    ground_id = f"{design.key}-ground"
    if design.key.startswith("architect-alt-4"):
        roofs = alt4_roofs(design)
    else:
        upper_sheet = next(sheet for sheet in design.sheets if sheet.key == "upper")
        roof_x, roof_y, roof_w, roof_h = upper_sheet.slab
        roofs = [
            {
                "id": f"{design.key}-roof-north",
                "type": "roof",
                "floorId": f"{design.key}-upper",
                "name": "North roof slope",
                "x": roof_x - 0.25,
                "y": roof_y - 0.25,
                "w": roof_w + 0.5,
                "h": roof_h / 2 + 0.25,
                "z": 2.92,
                "angle": 24,
                "tilt": "north",
                "color": "#9f4b2e",
                "opacity": 0.88,
            },
            {
                "id": f"{design.key}-roof-south",
                "type": "roof",
                "floorId": f"{design.key}-upper",
                "name": "South roof slope",
                "x": roof_x - 0.25,
                "y": roof_y + roof_h / 2,
                "w": roof_w + 0.5,
                "h": roof_h / 2 + 0.25,
                "z": 2.92,
                "angle": 24,
                "tilt": "south",
                "color": "#a95535",
                "opacity": 0.86,
            },
        ]
    plan = {
        "version": 1,
        "projectName": design.key,
        "source": "Architect DWG, centimetre scale",
        "scale": 52,
        "wallHeight": 2.8,
        "splitRatio": 0.58,
        "activeFloorId": ground_id,
        "viewFloor": "all",
        "view": {key: 1 for key in ("floor", "room", "spaces", "walls", "stairs", "windows", "doors", "elements", "roof", "boundary")},
        "camera": {"position": {"x": 35, "y": 15, "z": 31}, "yaw": 3.92, "pitch": -0.42},
        "floors": floors,
        "boundaries": boundaries,
        "rooms": rooms,
        "stairs": stairs,
        "walls": walls,
        "openings": openings,
        "elements": elements if design.key.startswith("architect-alt-4") else base_site_elements(design, ground_id),
        "rulers": [],
        "roofs": roofs,
    }
    if design.key.startswith("architect-alt-4"):
        plan["scale"] = 24
        plan["wallHeight"] = 2.79
        plan["camera"] = {"position": {"x": 20, "y": 14, "z": 22}, "yaw": 3.92, "pitch": -0.38}
        transform_alt4_to_saved_site(plan, design, site_plan, landscape_plan)
        validate_alt4_plan(plan)
    return plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True, help="Directory containing Alt-3.dxf, Alt-4.dxf and Alt-5.dxf")
    parser.add_argument("--output-dir", type=Path, default=Path("plans"))
    parser.add_argument(
        "--site-plan",
        type=Path,
        default=Path("plans/house_3d_view_alt4_ron_limor_yahal.json"),
        help="Saved Alt 4 scene whose external property objects should be reused",
    )
    parser.add_argument(
        "--landscape-plan",
        type=Path,
        default=Path("plans/ruchama_20_v01_2026_05_30.json"),
        help="Saved GitHub plan containing the grass, pool and ninja equipment",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    site_plan = json.loads(args.site_plan.read_text(encoding="utf-8")) if args.site_plan.exists() else None
    landscape_plan = json.loads(args.landscape_plan.read_text(encoding="utf-8")) if args.landscape_plan.exists() else None
    for design in DESIGNS:
        plan = build_plan(design, args.source_dir, site_plan, landscape_plan)
        output_path = args.output_dir / f"{design.key}.json"
        output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            f"{design.label}: {len(plan['walls'])} walls, "
            f"{len(plan['openings'])} openings, {len(plan['floors'])} floors"
        )


if __name__ == "__main__":
    main()
