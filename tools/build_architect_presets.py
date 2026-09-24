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
        "color": "#fefdfa",
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
        (18.210, 8.963, 0.65, "Salon entrance corner full-height window", 90),
        (24.330, 13.063, 0.95, "East window", 90),
        (11.510, 9.713, 3.85, "Window above kitchen work surface", 0),
        (14.885, 9.713, 0.80, "Guest toilet privacy window", 0),
        (11.112, 14.690, 1.23, "Ground window 5", 0),
        (19.235, 15.813, 2.55, "Salon south full-height window", 90),
        (8.710, 16.138, 0.60, "South-west window", 90),
    ),
    "living": (
        (16.435, 8.413, 0.90, "Living north window 1", 0),
        (17.935, 8.413, 0.90, "Living north window 2", 0),
        (24.330, 8.813, 1.05, "Living east window 1", 90),
        (20.160, 8.938, 0.80, "Living upper east window", 90),
        (14.110, 9.038, 0.90, "Living upper hall window", 90),
        (13.185, 9.713, 0.80, "Living north return window", 0),
        (11.185, 9.713, 1.00, "Living window 3", 0),
        (8.685, 10.288, 0.80, "Living west window", 90),
        (14.180, 10.288, 0.90, "Living window 4", 90),
        (8.135, 10.988, 0.90, "Living west return window", 0),
        (24.330, 13.358, 1.00, "Living east window 2", 90),
        (20.985, 15.538, 1.60, "Living lower west window", 90),
        (7.560, 16.588, 0.80, "Living south-west window", 90),
        (21.435, 17.190, 0.70, "Living south window", 0),
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
    for index, hint in enumerate(ALT4_WINDOW_HINTS.get(sheet.key, ()), start=1):
        x, y, width, name, *rotation_hint = hint
        privacy_window = "privacy" in name.lower()
        if rotation_hint:
            position = (x, y)
            rotation = rotation_hint[0]
        else:
            snapped = None if privacy_window else nearest_wall((x, y), centerlines)
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
            "height": 2.35 if full_height else 0.65 if privacy_window else 1.2,
            "sill": 0.15 if full_height else 1.75 if privacy_window else 0.9,
            "color": "#45a9d8",
            "opacity": 0.62,
        })
    return windows


def alt4_window_host_walls(design: Design, sheet: Sheet, windows: list[dict]) -> list[dict]:
    """Restore wall spans omitted by CAD window gaps so 3D can cut each opening."""
    walls = []
    for index, window in enumerate(windows, start=1):
        thickness = 0.20
        width = float(window["width"])
        host_width = 1.10 if "privacy" in window["name"].lower() else width
        walls.append({
            "id": f"{design.key}-{sheet.key}-window-host-{index}",
            "type": "wall",
            "floorId": f"{design.key}-{sheet.key}",
            "name": f"{window['name']} wall",
            "x": round_number(float(window["x"]) - host_width / 2),
            "y": round_number(float(window["y"]) - thickness / 2),
            "w": round_number(host_width),
            "h": thickness,
            "height": {"basement": 2.23, "ground": 2.79, "living": 2.75, "floor2": 2.05}.get(sheet.key, 2.8),
            "rotation": window["rotation"],
            "color": "#ffffff",
            "opacity": 0.95,
            "groupId": f"{design.key}-{sheet.key}-structure",
        })
    return walls


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
            "color": "#4a2c1b" if exterior else "#f3ead7",
            "opacity": 0.96 if exterior else 0.9,
        })
    return doors


ALT4_BLOCK_ELEMENTS = {
    "BED": ("bed", "Bed", 0.75, "#94a3b8"),
    "CH": ("chair", "Chair", 0.90, "#8ab17d"),
    "SOFA-60": ("sofa", "Sofa", 0.82, "#b7846f"),
    "SOFA-CRN": ("corner-sofa", "Corner sofa", 0.82, "#b7846f"),
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
            "elevation": 0.18 if block_name == "BLMLT" else 0,
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
        ("table", "Living room coffee table", 20.45, 11.58, 1.08, 0.62, 0.48, "#b08968"),
        ("toilet", "Guest toilet", 14.48, 9.86, 0.65, 0.80, 0.75, "#e8edf2"),
        ("sink", "Guest toilet sink", 14.48, 11.25, 0.65, 0.40, 0.85, "#70b7c8"),
    ),
    "living": (
        ("bed", "Master bedroom bed", 9.13, 14.89, 2.00, 2.10, 0.75, "#94a3b8"),
        ("wall-art", "Master bedroom waterfall artwork", 9.00, 13.87, 2.70, 0.08, 1.22, "#ffffff"),
        ("bed", "Bedroom bed 1", 14.27, 8.58, 1.20, 2.00, 0.75, "#94a3b8"),
        ("bed", "Bedroom bed 2", 18.78, 8.59, 1.20, 2.00, 0.75, "#94a3b8"),
        ("closet", "Bedroom 1 closet", 14.23, 12.04, 1.80, 0.60, 2.10, "#8b6145"),
        ("closet", "Bedroom 2 closet", 18.23, 12.04, 1.80, 0.60, 2.10, "#8b6145"),
        ("study-desk", "Bedroom 1 study desk", 16.40, 9.28, 0.65, 1.60, 0.78, "#b08968"),
        ("study-desk", "Bedroom 2 study desk", 17.21, 9.28, 0.65, 1.60, 0.78, "#b08968"),
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
            "color": "#f3ead7" if kind == "door" else "#45a9d8",
            "opacity": 0.9 if kind == "door" else 0.62,
        })
    return openings


def alt4_manual_elements(design: Design, sheet: Sheet) -> list[dict]:
    elements = []
    for index, (kind, name, x, y, width, depth, height, color) in enumerate(ALT4_MANUAL_ELEMENTS.get(sheet.key, ()), start=1):
        elevation = 1.25 if kind == "wall-art" else 0
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
            "elevation": elevation,
            "height": height,
            "rotation": 0,
            "color": color,
            "opacity": 0.9,
        })
    return elements


