"""Fresh Alt-4 import from verified AREA/A17/A34/A16/A12/A14/A24/A49 layers.

Run with a layer-preserving Alt-4 DXF. V1 supplies appearance only and is never overwritten.
Geometry is in metres with CAD north up in 2D. Source handles are retained.
"""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import ezdxf
from ezdxf import bbox, disassemble, path
from shapely import set_precision
from shapely.affinity import rotate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import polygonize, unary_union
from cad_text import decode_architect_text
from alt4_sections import section_constraints

KEY = "architect-alt-4-v2"
LAYERS = ("AREA", "A17", "A34", "A24", "A49", "A16", "A12", "A14", "A13")
# Handles identify verified contours, not old planner coordinates. The top
# room is a clear-area outline; its surrounding A14 platforms are separate.
FLOORS = (
    ("basement", "Basement", "101E", -2.75, "#7c3aed"),
    ("ground", "Ground floor", "1F44", 0, "#0f766e"),
    ("living", "Living floor", "1884", 3.14, "#2563eb"),
    ("floor2", "Floor 2", "D08", 5.724, "#b45309"),
)
BLOCKS = {
    "BED": ("bed", .75, "#94a3b8"), "CH": ("chair", .9, "#8ab17d"),
    "SOFA-60": ("sofa", .82, "#b7846f"), "SOFA-CRN": ("corner-sofa", .82, "#b7846f"),
    "HARSA506": ("sink", .85, "#70b7c8"), "SS01": ("toilet", .75, "#e8edf2"),
    "BATH": ("bath", .65, "#d9f0f5"),
    "BLMLT": ("sink", .9, "#70b7c8"),
}


def rounded(value):
    return round(float(value), 4)


def polygons(geometry):
    if geometry.is_empty:
        return []
    return [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)


def rects(geometry):
    """Exact orthogonal polygon tiling; never replace a stepped footprint by its bbox."""
    result = []
    for poly in polygons(set_precision(geometry, .0001)):
        if poly.geom_type != "Polygon" or poly.area < .00001:
            continue
        xs = sorted({rounded(p[0]) for ring in [poly.exterior, *poly.interiors] for p in ring.coords})
        bands = []
        for x1, x2 in zip(xs, xs[1:]):
            for part in polygons(poly.intersection(box(x1, poly.bounds[1] - 1, x2, poly.bounds[3] + 1))):
                if part.geom_type != "Polygon" or part.area < .00001:
                    continue
                bounds = tuple(rounded(v) for v in part.bounds)
                if abs(box(*bounds).area - part.area) > .003:
                    raise ValueError("Non-orthogonal contour requires polygon support; refusing bounding-box replacement")
                bands.append(bounds)
        for x1, y1, x2, y2 in sorted(bands, key=lambda b: (b[1], b[3], b[0])):
            if result and abs(result[-1][2] - x1) < .0002 and result[-1][1] == y1 and result[-1][3] == y2:
                result[-1] = (result[-1][0], y1, x2, y2)
            else:
                result.append((x1, y1, x2, y2))
    return result


def item_polygon(item):
    shape = box(item['x'], item['y'], item['x']+item['w'], item['y']+item['h'])
    return rotate(shape, item.get('rotation', 0), origin='center')