def alt4_sink_mirrors(design: Design, sheet: Sheet, centerlines, elements: list[dict]) -> list[dict]:
    mirrors = []
    sinks = [
        element for element in elements
        if element.get("elementKind") == "sink" and not element.get("name", "").lower().startswith("kitchen sink")
    ]
    for index, sink in enumerate(sinks, start=1):
        sink_center = (sink["x"] + sink["w"] / 2, sink["y"] + sink["h"] / 2)
        snapped = nearest_wall(sink_center, centerlines, 1.2)
        if not snapped:
            continue
        _, projected, _, _, _, _, wall_angle, _ = snapped
        toward_sink = (sink_center[0] - projected[0], sink_center[1] - projected[1])
        distance = math.hypot(*toward_sink)
        if distance > 1e-6:
            room_normal = (toward_sink[0] / distance, toward_sink[1] / distance)
        else:
            radians = math.radians(wall_angle)
            room_normal = (math.sin(radians), -math.cos(radians))
        front_normal = (
            math.sin(math.radians(wall_angle)),
            -math.cos(math.radians(wall_angle)),
        )
        rotation = wall_angle if front_normal[0] * room_normal[0] + front_normal[1] * room_normal[1] >= 0 else wall_angle + 180
        center = (projected[0] + room_normal[0] * 0.07, projected[1] + room_normal[1] * 0.07)
        width = max(0.55, min(1.2, sink["w"] * 1.05))
        depth = 0.08
        mirrors.append({
            "id": f"{design.key}-{sheet.key}-sink-mirror-{index}",
            "type": "element",
            "floorId": f"{design.key}-{sheet.key}",
            "name": f"{sink['name']} mirror",
            "elementKind": "mirror",
            "x": round_number(center[0] - width / 2),
            "y": round_number(center[1] - depth / 2),
            "w": round_number(width),
            "h": depth,
            "elevation": 1.05,
            "height": 0.8,
            "rotation": round_number(rotation % 360, 2),
            "color": "#b9d5df",
            "opacity": 0.94,
        })
    return mirrors


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
            "floorId": f"{design.key}-floor2",
            "name": "Lower wing flat roof",
            "x": 7.44,
            "y": 8.29,
            "w": 6.91,
            "h": 9.00,
            "z": -0.03,
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
            "x": 14.35,
            "y": 8.29,
            "w": 9.99,
            "h": 9.00,
            "z": 2.02,
            "rise": 2.00,
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


def repair_alt4_ground_kitchen_wall(plan: dict, design: Design) -> None:
    """Join the CAD window gaps into one exterior wall with two cutouts."""
    ground_id = f"{design.key}-ground"
    wall_left = 5.415
    wall_right = 12.495
    wall_center_y = 8.077

    def belongs_to_recovered_span(wall: dict) -> bool:
        if wall.get("floorId") != ground_id:
            return False
        rotation = float(wall.get("rotation", 0)) % 180
        if min(rotation, abs(rotation - 180)) > 2:
            return False
        center_y = float(wall.get("y", 0)) + float(wall.get("h", 0)) / 2
        if abs(center_y - wall_center_y) > 0.08:
            return False
        left = float(wall.get("x", 0))
        right = left + float(wall.get("w", 0))
        return right > wall_left and left < wall_right

    plan["walls"] = [wall for wall in plan.get("walls", []) if not belongs_to_recovered_span(wall)]
    plan["walls"].append({
        "id": f"{ground_id}-kitchen-wc-exterior-wall",
        "type": "wall",
        "floorId": ground_id,
        "name": "Kitchen and guest toilet exterior wall",
        "x": wall_left,
        "y": 7.952,
        "w": round_number(wall_right - wall_left),
        "h": 0.25,
        "height": 2.79,
        "rotation": 0,
        "color": "#fefdfa",
        "opacity": 0.95,
        "groupId": f"{ground_id}-structure",
    })


def repair_alt4_kitchen_dining_window(plan: dict, design: Design) -> None:
    """Restore the wall and floor-level sliding glass door to outdoor dining."""
    ground_id = f"{design.key}-ground"
    wall_name = "Kitchen to outdoor dining window wall"
    legacy_window_name = "Kitchen movable window to outdoor dining"
    door_name = "Kitchen sliding glass door to outdoor dining"
    wall_center_x = 12.495
    wall_bottom = 4.152
    wall_top = 6.552
    wall_length = wall_top - wall_bottom
    wall_thickness = 0.28
    wall_center_y = (wall_bottom + wall_top) / 2

    plan["walls"] = [wall for wall in plan["walls"] if wall.get("name") != wall_name]
    plan["openings"] = [
        opening for opening in plan["openings"]
        if opening.get("name") not in {legacy_window_name, door_name}
    ]
    plan["walls"].append({
        "id": f"{ground_id}-kitchen-outdoor-dining-window-wall",
        "type": "wall",
        "floorId": ground_id,
        "name": wall_name,
        "x": round_number(wall_center_x - wall_length / 2),
        "y": round_number(wall_center_y - wall_thickness / 2),
        "w": round_number(wall_length),
        "h": wall_thickness,
        "height": 2.79,
        "rotation": 270,
        "color": "#ffffff",
        "opacity": 0.95,
        "groupId": f"{ground_id}-structure",
    })
    add_alt4_opening(
        plan, design, "ground", door_name, "door",
        x=wall_center_x, y=wall_center_y, width=2.10, height=2.35,
        sill=0, rotation=270, color="#45a9d8", opacity=0.62,
        openingStyle="sliding", glass=True,
    )


def orient_alt4_kitchen_cabinets(plan: dict, design: Design) -> None:
    ground_id = f"{design.key}-ground"
    for element in plan.get("elements", []):
        if element.get("floorId") != ground_id:
            continue
        if element.get("name") == "Kitchen work surface":
            # The renderer places cabinet fronts on local -Z. In the final
            # site orientation, rotation 0 points those fronts into the room.
            element.update({
                "rotation": 0,
                "color": "#15171a",
                "type1": "black-navy-gold",
            })
        elif element.get("name") == "Kitchen work surface return":
            center_x = float(element["x"]) + float(element["w"]) / 2
            center_y = float(element["y"]) + float(element["h"]) / 2
            element["w"], element["h"] = element["h"], element["w"]
            element["x"] = round_number(center_x - float(element["w"]) / 2)
            element["y"] = round_number(center_y - float(element["h"]) / 2)
            element.update({
                "rotation": 270,
                "color": "#15171a",
                "type1": "black-navy-gold",
            })
        elif element.get("name") == "Kitchen sink 1":
            # Keep the tap on the wall side so its spout faces the kitchen.
            element["rotation"] = 180
        elif element.get("name") == "Kitchen island":
            element["type1"] = "dark-wood-top"
        elif element.get("name") == "Kitchen storage":
            element.update({
                "name": "Pantry north closets",
                "x": 8.30,
                "y": 2.40,
                "w": 3.20,
                "h": 0.70,
                "height": 2.50,
                "rotation": 0,
                "type1": "kitchen-tall-storage",
            })
        elif element.get("name") == "Pantry storage":
            element.update({
                "name": "Pantry south closets",
                "x": 8.08,
                "y": 0.772,
                "w": 4.15,
                "h": 0.60,
                "rotation": 180,
            })
    refrigerator = next((element for element in plan["elements"] if element.get("name") == "Kitchen pantry refrigerator"), None)
    refrigerator_values = {
        "elementKind": "refrigerator",
        "x": 9.60,
        "y": 3.20,
        "w": 1.10,
        "h": 0.60,
        "elevation": 0,
        "height": 2.45,
        "rotation": 180,
        "color": "#d8dee8",
        "opacity": 1.0,
    }
    if refrigerator is None:
        refrigerator = {
            "id": f"{ground_id}-kitchen-pantry-refrigerator",
            "type": "element",
            "floorId": ground_id,
            "name": "Kitchen pantry refrigerator",
        }
        plan["elements"].append(refrigerator)
    refrigerator.update(refrigerator_values)

    # The saved planner layout divides the pantry return into two tall-storage
    # bays around the refrigerator. Keep them as semantic, repeatable parts of
    # the pantry assembly rather than UI-created copies with random ids.
    for name, x in (("Pantry west tall closet", 8.30), ("Pantry east tall closet", 10.30)):
        closet = next((element for element in plan["elements"] if element.get("name") == name), None)
        closet_values = {
            "elementKind": "closet",
            "x": x,
            "y": 3.20,
            "w": 1.29,
            "h": 0.58,
            "elevation": 0,
            "height": 2.50,
            "rotation": 180,
            "color": "#9c8269",
            "opacity": 0.9,
            "type1": "kitchen-tall-storage",
        }
        if closet is None:
            closet = {
                "id": f"{ground_id}-{name.lower().replace(' ', '-')}",
                "type": "element",
                "floorId": ground_id,
                "name": name,
            }
            plan["elements"].append(closet)
        closet.update(closet_values)


def apply_alt4_saved_layout_updates(plan: dict, design: Design) -> None:
    """Apply verified planner-coordinate edits after the shared DWG transform."""
    stair_updates = {
        "basement": {"x": 5.30, "y": 0.50, "w": 2.50, "h": 3.30, "turn": "right", "landing": 1.10, "rotation": -90, "height": 2.80},
        "ground": {"x": 5.20, "y": 0.40, "w": 2.50, "h": 3.30, "turn": "right", "landing": 1.00, "rotation": -90, "height": 2.80},
    }
    for stair in plan["stairs"]:
        floor_key = stair["floorId"].rsplit("-", 1)[-1]
        if floor_key in stair_updates:
            stair.update(stair_updates[floor_key])


def add_alt4_element(plan: dict, design: Design, floor_key: str, name: str, kind: str, **values) -> None:
    floor_id = f"{design.key}-{floor_key}"
    plan["elements"].append({
        "id": f"{floor_id}-{name.lower().replace(' ', '-')}",
        "type": "element",
        "floorId": floor_id,
        "name": name,
        "elementKind": kind,
        "x": values.pop("x"),
        "y": values.pop("y"),
        "w": values.pop("w"),
        "h": values.pop("h"),
        "elevation": values.pop("elevation", 0),
        "height": values.pop("height"),
        "rotation": values.pop("rotation", 0),
        "color": values.pop("color"),
        "opacity": values.pop("opacity", 0.9),
        **values,
    })


def add_alt4_opening(plan: dict, design: Design, floor_key: str, name: str, kind: str, **values) -> None:
    floor_id = f"{design.key}-{floor_key}"
    plan["openings"].append({
        "id": f"{floor_id}-{name.lower().replace(' ', '-')}",
        "type": kind,
        "floorId": floor_id,
        "roomId": None,
        "wallId": None,
        "name": name,
        "side": "free",
        "t": 0.5,
        "x": values.pop("x"),
        "y": values.pop("y"),
        "rotation": values.pop("rotation"),
        "width": values.pop("width"),
        "height": values.pop("height"),
        "sill": values.pop("sill", 0),
        "swing": values.pop("swing", 0),
        "color": values.pop("color"),
        "opacity": values.pop("opacity", 0.9),
        **values,
    })


def repair_alt4_ground_living_room(plan: dict, design: Design) -> None:
    ground_id = f"{design.key}-ground"
    false_windows = {
        "North picture window",
        "Salon east upper full-height window",
        "East full-height window",
    }
    plan["openings"] = [
        opening for opening in plan["openings"]
        if not (opening.get("floorId") == ground_id and opening.get("name") in false_windows)
    ]
    for opening in plan["openings"]:
        if opening.get("floorId") == ground_id and opening.get("name") == "East window":
            opening["x"] = -3.105
        if opening.get("floorId") == ground_id and opening.get("name") in {
            "Salon entrance corner full-height window",
            "Salon south full-height window",
        }:
            opening["openingStyle"] = "sliding"

    # Replace fragmented sill/lintel traces with the actual CAD wall runs while
    # preserving the open exterior corner between the sofa and TV wall.
    def is_living_exterior_fragment(wall: dict) -> bool:
        if wall.get("floorId") != ground_id or wall.get("context"):
            return False
        rotation = float(wall.get("rotation", 0)) % 180
        cx = float(wall.get("x", 0)) + float(wall.get("w", 0)) / 2
        cy = float(wall.get("y", 0)) + float(wall.get("h", 0)) / 2
        horizontal = min(rotation, abs(rotation - 180)) < 2 and 8.95 < cy < 9.55 and -3.5 < cx < 4.5
        vertical = abs(rotation - 90) < 2 and -3.8 < cx < -2.7 and 3.3 < cy < 9.7
        return horizontal or vertical

    plan["walls"] = [wall for wall in plan["walls"] if not is_living_exterior_fragment(wall)]
    plan["walls"].extend((
        {
            "id": f"{ground_id}-salon-wall-behind-sofa",
            "type": "wall", "floorId": ground_id, "name": "Salon wall behind sofa",
            "x": 0.295, "y": 9.277, "w": 2.725, "h": 0.25, "height": 2.79,
            "rotation": 0, "color": "#ffffff", "opacity": 0.95,
            "groupId": f"{ground_id}-structure",
        },
        {
            "id": f"{ground_id}-salon-east-tv-wall",
            "type": "wall", "floorId": ground_id, "name": "Salon east TV wall",
            "x": -4.505, "y": 6.577, "w": 2.80, "h": 0.25, "height": 2.79,
            "rotation": 270, "color": "#ffffff", "opacity": 0.95,
            "groupId": f"{ground_id}-structure",
        },
        {
            "id": f"{ground_id}-salon-east-lower-wall",
            "type": "wall", "floorId": ground_id, "name": "Salon east lower exterior wall",
            "x": -3.405, "y": 3.827, "w": 0.60, "h": 0.25, "height": 2.79,
            "rotation": 270, "color": "#ffffff", "opacity": 0.95,
            "groupId": f"{ground_id}-structure",
        },
    ))

    for element in plan["elements"]:
        if element.get("floorId") == ground_id and element.get("name") == "Corner sofa 1":
            element["rotation"] = 180

    plan["elements"] = [
        element for element in plan["elements"]
        if not (element.get("floorId") == ground_id and element.get("name") == "Salon exterior-wall television")
    ]
    add_alt4_element(
        plan, design, "ground", "Salon exterior-wall television", "television",
        x=-3.815, y=6.662, w=1.75, h=0.08, elevation=0.95, height=1.02,
        rotation=90, color="#111827", opacity=1.0, type1="wall-mounted",
    )

    add_alt4_element(
        plan, design, "ground", "Living room rug", "rug",
        x=-2.05, y=5.40, w=4.45, h=3.35, height=0.035,
        color="#b9a58e", opacity=0.82,
    )
    rug = plan["elements"].pop()
    plan["elements"].insert(0, rug)
    add_alt4_element(
        plan, design, "ground", "Guest bathroom botanical wallpaper", "wallpaper",
        x=5.945, y=6.985, w=1.65, h=0.01, elevation=0.04, height=2.65,
        rotation=270, color="#eee6d8", opacity=0.98,
    )
    for opening in plan["openings"]:
        if opening.get("floorId") == ground_id and opening.get("name") == "Guest toilet door":
            opening.update({"swing": 180, "hingeSide": 1})
    for element in plan["elements"]:
        if element.get("floorId") == ground_id and element.get("name") == "Guest toilet sink":
            # The vanity back sits on the recovered bathroom wall's inner face.
            element["y"] = 6.012