class Importer:
    def __init__(self, source):
        self.doc = ezdxf.readfile(source)
        self.model = list(self.doc.modelspace())
        self.audit = {"source": source.name, "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                      "layers": {}, "floors": {}, "assumptions": [
                          "Story elevations follow the two CAD sections; top-floor high/low zones and roof-clipped walls remain to be integrated.",
                          "Legacy SHX labels are decoded from CP1252-preserved CP862 bytes; numeric runs retain their original order.",
                      ]}
        for layer in LAYERS:
            entities = [e for e in self.model if e.dxf.layer.upper() == layer]
            self.audit["layers"][layer] = dict(Counter(e.dxftype() for e in entities))
            if not entities:
                raise ValueError(f"Missing populated {layer} layer: ask the user to identify it")
        self.plan = {"version": 1, "projectName": "Alt-4 v2 (audit preview)", "source": "Alt-4 DWG, verified layers, draft v2",
                     "scale": 45, "wallHeight": 2.79, "splitRatio": .5,
                     "activeFloorId": KEY + "-ground", "viewFloor": KEY + "-ground",
                     "camera": {"position": {"x": 24, "y": 16, "z": 24}, "yaw": 3.9, "pitch": -.48},
                     "view": {k: 1 for k in ("floor", "room", "spaces", "walls", "stairs", "windows", "doors", "elements", "roof", "boundary")},
                     **{k: [] for k in ("floors", "boundaries", "rooms", "stairs", "walls", "openings", "elements", "rulers", "roofs")}}
        self.source_floor = {}
        self.audit['sections'] = section_constraints(self.doc)
        self.wall_geometry = {}
        self.material_donor = json.loads(Path("plans/architect-alt-4-sheet-1.json").read_text(encoding="utf-8"))

    def pt(self, p):
        return (rounded((p[0] - self.origin[0]) / 100), rounded((self.origin[1] - p[1]) / 100))

    def geom(self, entity):
        if entity.dxftype() == "HATCH":
            return [Polygon([self.pt(v) for v in p.vertices]).buffer(0).simplify(.0001) for p in entity.paths if hasattr(p, "vertices")]
        if entity.dxftype() == "LWPOLYLINE" and entity.closed:
            return [Polygon([self.pt(v) for v in entity.get_points("xy")]).buffer(0)]
        return []

    def linework(self, layers):
        lines = []
        for e in self.entities:
            if e.dxf.layer.upper() not in layers:
                continue
            if e.dxftype() == "HATCH":
                lines.extend(p.boundary for p in self.geom(e))
            elif e.dxftype() in ("LINE", "LWPOLYLINE"):
                points = [self.pt(p) for p in path.make_path(e).flattening(.1)]
                lines.extend(LineString([a, b]) for a, b in zip(points, points[1:]) if math.dist(a, b) > .005)
        return lines

    def item(self, collection, handle, name, bounds, **values):
        x1, y1, x2, y2 = bounds
        item = {"id": f"{self.floor_id}-{handle}", "type": "element" if collection == "elements" else "space" if collection == "rooms" else "wall",
                "floorId": self.floor_id, "name": name, "x": rounded(x1), "y": rounded(y1),
                "w": rounded(x2 - x1), "h": rounded(y2 - y1), **values}
        self.plan[collection].append(item)
        return item

    def slab(self, geometry, name, handle, outdoor=False):
        tiles = rects(geometry)
        for i, bounds in enumerate(tiles):
            self.item("rooms", f"{handle}-slab-{i}", name if len(tiles) == 1 else f"{name} {i + 1}", bounds,
                      structuralSlab=True, ceiling=not outdoor and self.floor_key != "floor2", outdoor=outdoor,
                      color="#d9dee5", opacity=.94,
                      sourceLayer="A14 AND NOT AREA" if outdoor else "AREA", sourceHandle=handle)
        assert abs(sum(box(*r).area for r in tiles) - geometry.area) < .01, "Slab tiling changed footprint area"

    def opening(self, handle, start, end, kind, layer, thickness=.1, **values):
        length = math.dist(start, end)
        angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
        cx, cy = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
        self.plan["openings"].append({"id": f"{self.floor_id}-{handle}", "type": kind, "floorId": self.floor_id,
            "name": f"{kind.title()} {handle}", "roomId": None, "wallId": f"{self.floor_id}-{handle}-host", "side": "wall-h", "t": .5,
            "x": rounded(cx), "y": rounded(cy), "rotation": rounded(angle), "width": rounded(length),
            "height": 2.1 if kind == "door" else 1.2, "sill": 0 if kind == "door" else 1,
            "swing": 0, "color": "#f3ead7" if kind == "door" else "#45a9d8", "opacity": .9 if kind == "door" else .62,
            "sourceLayer": layer, "sourceHandle": handle, **values})
        self.item("walls", handle + "-host", f"{kind.title()} host {handle}", (cx-length/2, cy-thickness/2, cx+length/2, cy+thickness/2),
                  rotation=rounded(angle), height=self.height, color="#fefdfa", opacity=1, sourceLayer=layer,
                  sourceHandle=handle, sourceRole="gap-host")
        return LineString([start, end])

    def wall_gaps(self, walls):
        """Pair facing wall end caps, after removing collinear hatch vertices."""
        edges = []
        for poly in polygons(walls.simplify(.0002)):
            for a, b in zip(poly.exterior.coords, list(poly.exterior.coords)[1:]):
                length = math.dist(a, b)
                if not .075 <= length <= .36:
                    continue
                horizontal = abs(a[1] - b[1]) < .001
                if not horizontal and abs(a[0] - b[0]) > .001:
                    continue
                center = ((a[0]+b[0])/2, (a[1]+b[1])/2)
                normal = (0, 1) if horizontal else (1, 0)
                if walls.contains(Point(center[0]+normal[0]*.003, center[1]+normal[1]*.003)):
                    normal = (-normal[0], -normal[1])
                edges.append((center, normal, length))
        gaps = []
        for i, (a, na, ta) in enumerate(edges):
            for b, nb, tb in edges[i+1:]:
                dx, dy = b[0]-a[0], b[1]-a[1]
                if na[0]*nb[0]+na[1]*nb[1] > -.99 or dx*na[0]+dy*na[1] <= 0:
                    continue
                if abs(dx*na[1]-dy*na[0]) > .015 or abs(ta-tb) > .011:
                    continue
                segment = LineString([a, b])
                if not .4 < segment.length < 4.6 or segment.intersection(walls.buffer(-.001)).length > .01:
                    continue
                if any(segment.hausdorff_distance(g["segment"]) < .18 for g in gaps):
                    continue
                gaps.append({"segment": segment, "thickness": max(ta, tb)})
        # A door can meet a T-junction: its far jamb is a long wall face rather
        # than another short end cap. Cast from the supported cap to that face.
        solid = walls.buffer(-.00001)
        for a, normal, thickness in edges:
            ray = LineString([a, (a[0]+normal[0]*4.6, a[1]+normal[1]*4.6)])
            hit = ray.intersection(solid)
            if hit.is_empty:
                continue
            starts = [ray.project(Point(p)) for part in ([hit] if hit.geom_type == "LineString" else getattr(hit, "geoms", []))
                      if part.geom_type == "LineString" for p in part.coords]
            if not starts or not .4 < min(starts) < 4.6:
                continue
            distance = min(starts)
            b = (rounded(a[0]+normal[0]*distance), rounded(a[1]+normal[1]*distance))
            segment = LineString([a, b])
            if not any(segment.hausdorff_distance(g["segment"]) < .18 for g in gaps):
                gaps.append({"segment": segment, "thickness": thickness})
        true_gaps = []
        for gap in gaps:
            segment = gap["segment"]
            a, b = segment.coords
            nx, ny = -(b[1]-a[1])/segment.length, (b[0]-a[0])/segment.length
            recess = False
            for offset in (-.25, -.15, -.1, .1, .15, .25):
                shifted = LineString([(p[0]+nx*offset,p[1]+ny*offset) for p in (a,b)])
                if shifted.intersection(solid).length > segment.length*.9:
                    recess = True
            if not recess:
                true_gaps.append(gap)
        return true_gaps

    def aligned_openings(self, walls):
        arcs = []
        for e in self.entities:
            if e.dxf.layer.upper() != "A12":
                continue
            for i, arc in enumerate(disassemble.recursive_decompose([e])):
                if arc.dxftype() == "ARC" and 50 <= arc.dxf.radius <= 140:
                    arcs.append({"handle": e.dxf.handle, "part": i, "hinge": self.pt(arc.ocs().to_wcs(arc.dxf.center)),
                                 "radius": arc.dxf.radius/100, "tips": [self.pt(arc.start_point), self.pt(arc.end_point)]})
        frames = self.linework({"A14", "A13"})
        used_arcs, resolved, evidence = set(), [], []
        for index, gap in enumerate(self.wall_gaps(walls)):
            segment = gap["segment"]
            a, b = list(segment.coords)
            matches = []
            for i, arc in enumerate(arcs):
                distance = min(math.dist(arc["hinge"], a), math.dist(arc["hinge"], b))
                size_error = min(abs(segment.length-arc["radius"]), abs(segment.length/2-arc["radius"]))
                if distance < .22 and size_error < .23 and i not in used_arcs:
                    matches.append((i, arc))
            support = sum(segment.intersection(line.buffer(gap["thickness"]/2+.015)).length for line in frames)
            info = {"endpoints": [list(a), list(b)], "thickness": rounded(gap["thickness"]),
                    "width": rounded(segment.length), "a14Support": rounded(support),
                    "doorHandles": [arc["handle"] for _, arc in matches]}
            evidence.append(info)
            if matches:
                paired = len(matches) == 2 and segment.length > 1.4
                for n, (i, arc) in enumerate(matches[:2] if paired else matches[:1]):
                    used_arcs.add(i)
                    hinge_end, latch_end = sorted((a, b), key=lambda p: math.dist(p, arc["hinge"]))
                    if paired:
                        latch_end = ((a[0]+b[0])/2, (a[1]+b[1])/2)
                    dx, dy = latch_end[0]-hinge_end[0], latch_end[1]-hinge_end[1]
                    tip = max(arc["tips"], key=lambda p: segment.distance(Point(p)))
                    cross = dx*(tip[1]-hinge_end[1])-dy*(tip[0]-hinge_end[0])
                    self.opening(f"door-{arc['handle']}-{n}", hinge_end, latch_end, "door", "A12/A17",
                                 thickness=gap["thickness"], swing=0 if cross > 0 else 180,
                                 name="Entrance paired leaf" if paired else f"Door {arc['handle']}",
                                 color="#4a2c1b" if paired else "#f3ead7", opacity=.96 if paired else .94)
                info["classification"] = "door"
                resolved.append(segment)
            elif support > segment.length*.45 and self.window_boundary_support(segment, gap["thickness"]):
                self.opening(f"window-gap-{index}", a, b, "window", "A14/A17", thickness=gap["thickness"])
                info["classification"] = "window-candidate"
                resolved.append(segment)
            else:
                info["classification"] = "unresolved-gap"
        self.floor_audit["openingGaps"] = evidence
        self.floor_audit["unresolvedDoors"] = [arc["handle"] for i, arc in enumerate(arcs) if i not in used_arcs]
        return resolved

    def window_boundary_support(self, segment, thickness):
        boundary = self.source_floor[self.floor_key][1].boundary
        if self.floor_key == "floor2":
            boundary = self.top_floor_enclosure().boundary
        return segment.intersection(boundary.buffer(thickness+.025)).length >= segment.length*.9

    def opening_roles(self):
        master_balcony_openings = []
        if self.floor_key == 'living':
            balcony = self.source_bounds('1CBB', '1AEE', '1CD5')
        for opening in self.plan['openings']:
            if opening['floorId'] != self.floor_id:
                continue
            x,y=opening['x'],opening['y']
            if self.floor_key=='living' and opening['type']=='window' and \
                    abs(x-(balcony[2]+.125))<.05 and balcony[1]<y<balcony[3] and opening['width']>1.8:
                opening.update(type='door',name='Master bedroom balcony sliding glass door',glass=True,
                               openingStyle='sliding',height=2.35,sill=0,color='#45a9d8',opacity=.62,
                               roleEvidence='A14 balcony edges 1CBB/1AEE/1CD5 and A17 facade gap')
                master_balcony_openings.append(opening['id'])
            elif self.floor_key=='ground' and x<.2 and 2.9<y<5.4:
                opening.update(type='door',name='Kitchen exterior sliding glass door',glass=True,
                               openingStyle='sliding',height=2.35,sill=0,color='#45a9d8',opacity=.62,
                               roleEvidence='User-confirmed kitchen-to-outdoor-dining circulation')
            elif opening['type']=='window' and ((self.floor_key=='ground' and x>9.3 and y<5.8) or
                                                 (self.floor_key=='living' and x<-.9)):
                opening.update(openingStyle='sliding',roleEvidence='User-confirmed salon/master movable glazing')
            if opening['type']=='door' and not opening.get('glass') and opening['name']!='Entrance paired leaf':
                opening['opacity']=.94 if self.floor_key=='living' else .9
        if self.floor_key=='living':
            if len(master_balcony_openings) != 1:
                raise ValueError(f'Expected one master balcony access opening, found {master_balcony_openings}')
            gap=next(g for g in self.floor_audit['openingGaps'] if abs(g['width']-.78)<.001 and
                     abs(g['endpoints'][0][1]-3.45)<.001)
            self.opening('master-bathroom-entry',*gap['endpoints'],'door','A17/user-confirmed',
                         thickness=gap['thickness'],name='Master bathroom entrance',color='#fefdfa',opacity=.5,
                         openingStyle='translucent')
            gap['classification']='user-confirmed-translucent-door'

    def top_floor_enclosure(self):
        bedroom = self.geom(self.doc.entitydb["D08"])[0]
        west = self.source_bounds("1411")[0]
        east = self.source_bounds("13FD")[2]
        north = self.source_bounds("1411")[1]
        south = self.source_bounds("1409")[3]
        bedroom_shell = box(west, north, east, south)
        stair_west, stair_north, _, _ = self.source_bounds("1568")
        hall_west, hall_north, _, _ = self.source_bounds("1550")
        _, _, hall_east, floor_south = self.source_bounds("1560")
        core = Polygon([(stair_west,stair_north), (hall_west,stair_north), (hall_west,hall_north),
                        (hall_east,hall_north), (hall_east,floor_south), (stair_west,floor_south)])
        # A17 encloses a second indoor bay east of the bedroom and the bridge
        # joining it to the stair core. AREA D08 outlines only the bedroom.
        east_bay = box(self.source_bounds("13FD")[0], self.source_bounds("13F5")[1],
                       self.source_bounds("13F9")[2], self.source_bounds("1401")[3])
        bridge = box(self.source_bounds("1409")[0], self.source_bounds("1401")[1],
                     self.source_bounds("154C")[2], self.source_bounds("1564")[3])
        assert bedroom_shell.covers(bedroom)
        return unary_union([bedroom_shell, east_bay, bridge, core])

    def perimeter_openings(self, footprint, walls):
        if self.floor_key == "floor2":
            return  # Its AREA is a clear room area, not the external perimeter.
        current = [o for o in self.plan["openings"] if o["floorId"] == self.floor_id]
        used = []
        for opening in current:
            angle = math.radians(opening["rotation"])
            vx, vy = math.cos(angle)*opening["width"]/2, math.sin(angle)*opening["width"]/2
            used.append(LineString([(opening["x"]-vx,opening["y"]-vy),(opening["x"]+vx,opening["y"]+vy)]).buffer(.4))
        excluded = unary_union([walls.buffer(.0001), *used])
        for index, (a,b) in enumerate(zip(footprint.exterior.coords,list(footprint.exterior.coords)[1:])):
            missing = LineString([a,b]).difference(excluded)
            parts = [missing] if missing.geom_type == "LineString" else getattr(missing,"geoms",[])
            for n, part in enumerate(parts):
                if part.geom_type != "LineString" or part.length < .45:
                    continue
                # Do not fabricate windows at open salon circulation or the
                # staircase/courtyard edge of the selected basement alternative.
                center = part.interpolate(.5, normalized=True)
                if self.floor_key == "ground" and center.y < .05:
                    self.floor_audit.setdefault("openPassages", []).append({"bounds":list(part.bounds),"role":"salon-to-terrace"})
                    continue
                start, end = part.coords[0], part.coords[-1]
                dx,dy=end[0]-start[0],end[1]-start[1]
                nx,ny=-dy/part.length,dx/part.length
                if not footprint.contains(Point(center.x+nx*.05, center.y+ny*.05)):
                    nx,ny=-nx,-ny
                thickness=.25
                start=(rounded(start[0]+nx*thickness/2),rounded(start[1]+ny*thickness/2))
                end=(rounded(end[0]+nx*thickness/2),rounded(end[1]+ny*thickness/2))
                patio = self.floor_key == "ground" and center.x < .1 and 2.9 < center.y < 5.4
                self.opening(f"perimeter-{index}-{n}",start,end,"door" if patio else "window","AREA/A17 perimeter",thickness=thickness,
                             **({"name":"Kitchen exterior sliding glass door","glass":True,"openingStyle":"sliding",
                                 "color":"#45a9d8","opacity":.62,"height":2.35} if patio else {}))
                self.floor_audit.setdefault("inferredPerimeterWindows", []).append({"bounds":list(part.bounds),"patioDoor":patio})

    def doors(self, wall_geometry):
        gaps = []
        for e in self.entities:
            if e.dxf.layer.upper() != "A12":
                continue
            for i, arc in enumerate(disassemble.recursive_decompose([e])):
                if arc.dxftype() != "ARC" or not 50 <= arc.dxf.radius <= 140:
                    continue
                hinge = self.pt(arc.dxf.center)
                radius = arc.dxf.radius / 100
                candidates = []
                for degrees in (arc.dxf.start_angle, arc.dxf.end_angle):
                    a = math.radians(-degrees)
                    unit = (math.cos(a), math.sin(a))
                    endpoint = tuple(hinge[j] + unit[j] * radius for j in range(2))
                    beyond = tuple(hinge[j] + unit[j] * (radius + .08) for j in range(2))
                    closed = LineString([hinge, endpoint])
                    blocked = closed.intersection(wall_geometry.buffer(-.015)).length
                    score = wall_geometry.distance(Point(beyond)) + blocked * 3
                    candidates.append((score, endpoint, degrees))
                score, endpoint, degrees = min(candidates)
                if score > .35:
                    self.floor_audit.setdefault("unresolvedDoors", []).append(e.dxf.handle)
                    continue
                if any(g.distance(Point(hinge)) < .03 and abs(g.length - radius) < .02 for g in gaps):
                    continue
                gaps.append(self.opening(f"door-{e.dxf.handle}-{i}", hinge, endpoint, "door", "A12"))
        return gaps

    def windows(self, footprint, walls, doors):
        coords = list(footprint.exterior.coords)
        for i, (a, b) in enumerate(zip(coords, coords[1:])):
            edge = LineString([a, b])
            covered = unary_union([walls.buffer(.015), *[g.buffer(.08) for g in doors]])
            missing = edge.difference(covered)
            parts = [missing] if missing.geom_type == "LineString" else list(getattr(missing, "geoms", []))
            for j, segment in enumerate(parts):
                if segment.length < .35 or segment.geom_type != "LineString":
                    continue
                start, end = tuple(segment.coords[0]), tuple(segment.coords[-1])
                # Endpoints must terminate at real wall/door structure.
                if max(covered.distance(Point(start)), covered.distance(Point(end))) > .03:
                    continue
                wide = segment.length > 1.8
                self.opening(f"perimeter-{i}-{j}", start, end, "door" if wide else "window", "A14/AREA perimeter gap",
                             **({"openingStyle": "sliding", "glass": True, "height": 2.35} if wide else {}))

    def furniture(self, footprint):
        occupied = []
        for e in self.entities:
            if e.dxf.layer.upper() not in ("A34", "A16") or e.dxftype() != "INSERT":
                continue
            spec = BLOCKS.get(e.dxf.name.upper())
            if e.dxf.name.upper() == "WASH":
                # Classified from the rendered source symbol, not the block name.
                self.floor_audit.setdefault("applianceBays", []).append({"handle": e.dxf.handle, "kind": "washing-machine"})
                continue
            if not spec:
                self.floor_audit.setdefault("unclassifiedBlocks", []).append({"handle": e.dxf.handle, "name": e.dxf.name})
                continue
            ex = bbox.extents([e])
            a, b = self.pt(ex.extmin), self.pt(ex.extmax)
            x1, y1, x2, y2 = min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])
            kind, height, color = spec
            local = bbox.extents(self.doc.blocks[e.dxf.name])
            matrix = e.matrix44()
            swap = e.dxf.name.upper() in ("BED", "SOFA-60", "SS01")
            native_x = (0, 1, 0) if swap else (1, 0, 0)
            native_depth = (1, 0, 0) if swap else (0, -1, 0)
            if e.dxf.name.upper() == 'SOFA-CRN':
                native_depth = (0, 1, 0)
            vx, vz = matrix.transform_direction(native_x), matrix.transform_direction(native_depth)
            dx, dy = vz.x, -vz.y
            angle = math.degrees(math.atan2(-dx, dy)) % 360
            app_x = (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
            mirror_x = vx.x*app_x[0]-vx.y*app_x[1] < 0
            w = (local.size.y if swap else local.size.x)*vx.magnitude/100
            h = (local.size.x if swap else local.size.y)*vz.magnitude/100
            cx, cy = self.pt(matrix.transform(local.center))
            if self.floor_key == "ground" and not footprint.buffer(.05).contains(Point(cx, cy)):
                continue  # Exterior furnishings come from the authoritative external save.
            result = self.item("elements", "fixture-" + e.dxf.handle, kind.replace("-", " ").title(), (cx-w/2, cy-h/2, cx+w/2, cy+h/2),
                      elementKind=kind, rotation=rounded(angle), mirrorX=mirror_x, elevation=0, height=height, color=color, opacity=.9,
                      sourceLayer=e.dxf.layer, sourceHandle=e.dxf.handle)
            if e.dxf.name.upper() == 'BLMLT':
                result.update(name='Kitchen sink 1', rotation=0, height=.92, countertopMounted=True)
            occupied.append(box(x1, y1, x2, y2))
        self.verified_furniture()
        local = [e for e in self.plan['elements'] if e['floorId']==self.floor_id]
        for desk in (e for e in local if e['elementKind']=='study-desk'):
            shape = item_polygon(desk)
            chairs = [e for e in local if e['elementKind']=='chair' and shape.distance(item_polygon(e))<.35]
            if not chairs:
                continue
            chair = min(chairs,key=lambda e: shape.centroid.distance(item_polygon(e).centroid))
            direction = item_polygon(chair).centroid
            angle=math.radians(desk['rotation'])
            facing=(-math.sin(angle),math.cos(angle))
            if facing[0]*(direction.x-shape.centroid.x)+facing[1]*(direction.y-shape.centroid.y)<0:
                desk['rotation']=(desk['rotation']+180)%360
            desk['separateChair']=True
            desk['facingEvidence']=chair['sourceHandle']

    def source_bounds(self, *handles):
        extents = bbox.extents([self.doc.entitydb[handle] for handle in handles])
        a, b = self.pt(extents.extmin), self.pt(extents.extmax)
        return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))

    def fixture(self, name, kind, handles, rotation=0, bounds=None, **values):
        x1, y1, x2, y2 = bounds or self.source_bounds(*handles)
        w, h = x2-x1, y2-y1
        if rotation % 180 == 90:
            w, h = h, w
        cx, cy = (x1+x2)/2, (y1+y2)/2
        heights = {"bed": .75, "closet": 2.5, "open-closet": self.height, "table": .75, "study-desk": .78,
                   "kitchen-island": .92, "kitchen-work-surface": .92, "sink": .85, "shower": 2.1,
                   "television": 1.02, "rug": .035, "refrigerator": 2.1, "laundry-closet": 2.5,
                   "sliding-window-opening": 2.1, "oven":.9, "mirror":.9, "wallpaper":2.6, "wall-art":1.0,
                   "sofa":.82}
        return self.item("elements", "assembly-"+name.lower().replace(" ", "-"), name, (cx-w/2, cy-h/2, cx+w/2, cy+h/2),
                         elementKind=kind, rotation=rotation, elevation=0, height=heights[kind],
                         sourceLayer="/".join(sorted({self.doc.entitydb[h].dxf.layer for h in handles})),
                         sourceHandles=handles, **values)

    def verified_furniture(self):
        # Semantic assignments are source-handle specific. Dimensions and positions
        # come from the new DXF, never the earlier corrected planner coordinates.
        f = self.fixture
        if self.floor_key == "basement":
            for name, kind, handles, angle in (
                ("Basement table", "table", ["EB4"], 0), ("Basement bedroom bed", "bed", ["EE6"], 0),
                ("Basement bedroom desk", "study-desk", ["EDE"], 270),
                ("Basement bedroom closet", "closet", ["EDF", "EE0", "EE1"], 90),
                ("Basement basin east", "sink", ["EF1"], 90), ("Basement basin west", "sink", ["1155"], 90),
                ("Basement storage", "closet", ["64", "65", "66"], 270),
                ("Basement coffee table", "table", ["EAC"], 0),
                ("Basement lounge sofa", "sofa", ["E04","E05","E06","E08","E0B","E0D","E0E","E10","E11"],0),
                ("Basement shower west", "shower", ["E29","E2A","E2B","E2C"],0),
                ("Basement shower east", "shower", ["EE9","EEA"],0),
            ): f(name, kind, handles, angle)
        elif self.floor_key == "ground":
            front = self.source_bounds("221A")
            back_y = self.geom(self.doc.entitydb["22DA"])[0].bounds[1] + .25
            f("Kitchen work surface", "kitchen-work-surface", ["221A", "22DA"], 180,
              (front[0], back_y, front[2], front[1]))
            ret = self.source_bounds("2206")
            wall_x = min(x for x, y in self.geom(self.doc.entitydb["22C6"])[0].exterior.coords if abs(y-1.55)<.001)
            f("Kitchen work surface return", "kitchen-work-surface", ["2206", "22C6"], 270,
              (ret[0], back_y, wall_x, ret[3]))
            for name, kind, handles, angle in (
                ("Kitchen island", "kitchen-island", ["2232", "2233", "2247", "2248"], 0),
                ("Pantry north closets", "closet", ["21DA", "21DB", "21F7", "220F"], 180),
                ("Pantry south closets", "closet", ["2212", "223B", "2254"], 0),
                ("Dining table", "table", ["229E"], 0),
                ("Living room coffee table", "table", ["2312"], 0),
                ("Salon second coffee table", "table", ["2315"], 0),
                ("Living room rug", "rug", ["2310","2311"],0),
                ("Salon exterior-wall television", "television", ["1F3D", "1F3E"], 90),
                ("Guest toilet sink", "sink", ["21C8"], 0),
            ): f(name, kind, handles, angle)
            left = self.source_bounds("1F08", "1F0D")
            right = self.source_bounds("1F0C", "22B8")
            f("Kitchen tall storage left", "closet", ["1F08", "1F0D"], 0, left, materialRole="Pantry north closets")
            f("Kitchen tall storage right", "closet", ["1F0C", "22B8"], 0, right, materialRole="Pantry north closets")
            f("Kitchen pantry refrigerator", "refrigerator", ["1F0D", "1F0C"], 0)
            hob = self.source_bounds('21FB')
            f('Kitchen oven', 'oven', ['21FB','21FC','21FD','21FE','21FF','2200'], 270,
              (ret[0],hob[1],wall_x,hob[3]))
            for cabinet in self.plan['elements']:
                if cabinet['floorId']==self.floor_id and cabinet['elementKind']=='closet':
                    cabinet['cabinetLayout']='solid'
            # The basin's back touches the existing guest-WC wall face.
            sink = next(e for e in self.plan["elements"] if e["floorId"] == self.floor_id and e["name"] == "Guest toilet sink")
            face = self.source_bounds("21BE")[1]
            sink["y"] = face
        elif self.floor_key == "living":
            for name, kind, handles, angle in (
                ("Bedroom bed 1", "bed", ["19E3"], 0), ("Bedroom bed 2", "bed", ["19F5"], 0),
                ("Bedroom 1 study desk", "study-desk", ["19EA"], 270),
                ("Bedroom 2 study desk", "study-desk", ["19EB"], 90),
                ("Bedroom 1 closet", "closet", ["19ED", "19EE", "19EF"], 0),
                ("Bedroom 2 closet", "closet", ["19F0", "19F1", "19F2"], 0),
                ("Master bedroom study desk", "study-desk", ["18F2"], 0),
                ("Master bedroom bed", "bed", ["1A3F"], 90),
            ): f(name, kind, handles, angle)
            east_bank = self.source_bounds("1A38", "1A39", "1A3E")
            f("Master walk-in closet east bank", "open-closet", ["1A38", "1A39", "1A3E"], 270,
              (east_bank[2]-.5, east_bank[1], east_bank[2], east_bank[3]))
            bank = self.source_bounds("1A3C", "1A3D")
            f("Master walk-in closet west bank", "open-closet", ["1A3C", "1A3D"], 90,
              (bank[0], bank[1], bank[0]+.5, bank[3]))
            self.floor_audit.setdefault('userOverrides', []).append({
                'role': 'Master walk-in closet banks',
                'sourceDepthsM': [rounded(bank[2]-bank[0]), rounded(east_bank[2]-east_bank[0])],
                'modeledDepthsM': [.5, .5], 'backingFacesFixed': True, 'clearAisleM': .95})
            divider = self.source_bounds("1A3B", "1A3C")
            self.item("walls", "master-wardrobe-divider", "Master wardrobe backing wall", divider,
                      height=self.height, color="#fefdfa", opacity=1, sourceLayer="A34/A24", sourceHandles=["1A3B", "1A3C"],
                      sourceRole="dimensioned-10cm-wardrobe-backing")
            shower_edge = self.source_bounds("1A35")
            shower_mid_y = (shower_edge[1] + shower_edge[3]) / 2
            wall_section = self.geom(self.doc.entitydb["1C7B"])[0].intersection(
                box(shower_edge[0], shower_mid_y-.005, shower_edge[0]+3, shower_mid_y+.005))
            if wall_section.is_empty:
                raise ValueError("Master shower has no adjacent bathroom wall")
            bath_wall_face = wall_section.bounds[0]
            if bath_wall_face <= shower_edge[0]:
                raise ValueError("Master shower wall must be beyond its glass partition")
            f("Master bathroom dual shower", "shower", ["1A35", "1C7B"], 90,
              (shower_edge[0], shower_edge[1], bath_wall_face, shower_edge[3]))
            f("Master bathroom movable glass partition", "sliding-window-opening", ["1A35"], 90,
              (shower_edge[0]-.025, shower_edge[1], shower_edge[0]+.025, shower_edge[3]))
            top_face = self.source_bounds("1A35")[1]
            vanity_front = self.source_bounds("164B")
            f("Master bathroom drawer vanity", "sink", ["164B", "1C7F", "1A31"], 0,
              (vanity_front[0], top_face, vanity_front[2], vanity_front[1]), drawersAtFront=True)
            vanity = self.source_bounds("1655", "1A03")
            f("Living bathroom sink with storage", "sink", ["1655", "1A03", "1A01"], 90, vanity)
            bay = self.source_bounds("1661", "1662")
            f("Living bathroom laundry closet", "laundry-closet", ["1661", "1662"], 180, bay, applianceLayout='stacked')
            f("Utility laundry storage", "laundry-closet", ["1576", "1A02"], 0, materialRole="Living bathroom laundry closet")
        elif self.floor_key == "floor2":
            for name, kind, handles, angle in (
                ("Floor 2 bed", "bed", ["12F4"], 0), ("Floor 2 desk", "study-desk", ["12F3"], 0),
                ("Floor 2 storage", "closet", ["7FD", "1249", "124A", "1255"], 90),
                ("Floor 2 bathroom sink", "sink", ["13F1"], 270),
                ("Floor 2 shower", "shower", ["12C5","12C6"],90),
            ): f(name, kind, handles, angle)

    def apply_materials(self):
        donors = self.material_donor["elements"]
        names = {e["name"]: e for e in donors}
        fields = ("color", "opacity", "type1", "finish")
        generic_roles = {"bed":"Bed 1", "chair":"Chair 1", "sofa":"Sofa 1", "corner-sofa":"Corner sofa 1",
                         "sink":"Sink 1", "toilet":"Toilet 1", "bath":"Living bathroom bath",
                         "closet":"Bedroom 1 closet", "study-desk":"Bedroom 1 study desk",
                         "table":"Dining table", "mirror":"Sink 1 mirror", "shower":"Shower 1"}
        profiles = []
        for element in self.plan["elements"]:
            name = element.get("materialRole", element["name"])
            donor = names.get(name)
            if not donor:
                role = generic_roles.get(element["elementKind"])
                if not role:
                    raise ValueError(f"No verified material role for {name}")
                donor = names[role]
            element.update({key: donor[key] for key in fields if key in donor})
            element["materialSource"] = donor["id"]
            if element.get("sourceHandle") in ("1A29", "1A34"):
                role = "Living bathroom toilet" if element["sourceHandle"] == "1A29" else "Master bathroom toilet"
                element.update({key: names[role][key] for key in fields if key in names[role]})
                element["name"], element["materialSource"] = role, names[role]["id"]
            profiles.append({"id":element["id"],"role":element["name"],"donor":element["materialSource"]})
        self.audit["materialAssignments"] = profiles

    def register_to_saved_site(self):
        donor_slab = next(r for r in self.material_donor["rooms"] if r.get("structuralSlab") and r["floorId"].endswith("-ground"))
        tx, ty = donor_slab["x"]+donor_slab["w"], donor_slab["y"]+donor_slab["h"]
        def rotate_rect(item):
            item["x"] = rounded(tx-item["x"]-item["w"])
            item["y"] = rounded(ty-item["y"]-item["h"])
        for collection in ("rooms", "walls", "stairs", "elements", "roofs"):
            for item in self.plan[collection]:
                rotate_rect(item)
                for rect in item.get("surfaceRects", []):
                    rotate_rect(rect)
                if "rotation" in item:
                    item["rotation"] = rounded((item["rotation"]+180) % 360)
                if item.get('circularProfile'):
                    item['circularProfile']['centerX']=rounded(tx-item['circularProfile']['centerX'])
                for field in ("floorHoles", "ceilingHoles"):
                    for hole in item.get(field, []):
                        rotate_rect(hole)
        for opening in self.plan["openings"]:
            opening["x"],opening["y"] = rounded(tx-opening["x"]), rounded(ty-opening["y"])
            opening["rotation"] = rounded((opening["rotation"]+180)%360)
        external = json.loads(Path("plans/ruchama-18-20-external.json").read_text(encoding="utf-8"))
        for collection in ("walls", "elements"):
            for source in external[collection]:
                item = dict(source)
                item.update(id=KEY+"-external-"+source["id"], floorId=KEY+"-ground", context=True)
                self.plan[collection].append(item)
        for boundary in self.plan["boundaries"]:
            if boundary["floorId"] == KEY+"-ground":
                boundary.update({k: external["boundaries"][0][k] for k in ("x","y","w","h")})
            else:
                rotate_rect(boundary)
        self.audit["siteRegistration"] = {"transform": "180-degree house rotation, external objects unchanged",
                                           "xTranslation": tx, "yTranslation": ty, "donorSlabId": donor_slab["id"],
                                           "exteriorSave": "plans/ruchama-18-20-external.json"}
        self.plan["camera"] = dict(self.material_donor["camera"])

    def section_roof(self):
        self.origin,_=self.source_floor['floor2']
        self.floor_key,self.floor_id='floor2',KEY+'-floor2'
        enclosure=self.top_floor_enclosure()
        # Register the section's dining span (490 cm) to its plan wall face.
        # The independently labeled plan ridge lies at the same station.
        section_origin_x=self.doc.entitydb['C5A'].dxf.start.x-565
        arc=self.doc.entitydb['975']
        center_x=(arc.dxf.center.x-section_origin_x)/100
        ridge=self.pt(self.doc.entitydb['12F1'].dxf.insert)[0]
        if abs(center_x-ridge)>.05:
            raise ValueError('Section-to-plan roof ridge registration failed')
        profile={k:self.audit['sections']['roof'][k] for k in ('outerRadius','innerRadius','finishRadius','centerElevation')}
        roof_footprint=enclosure.buffer(.1, join_style=2)
        wall_west,_,wall_east,_=enclosure.bounds
        profile['centerX']=rounded((wall_west+wall_east)/2)
        wall_half_span=(wall_east-wall_west)/2
        wall_rise=profile['finishRadius']-math.sqrt(profile['finishRadius']**2-wall_half_span**2)
        donor=next(r for r in self.material_donor['roofs'] if r.get('shape')=='barrel')
        roof=self.item('roofs','section-roof','Section-derived circular roof',roof_footprint.bounds,
                       type='roof',shape='barrel',axis='z',circularProfile=profile,
                       color=donor['color'],opacity=donor['opacity'],sourceLayer='A10/A13/A14/A17/A24',
                       sourceHandles=['975','858','9BF','B6F','C5A','12F1','13FD','13F9','154C'])
        roof['surfaceRects']=[{'x':x1,'y':y1,'w':rounded(x2-x1),'h':rounded(y2-y1)}
                              for x1,y1,x2,y2 in rects(roof_footprint)]
        if abs(sum(rect['w']*rect['h'] for rect in roof['surfaceRects'])-roof_footprint.area)>.01:
            raise ValueError('Single roof surface does not cover its buffered wall contour')
        self.audit['sections']['roof']['planCenterX']=rounded(center_x)
        self.audit['sections']['roof']['ridgeLabelOffset']=rounded(abs(center_x-ridge))
        self.audit['sections']['roof']['renderedCenterX']=profile['centerX']
        self.audit['sections']['roof']['renderedCenterAdjustmentM']=rounded(profile['centerX']-center_x)
        self.audit['sections']['roof']['wallEdgeRiseM']=rounded(wall_rise)
        self.audit['sections']['roof']['overhangM']=.1
        self.audit['sections']['roof']['footprintStatus']='One arc over A17-enclosed wall contour plus 10 cm drip edge; terrace open to sky'

    def geometry_checks(self):
        for key, audit in self.audit["floors"].items():
            walls = unary_union([item_polygon(w) for w in self.plan["walls"]
                                 if w["floorId"] == KEY+'-'+key and w.get("sourceLayer") == "A17"])
            audit["wallReconstructionDifferenceM2"] = rounded(walls.symmetric_difference(self.wall_geometry[key]).area)
            if audit["wallReconstructionDifferenceM2"] > .01:
                raise ValueError(f"Generated {key} walls differ from A17 source")
            self.wall_geometry[key] = walls
            for dimension in audit["dimensions"]:
                a,b = dimension["endpoints"]
                distances = [walls.boundary.distance(Point(p)) for p in (a,b)]
                dimension["generatedWallFaceOffsets"] = [rounded(v) for v in distances]
                dimension["modelVerified"] = max(distances)<.015 and dimension["difference"]<.01
            audit["modelVerifiedDimensionCount"] = sum(d["modelVerified"] for d in audit["dimensions"])
        room_handles = {"basement":["D22"], "ground":["2170"], "living":["1664","1663"], "floor2":["D08"]}
        for key, handles in room_handles.items():
            self.origin,_=self.source_floor[key]
            checks=[]
            for handle in handles:
                shape=self.geom(self.doc.entitydb[handle])[0]
                x1,y1,x2,y2=shape.bounds
                face_checks=[]
                for a,b in zip(shape.exterior.coords,list(shape.exterior.coords)[1:]):
                    line=LineString([a,b])
                    supported=line.intersection(self.wall_geometry[key].boundary.buffer(.001)).length
                    face_checks.append(rounded(supported/line.length))
                checks.append({"areaHandle":handle,"width":rounded(x2-x1),"depth":rounded(y2-y1),
                               "area":rounded(shape.area),"wallSupportFractions":face_checks})
            self.audit["floors"][key]["clearAreaChecks"]=checks

    def dimensions(self):
        checks = []
        for e in self.entities:
            if e.dxf.layer.upper() != "A24" or e.dxftype() != "DIMENSION":
                continue
            attrs = e.dxf.all_existing_dxf_attribs()
            if "defpoint2" not in attrs or "defpoint3" not in attrs:
                continue
            a, b = self.pt(attrs["defpoint2"]), self.pt(attrs["defpoint3"])
            angle = math.radians(-attrs.get("angle", 0))
            measured = abs((b[0]-a[0])*math.cos(angle) + (b[1]-a[1])*math.sin(angle))
            stated = attrs.get("actual_measurement", 0) / 100
            if stated <= .01:
                continue
            checks.append({"handle": e.dxf.handle, "metres": rounded(stated), "endpoints": [a,b], "difference": rounded(abs(stated-measured))})
        self.floor_audit["dimensions"] = checks

    def build_floor(self, spec):
        key, name, handle, elevation, color = spec
        contour = self.doc.entitydb[handle]
        source_points = list(contour.get_points("xy"))
        top = max(p[1] for p in source_points)
        # Floor 2's AREA is a room outline. Register the shared south external
        # wall (A17 1538) to the south baseline of the other stories.
        if key == "floor2":
            top = bbox.extents([self.doc.entitydb["1538"]]).extmin.y + 900
        self.origin = (min(p[0] for p in self.doc.entitydb["1F44"].get_points("xy")), top)
        self.floor_key, self.floor_id = key, KEY + "-" + key
        self.height = {"basement":2.75,"ground":2.79,"living":2.79,"floor2":2.75}[key]
        footprint = self.geom(contour)[0]
        self.floor_audit = {"areaHandle": handle, "originCm": list(self.origin), "areaM2": rounded(footprint.area)}
        self.audit["floors"][key] = self.floor_audit
        self.source_floor[key] = (self.origin, footprint)
        self.entities = []
        for e in self.model:
            if e.dxf.layer.upper() not in LAYERS:
                continue
            ex = bbox.extents([e])
            if ex.has_data and self.origin[1]-1100 < ex.center.y < self.origin[1]+350 and 12500 < ex.center.x < 14700:
                self.entities.append(e)
        self.plan["floors"].append({"id": self.floor_id, "name": name, "elevation": elevation, "color": color,
                                   "finish": "light-gray-granite" if key == "ground" else "parquet" if key == "living" else None})
        self.item("boundaries", "boundary", name + " extent", (-2,-3,19,12), type="boundary",color="#94a3b8",opacity=.1)
        labels = [{"handle": e.dxf.handle, "text": decode_architect_text(e.dxf.text), "position": self.pt(e.dxf.insert)}
                  for e in self.entities if e.dxftype() == "TEXT" and e.dxf.layer.upper() == "A49"]
        self.floor_audit["labels"] = labels
        if key == "living":
            void = self.geom(self.doc.entitydb["164D"])[0]
            evidence = [label for label in labels if label["handle"] in ("189E", "15BF", "15C0")]
            if not any(label["text"] == "\u05d7\u05dc\u05dc \u05db\u05e4\u05d5\u05dc" for label in evidence):
                raise ValueError("Double-height void label verification failed")
            self.floor_audit["voids"] = [{"areaHandle": "164D", "labels": evidence, "areaM2": rounded(void.area)}]
            self.slab(footprint, name, handle)
            x1, y1, x2, y2 = void.bounds
            opening = {"x": x1, "y": y1, "w": x2-x1, "h": y2-y1, "sourceHandle": "164D"}
            for slab in self.plan["rooms"]:
                if slab["floorId"] == self.floor_id:
                    slab["floorHoles"] = [dict(opening)]
                elif slab["floorId"] == KEY+"-ground" and not slab.get("outdoor"):
                    slab["ceilingHoles"] = [dict(opening)]
        else:
            self.slab(footprint, name, handle)
        hatch_polys = []
        for e in self.entities:
            if e.dxf.layer.upper() != "A17" or e.dxftype() != "HATCH":
                continue
            for p in self.geom(e):
                if p.area < .003 or p.distance(footprint) > 6:
                    continue
                # The first three AREA outlines enclose complete stories. Nearby
                # site/courtyard hatches are not full-height house walls. Floor 2
                # differs: its AREA contour encloses only the bedroom clear area.
                if key != "floor2" and p.intersection(footprint).area < .001:
                    self.floor_audit.setdefault("excludedExteriorHatches", []).append(e.dxf.handle)
                    continue
                hatch_polys.append(p)
                for i, bounds in enumerate(rects(p)):
                    x1,y1,x2,y2=bounds
                    if min(x2-x1,y2-y1) < .035:
                        continue
                    self.item("walls", f"hatch-{e.dxf.handle}-{i}", f"Wall {e.dxf.handle}", bounds,
                              rotation=0, height=self.height, color="#fefdfa",opacity=1,sourceLayer="A17",sourceHandle=e.dxf.handle)
        wall_geometry = unary_union(hatch_polys)
        self.wall_geometry[key] = wall_geometry
        self.aligned_openings(wall_geometry)
        self.perimeter_openings(footprint,wall_geometry)
        self.opening_roles()
        self.furniture(footprint)
        self.dimensions()
        outdoor_lines = self.linework({"A14", "A17", "AREA"})
        cells = list(polygonize(unary_union([set_precision(line,.001) for line in outdoor_lines])))
        if key == "floor2":
            enclosure = self.top_floor_enclosure()
            platform = unary_union([p for p in cells if p.area > .003])
            # The two labeled terrace cells include open door gaps into the
            # bathroom/hall. Subtract the A17-supported enclosure before tiling.
            terraces = unary_union([p for p in cells if any(
                "\u05de\u05e8\u05e4\u05e1\u05ea" in label["text"] and p.contains(Point(label["position"])) for label in labels)])
            outdoor = terraces.difference(enclosure)
            self.plan["rooms"] = [r for r in self.plan["rooms"] if r["floorId"] != self.floor_id]
            self.slab(enclosure, "Top-floor enclosed slab", "D08-A17")
            self.slab(outdoor, "Roof terrace", "A14-labeled-terraces", True)
            for terrace in self.plan['rooms']:
                if terrace['floorId']==self.floor_id and terrace.get('outdoor'):
                    terrace['surfaceColor']='#d9dee5'
            self.floor_audit["enclosureM2"] = rounded(enclosure.area)
            self.floor_audit["balconies"] = [{"areaM2": rounded(outdoor.area), "labels": ["1256", "D06", "12A3"]}]
            self.floor_audit["counts"] = {c:sum(v.get("floorId")==self.floor_id for v in self.plan[c]) for c in ("walls","openings","elements","rooms")}
            return
        outdoor = []
        for candidate in cells:
            if candidate.area < 1.5 or candidate.intersection(footprint).area > candidate.area*.05:
                continue
            if candidate.distance(footprint) > .36 or candidate.intersection(wall_geometry).area > candidate.area*.1:
                continue
            if not any(candidate.boundary.intersection(g.buffer(.003)).length > .4 for g in self.linework({"A14"})):
                continue
            outdoor.append(candidate)
        for i,p in enumerate(outdoor):
            self.slab(p, "Terrace" if key in ("ground","basement") else "Balcony", f"a14-balcony-{i}", True)
        self.floor_audit["balconies"] = [{"areaM2":rounded(p.area),"bounds":[rounded(v) for v in p.bounds]} for p in outdoor]
        if key == 'living':
            master_balcony = box(*self.source_bounds('1CBB', '1AEE', '1CD5'))
            label = next(label for label in labels if label['handle'] == 'C8B')
            if not master_balcony.contains(Point(label['position'])) or master_balcony.intersection(footprint).area > .001:
                raise ValueError('Master balcony must contain its A49 label and lie outside AREA')
            x1,y1,x2,y2 = master_balcony.bounds
            self.slab(master_balcony, 'Master bedroom balcony', 'a14-master-bedroom-balcony', True)
            for name, bounds, handle in (
                ('outer', (x1,y1,x1+.05,y2), '1CBB'),
                ('north', (x1,y1,x2,y1+.05), '1AEE'),
                ('south', (x1,y2-.05,x2,y2), '1CD5'),
            ):
                self.item('walls', f'master-balcony-guard-{name}', 'Master balcony guard', bounds,
                          type='glass-wall', height=1.05, color='#b9d8e8', opacity=.48,
                          sourceLayer='A14', sourceHandle=handle, sourceRole='balcony-guard')
            self.floor_audit['balconies'].append({'areaM2':rounded(master_balcony.area),
                                                  'bounds':[rounded(v) for v in master_balcony.bounds],
                                                  'label':'C8B', 'edgeHandles':['1CBB','1AEE','1CD5']})
        self.floor_audit["counts"] = {c:sum(v.get("floorId")==self.floor_id for v in self.plan[c]) for c in ("walls","openings","elements","rooms")}

    def stairs(self):
        for key, handle in (("basement","11CC"),("ground","2287")):
            self.origin, _ = self.source_floor[key]
            p = self.geom(self.doc.entitydb[handle])[0]
            x1,y1,x2,y2=p.bounds
            width = min(math.dist(a,b) for a,b in zip(p.exterior.coords,list(p.exterior.coords)[1:]))
            # CAD ascent: long lower run westward, landing, short run northward.
            cx,cy=(x1+x2)/2,(y1+y2)/2
            w,h=y2-y1,x2-x1
            self.plan["stairs"].append({"id":f"{KEY}-{key}-stair", "type":"stair", "floorId":f"{KEY}-{key}",
                "name":f"{key.title()} stairs", "x":rounded(cx-w/2),"y":rounded(cy-h/2),"w":rounded(w),"h":rounded(h),
                "shape":"turned","turn":"right","landing":rounded(width),"rotation":90,"level":0,
                "height":2.75 if key=="basement" else 3.14,"color":"#3d2418","opacity":1,"type1":"dark-wood",
                "sourceLayer":"AREA","sourceHandle":handle})
        # The outgoing floor's AREA core and A14 treads determine the route;
        # arrival-floor tread graphics put the short run on the opposite side.
        self.origin,_=self.source_floor["ground"]
        ground_core=self.geom(self.doc.entitydb["2287"])[0].bounds
        self.origin,_=self.source_floor["living"]
        area=self.geom(self.doc.entitydb["1575"])[0]
        left_x,top_y,right_x,bottom_y=area.bounds
        horizontal=self.source_bounds("1D50")
        vertical=self.source_bounds("1D58")
        vertical_end=self.source_bounds("1D60")[3]
        horizontal_top=self.source_bounds("1D53")[1]
        w,h=right_x-left_x,bottom_y-top_y
        run_x=horizontal[0]-left_x
        run_y=horizontal_top-top_y
        short_w=vertical[2]-left_x
        short_h=vertical_end-top_y
        if abs(left_x-ground_core[0])>.01 or abs(bottom_y-ground_core[3])>.01:
            raise ValueError("Living outgoing stair no longer registers to the shared AREA core")
        if abs(self.source_bounds("1D56")[1]-top_y)>.01:
            raise ValueError("Living stair upper-end marker does not meet its outgoing run")
        self.plan["stairs"].append({"id":f"{KEY}-living-stair","type":"stair","floorId":f"{KEY}-living",
            "name":"Living floor stairs", "x":rounded(left_x),"y":rounded(top_y),"w":rounded(w),"h":rounded(h),
            "shape":"turned","turn":"right","landing":rounded(max(run_x, h-short_h)),"rotation":0,"level":0,"height":2.584,
            "color":"#3d2418","opacity":1,"type1":"dark-wood",
            "cadRuns":[{"x":rounded(run_x/w),"y":rounded(run_y/h),"w":rounded((w-run_x)/w),"h":rounded((h-run_y)/h),"dir":"x","reverse":True},
                       {"x":0,"y":0,"w":rounded(short_w/w),"h":rounded(short_h/h),"dir":"z","reverse":True}],
            "cadLanding":{"x":0,"y":rounded(short_h/h),"w":rounded(run_x/w),"h":rounded((h-short_h)/h)},
            "sourceLayer":"AREA/A13/A14","sourceHandles":["1575","1D50","1D53","1D58","1D60","1D56"]})

    def run(self):
        for spec in FLOORS:
            self.build_floor(spec)
        self.stairs()
        self.apply_materials()
        self.geometry_checks()
        self.section_roof()
        self.register_to_saved_site()
        ids=[item["id"] for key in ("rooms","walls","openings","stairs","elements") for item in self.plan[key]]
        assert len(ids)==len(set(ids)), "Duplicate source ids"
        self.plan["importAudit"] = "docs/alt4-v2-layer-audit.json"
        self.audit["validation"] = {"status":"draft", "publicationReady":False,
                                    "verified":["Living-to-top stair route from departure-floor AREA 1575, A14 treads and A13 upper-end marker",
                                                "Single top-level arc over enclosed A17 walls with 10 cm overhang and uncovered light-gray terraces"],
                                    "pending":["Full room-by-room source overlay review", "Final human-height browser QA",
                                               "Integrate top-floor high/low zones and verify roof-clipped walls against both sections"]}
        return self.plan


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path)
    args=parser.parse_args()
    importer=Importer(args.source)
    plan=importer.run()
    Path(f"plans/{KEY}.json").write_text(json.dumps(plan,indent=2)+"\n",encoding="utf-8")
    Path("docs/alt4-v2-layer-audit.json").write_text(json.dumps(importer.audit,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({key: data["counts"] for key,data in importer.audit["floors"].items()},indent=2))