def repair_alt4_living_floor(plan: dict, design: Design) -> None:
    living_id = f"{design.key}-living"
    # This short vertical trace is the front edge of an exploded wardrobe,
    # not a room-height partition. Leaving it as a wall blocks the walk-in's
    # dimensioned 0.90 m aisle.
    plan["walls"] = [
        wall for wall in plan["walls"]
        if not (
            wall.get("floorId") == living_id
            and wall.get("name") in {"CAD wall 18", "CAD wall 30"}
        )
    ]
    plan["walls"].append({
        "id": f"{living_id}-master-walk-in-entrance-wall",
        "type": "wall",
        "floorId": living_id,
        "name": "Master walk-in closet entrance wall",
        "x": 6.20,
        "y": 3.94,
        "w": 2.59,
        "h": 0.12,
        "height": 2.75,
        "rotation": 0,
        "color": "#ffffff",
        "opacity": 1.0,
        "groupId": f"{living_id}-structure",
    })
    plan["walls"].append({
        "id": f"{living_id}-master-bedroom-artwork-wall",
        "type": "wall",
        "floorId": living_id,
        "name": "Master bedroom waterfall artwork wall",
        "x": 12.495,
        "y": 4.63,
        "w": 2.35,
        "h": 0.20,
        "height": 2.75,
        "rotation": 270,
        "color": "#ffffff",
        "opacity": 1.0,
        "groupId": f"{living_id}-structure",
    })
    for wall in plan["walls"]:
        if wall.get("floorId") == living_id and not wall.get("context"):
            wall["color"] = "#fefdfa"
            wall["opacity"] = 1.0

    # The source has several overlapping swing arcs. Replace those detections
    # with one opening for each actual room doorway.
    plan["openings"] = [
        opening for opening in plan["openings"]
        if not (opening.get("floorId") == living_id and opening.get("type") == "door")
    ]
    cream = "#f3ead7"
    for name, x, y, width, rotation, swing in (
        ("Bedroom 1 door", 4.625, 5.102, 0.85, 180, 0),
        ("Bedroom 2 door", 3.575, 5.102, 0.85, 180, 180),
        ("Living bathroom door", 8.20, 5.102, 0.80, 180, 0),
        ("Master walk-in closet door", 7.15, 3.995, 1.00, 0, 180),
    ):
        add_alt4_opening(
            plan, design, "living", name, "door",
            x=x, y=y, width=width, height=2.10, rotation=rotation,
            swing=swing, color=cream, opacity=0.94,
        )
    add_alt4_opening(
        plan, design, "living", "Master bathroom translucent door", "door",
        x=11.33, y=5.995, width=0.78, height=2.10, rotation=0,
        swing=180, color="#ffffff", opacity=0.50, openingStyle="translucent",
    )

    living_by_name = {
        element.get("name"): element
        for element in plan["elements"]
        if element.get("floorId") == living_id
    }
    living_bath = living_by_name.get("Bath 1")
    if living_bath:
        living_bath.update({
            "name": "Living bathroom bath",
            "x": 7.12,
            "y": 5.20,
            "w": 0.70,
            "h": 1.70,
            "rotation": 180,
        })
    living_sink = living_by_name.get("Sink 1")
    if living_sink:
        living_sink.update({
            "name": "Living bathroom sink with storage",
            "x": 7.91,
            "y": 5.37,
            "w": 0.62,
            "h": 0.36,
            "rotation": 90,
        })
    living_mirror = living_by_name.get("Sink 1 mirror")
    if living_mirror:
        living_mirror.update({
            "name": "Living bathroom sink mirror",
            "x": 8.03,
            "y": 5.51,
            "w": 0.63,
            "h": 0.08,
            "rotation": 270,
        })
    add_alt4_element(
        plan, design, "living", "Living bathroom toilet", "toilet",
        x=7.84, y=6.20, w=0.62, h=0.76, height=0.75,
        rotation=90, color="#ffffff", opacity=0.98,
    )
    add_alt4_element(
        plan, design, "living", "Living bathroom laundry closet", "laundry-closet",
        x=7.10, y=7.15, w=1.24, h=0.70, height=2.50,
        rotation=0, color="#a9825f", opacity=0.97,
    )
    master_bed = living_by_name.get("Master bedroom bed")
    if master_bed:
        master_bed.update({"x": 10.10, "y": 0.85, "w": 2.0, "h": 2.10, "rotation": 270})
    artwork = living_by_name.get("Master bedroom waterfall artwork")
    if artwork:
        # The bed faces east after the saved-site rotation. Keep the wide
        # waterfall print on the solid wall band beyond the porch window.
        artwork.update({"x": 12.40, "y": 4.69, "w": 2.20, "h": 0.06, "rotation": 270, "elevation": 1.20})

    add_alt4_element(
        plan, design, "living", "Master bedroom neighbor-wall wallpaper", "wallpaper",
        x=9.15, y=0.68, w=4.00, h=0.01, elevation=0.04, height=2.65,
        rotation=180, color="#eadfd5", opacity=0.98, type1="embracing-leaves",
    )
    for wall in plan["walls"]:
        if wall.get("floorId") == living_id and wall.get("name") == "CAD wall 11":
            # The child-room clear span is dimensioned 285 cm in the source.
            wall["w"] = 2.85
    add_alt4_element(
        plan, design, "living", "Master walk-in closet west bank", "open-closet",
        x=4.85, y=2.10, w=3.25, h=0.45, height=2.68,
        rotation=90, color="#9b7653", opacity=0.96,
    )
    add_alt4_element(
        plan, design, "living", "Master walk-in closet east bank", "open-closet",
        x=6.275, y=2.025, w=3.25, h=0.60, height=2.68,
        rotation=270, color="#9b7653", opacity=0.96,
    )

    # The master bathroom is the 2.90 x 1.85 m enclosure at the north-east
    # corner after the whole-house rotation. The shower occupies the full
    # west bay; the vanity follows it along the south wall, and the toilet is
    # immediately east of the entrance facing back toward the shower.
    master_sink = living_by_name.get("Sink 2")
    if master_sink:
        master_sink.update({
            "name": "Master bathroom drawer vanity",
            "x": 10.70,
            "y": 7.42,
            "w": 1.10,
            "h": 0.50,
            "rotation": 0,
            "type1": "drawer-vanity",
        })
    master_mirror = living_by_name.get("Sink 2 mirror")
    if master_mirror:
        master_mirror.update({
            "name": "Master bathroom vanity mirror",
            "x": 10.70,
            "y": 7.86,
            "w": 1.10,
            "h": 0.08,
            "rotation": 0,
        })
    add_alt4_element(
        plan, design, "living", "Master bathroom dual shower", "shower",
        x=9.165, y=6.55, w=1.75, h=0.88, height=2.35,
        rotation=90, color="#9bd5e5", opacity=0.92, type1="dual-rain",
    )
    add_alt4_element(
        plan, design, "living", "Master bathroom movable glass partition", "sliding-window-opening",
        x=9.635, y=6.95, w=1.75, h=0.08, elevation=0.08, height=2.12,
        rotation=90, color="#9bdff0", opacity=0.52, type1="shower-partition",
    )
    add_alt4_element(
        plan, design, "living", "Master bathroom toilet", "toilet",
        x=11.62, y=6.11, w=0.62, h=0.78, height=0.75,
        rotation=90, color="#ffffff", opacity=0.98,
    )

    plan["openings"] = [
        opening for opening in plan["openings"]
        if not (opening.get("floorId") == living_id and opening.get("name") == "Living south-west window")
    ]
    add_alt4_opening(
        plan, design, "living", "Master bedroom sliding window to porch", "window",
        x=13.67, y=2.30, width=2.40, height=2.30, sill=0.10,
        rotation=270, color="#45a9d8", opacity=0.62,
        openingStyle="sliding",
    )


def normalize_alt4_architectural_walls(plan: dict) -> None:
    """Apply the 90-percent-white, 10-percent-cream architectural finish."""
    for wall in plan.get("walls", []):
        if wall.get("type") == "wall" and not wall.get("context"):
            wall["color"] = "#fefdfa"
            wall["opacity"] = 1.0


def close_alt4_main_entrance(plan: dict, design: Design) -> None:
    ground_id = f"{design.key}-ground"
    doors = sorted(
        (
            opening for opening in plan.get("openings", [])
            if opening.get("floorId") == ground_id
            and str(opening.get("name", "")).startswith("Front door")
        ),
        key=lambda opening: float(opening["x"]),
    )
    if len(doors) != 2:
        return
    center = sum(float(door["x"]) for door in doors) / 2
    nearby_walls = [
        wall for wall in plan.get("walls", [])
        if wall.get("floorId") == ground_id
        and abs(float(wall.get("y", 0)) + float(wall.get("h", 0)) / 2 - float(doors[0]["y"])) < 0.3
        and abs(float(wall.get("rotation", 0)) % 180) < 2
    ]
    left_edges = [
        float(wall["x"]) + float(wall["w"])
        for wall in nearby_walls
        if float(wall["x"]) + float(wall["w"]) <= center
    ]
    right_edges = [
        float(wall["x"])
        for wall in nearby_walls
        if float(wall["x"]) >= center
    ]
    outer_left = max(left_edges, default=min(float(door["x"]) - float(door["width"]) / 2 for door in doors))
    outer_right = min(right_edges, default=max(float(door["x"]) + float(door["width"]) / 2 for door in doors))
    if not 1.2 <= outer_right - outer_left <= 3.0:
        return
    leaf_width = (outer_right - outer_left) / 2
    for index, door in enumerate(doors):
        door["x"] = round_number(outer_left + leaf_width * (index + 0.5))
        door["width"] = round_number(leaf_width)
        door["color"] = "#4a2c1b"
        door["opacity"] = 0.96


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
    repair_alt4_ground_kitchen_wall(plan, design)
    repair_alt4_kitchen_dining_window(plan, design)
    orient_alt4_kitchen_cabinets(plan, design)
    apply_alt4_saved_layout_updates(plan, design)
    repair_alt4_ground_living_room(plan, design)
    repair_alt4_living_floor(plan, design)
    normalize_alt4_architectural_walls(plan)
    close_alt4_main_entrance(plan, design)

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

    required_names = {
        "Guest toilet door",
        "Guest toilet",
        "Guest toilet sink",
        "Guest toilet sink mirror",
        "Guest toilet privacy window",
        "Kitchen sliding glass door to outdoor dining",
        "Salon entrance corner full-height window",
        "Salon south full-height window",
        "Salon exterior-wall television",
        "Master bedroom bed",
        "Master bedroom waterfall artwork",
        "Guest bathroom botanical wallpaper",
        "Living room rug",
        "Pantry north closets",
        "Pantry south closets",
        "Kitchen pantry refrigerator",
        "Bedroom 1 door",
        "Bedroom 2 door",
        "Bedroom 1 closet",
        "Bedroom 2 closet",
        "Bedroom 1 study desk",
        "Bedroom 2 study desk",
        "Living bathroom door",
        "Living bathroom bath",
        "Living bathroom sink with storage",
        "Living bathroom sink mirror",
        "Living bathroom laundry closet",
        "Living bathroom toilet",
        "Living north window 1",
        "Living north window 2",
        "Living upper east window",
        "Living upper hall window",
        "Living north return window",
        "Living west return window",
        "Living lower west window",
        "Master walk-in closet door",
        "Master walk-in closet west bank",
        "Master walk-in closet east bank",
        "Master bedroom sliding window to porch",
        "Master bedroom neighbor-wall wallpaper",
        "Master bathroom translucent door",
        "Master bathroom dual shower",
        "Master bathroom movable glass partition",
        "Master bathroom drawer vanity",
        "Master bathroom vanity mirror",
        "Master bathroom toilet",
    }
    present_names = {item.get("name") for item in [*plan["openings"], *plan["elements"]]}
    missing_names = required_names - present_names
    if missing_names:
        raise ValueError(f"Missing Alt 4 guest-WC items: {sorted(missing_names)}")

    false_salon_windows = {
        "North picture window",
        "Salon east upper full-height window",
        "East full-height window",
    }
    present_false_windows = false_salon_windows & {opening.get("name") for opening in plan["openings"]}
    if present_false_windows:
        raise ValueError(f"False salon windows remain: {sorted(present_false_windows)}")
    required_salon_walls = {
        "Salon wall behind sofa",
        "Salon east TV wall",
        "Salon east lower exterior wall",
    }
    missing_salon_walls = required_salon_walls - {wall.get("name") for wall in structural_walls}
    if missing_salon_walls:
        raise ValueError(f"Missing salon wall segments: {sorted(missing_salon_walls)}")
    if "Master bedroom waterfall artwork wall" not in {wall.get("name") for wall in structural_walls}:
        raise ValueError("Missing solid master-bedroom wall behind the waterfall artwork")
    if by_name.get("Corner sofa 1", {}).get("rotation") != 180:
        raise ValueError("Corner sofa must face the salon after its 180-degree correction")
    salon_openings = {
        opening.get("name"): opening for opening in plan["openings"]
        if opening.get("name") in {
            "Salon entrance corner full-height window",
            "Salon south full-height window",
        }
    }
    if len(salon_openings) != 2 or any(
        opening.get("openingStyle") != "sliding" for opening in salon_openings.values()
    ):
        raise ValueError("Both salon glazed openings must be movable sliding windows")
    salon_tv = by_name.get("Salon exterior-wall television", {})
    if salon_tv.get("elementKind") != "television" or salon_tv.get("rotation") != 90:
        raise ValueError("Salon television must be wall-mounted on the east exterior wall and face inward")
    if abs((float(salon_tv.get("x", 0)) + float(salon_tv.get("w", 0)) / 2) - (-2.94)) > 0.03:
        raise ValueError("Salon television is detached from the east exterior wall")

    ground_floor_id = next(floor["id"] for floor in plan["floors"] if floor["id"].endswith("-ground"))
    outdoor_tables = [
        element for element in plan["elements"]
        if element.get("floorId") == ground_floor_id
        and element.get("name") in {"Garden dining table", "Garden lounge table"}
    ]
    if len(outdoor_tables) != 1 or outdoor_tables[0].get("name") != "Garden dining table":
        raise ValueError("Outdoor kitchen dining area must contain exactly one table")

    slabs = [room for room in plan["rooms"] if str(room.get("id", "")).endswith("-slab")]
    if not slabs or any(not slab.get("structuralSlab") for slab in slabs):
        raise ValueError("Architectural floor slabs must be marked as structural")
    if any(
        stair.get("color") != "#3d2418"
        or stair.get("opacity") != 1.0
        or stair.get("type1") != "dark-wood"
        for stair in plan["stairs"]
    ):
        raise ValueError("Alt 4 staircases must use the specified solid dark-wood finish")
    expected_stair_specs = {
        "basement": (5.30, 0.50, 2.50, 3.30, -90, "right", 1.10, 2.80),
        "ground": (5.20, 0.40, 2.50, 3.30, -90, "right", 1.00, 2.80),
        "living": (2.08, 0.99, 2.35, 3.25, 270, "right", 1.05, 2.75),
    }
    if len(plan["stairs"]) != 3 or any(
        stair.get("shape") != "turned"
        or tuple(float(stair.get(field, 0)) if field != "turn" else stair.get(field) for field in ("x", "y", "w", "h", "rotation", "turn", "landing", "height"))
        != expected_stair_specs[stair["floorId"].rsplit("-", 1)[-1]]
        for stair in plan["stairs"]
    ):
        raise ValueError("Alt 4 staircases must preserve their source-specific 90-degree podest orientation and turn")
    living_slab = next(slab for slab in slabs if slab["floorId"].endswith("-living"))
    flat_roof = next(roof for roof in plan["roofs"] if roof.get("name") == "Lower wing flat roof")
    barrel_roof = next(roof for roof in plan["roofs"] if roof.get("shape") == "barrel")
    tolerance = 0.01
    floor2_id = next(floor["id"] for floor in plan["floors"] if floor["id"].endswith("-floor2"))
    if flat_roof.get("floorId") != floor2_id or abs(float(flat_roof.get("z", 0)) + 0.03) > tolerance:
        raise ValueError("Lower wing roof must be owned by floor 2 at the living-ceiling elevation")
    roof_edges = (
        abs(barrel_roof["x"] - living_slab["x"]),
        abs(barrel_roof["x"] + barrel_roof["w"] - flat_roof["x"]),
        abs(flat_roof["x"] + flat_roof["w"] - living_slab["x"] - living_slab["w"]),
        abs(barrel_roof["y"] - living_slab["y"]),
        abs(flat_roof["y"] - living_slab["y"]),
        abs(barrel_roof["h"] - living_slab["h"]),
        abs(flat_roof["h"] - living_slab["h"]),
    )
    if any(offset > tolerance for offset in roof_edges):
        raise ValueError("Alt 4 roof sections must partition the covered room footprint without overhang")

    if any(wall.get("color") != "#fefdfa" for wall in structural_walls):
        raise ValueError("Alt 4 structural walls must use the 90% white / 10% cream finish")

    guest_door = next(opening for opening in plan["openings"] if opening.get("name") == "Guest toilet door")
    guest_sink = next(element for element in plan["elements"] if element.get("name") == "Guest toilet sink")
    if guest_door.get("swing") != 180 or guest_door.get("hingeSide") != 1:
        raise ValueError("Guest toilet door must open left from its host opening")
    if abs(float(guest_sink.get("y", 0)) - 6.012) > tolerance:
        raise ValueError("Guest toilet sink must be mounted against its wall")

    child_room_wall = next(
        wall for wall in plan["walls"]
        if wall.get("floorId", "").endswith("-living") and wall.get("name") == "CAD wall 11"
    )
    if abs(float(child_room_wall.get("w", 0)) - 2.85) > tolerance:
        raise ValueError("Living-floor child room wall must preserve the DWG 285 cm span")

    if abs(float(barrel_roof.get("rise", 0)) - 2.0) > tolerance:
        raise ValueError("Alt 4 barrel roof must rise exactly 2 m from base to crown")

    exterior_wall = next(
        (wall for wall in structural_walls if wall.get("name") == "Kitchen and guest toilet exterior wall"),
        None,
    )
    if not exterior_wall:
        raise ValueError("Missing continuous kitchen and guest-WC exterior wall")
    for opening_name in ("Window above kitchen work surface", "Guest toilet privacy window"):
        opening = next(item for item in plan["openings"] if item.get("name") == opening_name)
        distance = project_to_segment(
            (opening["x"], opening["y"]),
            *planner_wall_segment(exterior_wall),
        )[0]
        if distance > 0.14:
            raise ValueError(f"{opening_name} is detached from the recovered exterior wall")

    dining_wall = next(
        (wall for wall in structural_walls if wall.get("name") == "Kitchen to outdoor dining window wall"),
        None,
    )
    dining_door = next(
        opening for opening in plan["openings"]
        if opening.get("name") == "Kitchen sliding glass door to outdoor dining"
    )
    if not dining_wall:
        raise ValueError("Missing kitchen to outdoor dining window wall")
    distance = project_to_segment(
        (dining_door["x"], dining_door["y"]),
        *planner_wall_segment(dining_wall),
    )[0]
    if (
        distance > 0.14
        or dining_door.get("type") != "door"
        or dining_door.get("openingStyle") != "sliding"
        or not dining_door.get("glass")
        or abs(float(dining_door.get("sill", -1))) > 0.001
        or float(dining_door.get("height", 0)) < 2.2
    ):
        raise ValueError("Kitchen sliding glass door must be floor-level, glazed, attached, and sliding")

    if by_name["Kitchen work surface"].get("rotation") != 0:
        raise ValueError("Kitchen work surface cabinet fronts do not face inward")
    if by_name["Kitchen sink 1"].get("rotation") != 180:
        raise ValueError("Kitchen sink tap does not face inward")
    return_surface = by_name["Kitchen work surface return"]
    if return_surface.get("rotation") != 270 or return_surface["w"] <= return_surface["h"]:
        raise ValueError("Kitchen work surface return orientation is invalid")
    for surface in (by_name["Kitchen work surface"], return_surface):
        if surface.get("color") != "#15171a" or surface.get("type1") != "black-navy-gold":
            raise ValueError("Kitchen work surface is missing its 80/10/10 black, navy, and gold finish")
    if by_name["Kitchen island"].get("type1") != "dark-wood-top":
        raise ValueError("Kitchen island is missing its dark-wood countertop")

    pantry_north = by_name["Pantry north closets"]
    pantry_south = by_name["Pantry south closets"]
    pantry_refrigerator = by_name["Kitchen pantry refrigerator"]
    pantry_returns = [by_name["Pantry west tall closet"], by_name["Pantry east tall closet"]]
    if pantry_north["w"] < 3.2 or pantry_south["w"] < 4 or any(closet["w"] < 1.2 for closet in pantry_returns):
        raise ValueError("Pantry closet banks do not cover the planned wall runs")
    if pantry_north["rotation"] != 0 or pantry_south["rotation"] != 180 or any(closet["rotation"] != 180 for closet in pantry_returns):
        raise ValueError("Pantry closet fronts do not face into the pantry")
    pantry_inner_south = 0.772
    pantry_assembly = [pantry_north, pantry_south, pantry_refrigerator, *pantry_returns]
    if any(
        element["y"] < pantry_inner_south - 0.01
        or element["y"] + element["h"] > 3.80 + 0.01
        for element in pantry_assembly
    ):
        raise ValueError("Pantry closet bank extends outside the pantry wall faces")
    pantry_aisle = pantry_north["y"] - (pantry_south["y"] + pantry_south["h"])
    if pantry_aisle < 1.0:
        raise ValueError("Pantry closet banks leave less than 1 m of clear aisle")
    if (
        pantry_north.get("type1") != "kitchen-tall-storage"
        or pantry_north.get("height", 0) < 2.4
        or pantry_refrigerator.get("elementKind") != "refrigerator"
        or pantry_refrigerator.get("rotation") != 180
        or abs(pantry_refrigerator["x"] - 9.60) > 0.01
        or abs(pantry_refrigerator["y"] - 3.20) > 0.01
        or any(closet.get("type1") != "kitchen-tall-storage" for closet in pantry_returns)
    ):
        raise ValueError("Kitchen pantry storage must retain its built-in refrigerator bay")

    if any(wall.get("color") != "#fefdfa" or wall.get("opacity") != 1.0 for wall in structural_walls):
        raise ValueError("Architectural walls must preserve the white-and-cream finish")
    bedroom_doors = [opening for opening in plan["openings"] if opening.get("name") in {"Bedroom 1 door", "Bedroom 2 door"}]
    if len(bedroom_doors) != 2 or any(opening.get("color") != "#f3ead7" for opening in bedroom_doors):
        raise ValueError("Living-floor bedroom doors are incomplete or use the wrong finish")

    living_bathroom_door = next(opening for opening in plan["openings"] if opening.get("name") == "Living bathroom door")
    living_bath = by_name["Living bathroom bath"]
    living_sink = by_name["Living bathroom sink with storage"]
    living_toilet = by_name["Living bathroom toilet"]
    living_laundry = by_name["Living bathroom laundry closet"]
    if living_bath["x"] + living_bath["w"] >= living_bathroom_door["x"]:
        raise ValueError("Living bathroom bath must remain left of its door")
    if living_sink["x"] + living_sink["w"] / 2 <= living_bathroom_door["x"]:
        raise ValueError("Living bathroom sink must remain right of its door")
    if living_toilet["y"] <= living_sink["y"] + living_sink["h"]:
        raise ValueError("Living bathroom toilet must follow the sink")
    if living_laundry["y"] <= living_bath["y"] + living_bath["h"]:
        raise ValueError("Living bathroom laundry closet must follow the bath")

    master_bed = by_name["Master bedroom bed"]
    master_art = by_name["Master bedroom waterfall artwork"]
    master_wallpaper = by_name["Master bedroom neighbor-wall wallpaper"]
    if master_bed.get("rotation") != 270:
        raise ValueError("Master bed head must face the walk-in closet and its foot must face outside")
    if master_art.get("rotation") != 270 or master_art["x"] + master_art["w"] / 2 <= master_bed["x"] + master_bed["w"] / 2:
        raise ValueError("Master bedroom waterfall artwork must remain on the wall facing the bed")
    if master_wallpaper.get("type1") != "embracing-leaves":
        raise ValueError("Master bedroom wallpaper must use the detailed embracing-leaves treatment")

    west_closet = by_name["Master walk-in closet west bank"]
    east_closet = by_name["Master walk-in closet east bank"]
    closet_door = next(opening for opening in plan["openings"] if opening.get("name") == "Master walk-in closet door")
    west_center = west_closet["x"] + west_closet["w"] / 2
    east_center = east_closet["x"] + east_closet["w"] / 2
    aisle_width = east_center - west_center - west_closet["h"] / 2 - east_closet["h"] / 2
    if west_closet["w"] < 3.24 or east_closet["w"] < 3.24:
        raise ValueError("Master walk-in closet must contain two full 3.25 m banks")
    if west_closet.get("rotation") != 90 or east_closet.get("rotation") != 270:
        raise ValueError("Master walk-in closet banks must face each other")
    if min(west_closet["height"], east_closet["height"]) < 2.65 or abs(aisle_width - 0.90) > 0.03:
        raise ValueError("Master walk-in closet must be ceiling-height with a 0.90 m aisle")
    if not west_center < closet_door["x"] < east_center or closet_door.get("color") != "#f3ead7":
        raise ValueError("Master walk-in closet door must open into the aisle and use the cream finish")
    entrance_wall = next(wall for wall in plan["walls"] if wall.get("name") == "Master walk-in closet entrance wall")
    closet_front_y = min(west_closet["y"] + west_closet["h"] / 2, east_closet["y"] + east_closet["h"] / 2)
    if abs(closet_front_y - 2.325) > 0.03 or abs(entrance_wall["y"] - 3.94) > 0.03:
        raise ValueError("Master walk-in closet banks must remain registered to the DWG entry wall")
    if any(wall.get("name") == "Master suite entry wall" for wall in plan["walls"]):
        raise ValueError("Do not invent a free-standing master-suite divider from wardrobe linework")
    if any(opening.get("name") == "Master bedroom door" for opening in plan["openings"]):
        raise ValueError("The master suite uses the centered walk-in entry, not a second free-standing door")

    master_door = next(opening for opening in plan["openings"] if opening.get("name") == "Master bathroom translucent door")
    master_shower = by_name["Master bathroom dual shower"]
    master_partition = by_name["Master bathroom movable glass partition"]
    master_vanity = by_name["Master bathroom drawer vanity"]
    master_toilet = by_name["Master bathroom toilet"]
    if master_door.get("color") != "#ffffff" or abs(float(master_door.get("opacity", 0)) - 0.50) > 0.01:
        raise ValueError("Master bathroom door must be 50-percent translucent white")
    if master_shower.get("type1") != "dual-rain" or master_shower["x"] + master_shower["w"] / 2 >= master_door["x"]:
        raise ValueError("Master bathroom dual shower must occupy the bay immediately left of the door")
    if master_partition.get("type1") != "shower-partition" or master_partition.get("rotation") != 90:
        raise ValueError("Master bathroom shower requires a movable glass water partition")
    if master_vanity.get("type1") != "drawer-vanity" or master_vanity["x"] <= master_shower["x"]:
        raise ValueError("Master bathroom drawer vanity must follow the shower along the right side")
    if master_toilet["x"] + master_toilet["w"] / 2 <= master_door["x"] or master_toilet.get("rotation") != 90:
        raise ValueError("Master bathroom toilet must be after the door and face the shower")

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
        floor = {
            "id": floor_id,
            "name": sheet.label,
            "elevation": floor_elevations[sheet.key],
            "color": floor_colors[sheet.key],
        }
        if design.key.startswith("architect-alt-4"):
            floor["finish"] = "light-gray-granite" if sheet.key == "ground" else "parquet" if sheet.key == "living" else None
        floors.append(floor)
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
            "structuralSlab": True,
            "floorId": floor_id,
            "name": f"{sheet.label} slab",
            "x": slab_x,
            "y": slab_y,
            "w": slab_w,
            "h": slab_h,
            "color": "#d9dee5",
            "wallColor": "#ffffff",
            "opacity": 0.94,
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
            floor_windows = collect_alt4_windows(design, sheet, centerlines)
            floor_openings.extend(floor_windows)
            floor_openings.extend(alt4_manual_openings(design, sheet))
            floor_walls.extend(alt4_window_host_walls(design, sheet, floor_windows))
            walls.extend(floor_walls[len(centerlines):])
            openings.extend(floor_openings)
            floor_elements = collect_alt4_block_elements(modelspace, design, sheet)
            floor_elements.extend(alt4_manual_elements(design, sheet))
            elements.extend(floor_elements)
            elements.extend(alt4_sink_mirrors(design, sheet, centerlines, floor_elements))
        else:
            floor_openings = collect_doors(modelspace, design, sheet)
            floor_openings.extend(collect_windows(modelspace, design, sheet))
            openings.extend(add_reference_openings(design, sheet, floor_openings))

        top_key = "floor2" if design.key.startswith("architect-alt-4") else "upper"
        if sheet.key != top_key:
            # The yellow tread clusters share an L shape but not a common
            # compass orientation or handedness. The ground flight turns
            # left, while the living-to-floor-2 flight rotates clockwise.
            stair_specs = {
                "basement": (17.15, 13.70, 2.45, 3.25, 0, "right"),
                # The entrance flight occupies the right-hand leg of the
                # L-shaped core. Its bounding box intentionally differs from
                # the adjacent-flight boxes; verify the marked landing and
                # outgoing triangle instead of forcing box overlap.
                "ground": (13.85, 13.95, 2.55, 3.30, 0, "left"),
                "living": (16.80, 13.55, 2.35, 3.25, 90, "right"),
            }
            if design.key.startswith("architect-alt-4"):
                stair_x, stair_y, stair_w, stair_h, stair_rotation, stair_turn = stair_specs.get(sheet.key, (*design.stair, 0, "right"))
            else:
                stair_x, stair_y, stair_w, stair_h = design.stair
                stair_rotation = 0
                stair_turn = "right"
            stairs.append({
                "id": f"{floor_id}-stairs",
                "type": "stair",
                "floorId": floor_id,
                "name": f"{sheet.label} stairs",
                "x": stair_x,
                "y": stair_y,
                "w": stair_w,
                "h": stair_h,
                "shape": "turned" if design.key.startswith("architect-alt-4") else "uturn",
                "turn": stair_turn,
                "landing": 1.05,
                "rotation": stair_rotation,
                "level": 0,
                "height": 2.75 if design.key.startswith("architect-alt-4") else 2.8,
                "color": "#3d2418" if design.key.startswith("architect-alt-4") else "#6e62cf",
                "opacity": 1.0 if design.key.startswith("architect-alt-4") else 0.9,
                "type1": "dark-wood" if design.key.startswith("architect-alt-4") else None,
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
