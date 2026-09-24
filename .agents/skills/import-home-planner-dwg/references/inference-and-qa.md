# DWG Inference And QA

Use this reference for a new architect import or when several imported objects are wrong in the same way.

## Evidence Order

Prefer evidence in this order:

1. Written dimensions, levels, section marks, and readable labels.
2. Wall continuity, paired wall faces, explicit gaps, and opening frames.
3. Repeated symbol geometry elsewhere in the same drawing.
4. Room access, circulation, plumbing adjacency, and functional sequence.
5. Layer and color conventions.

Unreadable text is weak evidence. Do not let mojibake override geometry.

## Floor And Transform Contract

Create a table for every sheet before extraction:

| Field | Meaning |
|---|---|
| source bounds | The sheet crop in CAD coordinates |
| units | Usually centimetres in this project; verify from dimensions |
| origin | Shared local house origin |
| axis mapping | CAD X/Y to planner X/Y, including Y inversion |
| elevation | Story baseline |
| north | Source north before site placement |
| site transform | Translation and rotation applied to the complete house |

Test the contract with at least three asymmetric anchors: front entrance, stair core, and one exterior corner or distinctive window. A symmetric slab alone cannot detect a 180-degree error.

Transforms apply to object centers and orientation together. After rotating the house, re-evaluate directional properties such as roof tilt and object fronts. Do not rotate copied roads, fences, trees, pools, or neighboring buildings with the house.

### Coordinate-Phase Discipline

Keep source extraction and final-site repairs separate. A coordinate literal is valid in one phase only:

- **Source phase:** before Y inversion, site translation, and house rotation have all completed.
- **Final phase:** after the complete house transform, in the coordinate system rendered by the planner.

Name helper functions and comments by phase, such as `repair_source_*` and `repair_final_*`. Do not append a final-coordinate wall before the transform or use a source-coordinate measurement after it. A mixed phase can make a correct local measurement appear mirrored, offset, or attached to the wrong room.

## Room-First Reconstruction

For each floor, make a room inventory before generating objects:

- perimeter walls and internal partitions
- entrances and swing direction
- windows and sill/head heights
- fixed plumbing and kitchen fixtures
- storage and built-ins
- movable furniture
- finishes and decorations

Then describe each room from its entrance clockwise. This catches the common failure where all objects exist but occupy the wrong sides.

For a room cluster that includes a closet, bathroom, or stair core, trace an actual walkable route through the drawing. Each transition must have a source-supported wall gap and door where appropriate. Do not accept a repair that creates a new divider or an extra door simply because it makes a local crop look more regular.

Represent instructions as constraints, for example:

- `bath.center.x < door.center.x`
- `sink.center.x > door.center.x`
- `toilet.alongWall > sink.alongWall`
- `laundry.alongWall > bath.alongWall`
- `sink footprint overlaps counter footprint`
- `walk_in_bank_a.faces(walk_in_bank_b)` and the clear aisle equals the written dimension
- `shower.before(entrance)`, `toilet.after(entrance)`, and `toilet.faces(shower)`

Add these constraints to generator validation when they express intended architecture rather than a temporary visual preference.

## Symbol Interpretation

Treat exploded symbols as connected or proximal clusters, not independent rectangles.

- A door uses a wall gap plus leaf and/or swing arc. Multiple arcs around one gap are alternatives or annotation noise, not necessarily multiple doors.
- A window uses a framed wall gap; yellow frame pairs were reliable in Alt-4. Reconstruct the wall above and below the opening instead of deleting the full wall segment.
- A full-height glazed opening with zero sill and exterior circulation on both sides is a sliding glass door, even when the drawing or user calls it a movable window. Model it as a door so the wall cutout reaches the floor; use the frame overlap to infer the sliding panels rather than adding a swing arc.
- An X-marked green rectangle is commonly a closet in this project. An empty green rectangle is commonly a bed. A long rectangle with a smaller offset rectangle commonly represents a study desk and chair.
- A basin plus cabinet footprint is one sink-with-storage assembly. The mirror aligns to the same wall and faces inward.
- A bath is an elongated rim/basin symbol. A toilet has a bowl/cistern cluster. Washer/dryer symbols should be grouped with their open cabinet and upper storage when enclosed together.
- Repeated cabinet rectangles form one run; recover the full run and orient all handles toward the room. Inspect the bays before normalizing: a different-width, double-door, appliance-marked, or explicitly dimensioned bay may be an integrated refrigerator, oven, washer, or pantry tower. Preserve the run plus each such bay as an anchored semantic component.
- A staircase is a directional cluster, not just its bounding rectangle. Where the drawing uses the verified convention, collect the yellow tread and landing linework into one footprint; the outgoing triangle points to the upper end of the flight. Infer ascent from the opposite end toward that triangle. Do not use page orientation, a nearby arrow, or the longer side of the bounding box as a substitute for this marker.
- Cyan linework is not automatically glass or a window. Check whether it continues the wall system, frames an opening, or belongs to annotation.

When a source symbol is absent or too exploded to recover reliably, add one semantic object only after room geometry and repeated examples make its role clear.

## Structural Wall Proof

Before creating a wall that is not a direct paired-face extraction, write down its proof:

1. The two wall endpoints and the existing wall graph nodes they meet.
2. The written dimension, repeated boundary, or cross-sheet alignment that requires it.
3. The rooms it separates and the circulation route it preserves.
4. Any openings hosted by it, with their jambs and clear width.

Reject the proposed wall when its only evidence is a wardrobe front, furniture edge, door swing arc, hatch line, dimension line, or a desire to give a loose opening a host. Reconstruct a continuous host only when the enclosing wall is already established; never create a free-standing divider as a host-of-last-resort.

For a walk-in closet, validate the assembly as one object: entry host, entry opening, two opposing banks, bank depths, front directions, and aisle width. A closet drawn with exploded furniture can look like several short walls. The furniture remains furniture unless it also has the endpoint and enclosure proof above.

## Identity And Scope

Generic imported names repeat across floors. Always filter by `floorId` before matching `Sink 1`, `Wall 3`, `Window 2`, and similar names. Prefer a map keyed by `(floorId, sourceId)` or `(floorId, semantic role)`.

After manual semantic repair, use unique names such as `Living bathroom sink with storage`. Keep IDs stable when possible, but never allow a name collision to move an object on another floor.

If one example is wrong, audit the shared rule:

- several panes offset from cutouts: inspect rotated-wall transforms and host selection
- furniture rotated outward: inspect front-face convention after the house transform
- missing windows: inspect layer filtering, wall-gap detection, and merged repeated symbols
- one floor’s fixture moved: inspect global name lookup and floor scoping
- missing wall bands: inspect overlap suppression and whether room slabs were mistaken for wall-less spaces

## Opening And Wall Geometry

Use a wall-local frame for rotated walls:

1. Translate the point by the wall center.
2. Inverse-rotate into wall-local coordinates.
3. Project along the wall length and measure perpendicular distance.
4. Store or derive normalized `t` along the host.
5. Transform the pane and cutout back through the same frame.

When a free opening intersects more than one nearby fragment, score candidates by projected-center distance and architectural continuity. Prefer a reconstructed host spanning the intended gap over a fragment that merely touches one edge.

## Collision And Orientation Review

For each room, verify:

- fixtures remain inside the intended wall envelope
- the entrance and circulation path stay usable
- movable furniture does not intersect other furniture
- sanitary fixtures do not intersect each other
- doors can swing without crossing permanent fixtures unless the source explicitly shows that condition
- cabinet and appliance fronts face open room space
- mirrors face the camera side of their sink wall
- windows are not accidentally hidden by tall furniture

Rotated footprints must be tested after rotation, not by their unrotated JSON width and height.

## Dimension Reconciliation

Keep a per-room dimension ledger containing the source clear width, clear depth, generated clear width, generated clear depth, and the source references used. Measure between finished wall faces or jambs, not from centerlines, furniture bounds, or annotations.

- Calibrate the floor transform with three asymmetric anchors before using any local dimension as a correction.
- Correct the smallest affected room cluster. A mismatch in one 285 cm bedroom does not authorize a whole-floor scale change.
- After a transform or a wall repair, repeat the ledger check for neighboring rooms sharing the altered walls.
- Treat a repeated mismatch across multiple rooms as a transform, wall-thickness, or wall-local-frame defect and fix that shared rule first.

## Stair Reconstruction

Decode and validate stairs before applying the whole-house/site transform:

1. Cluster the yellow parallel tread lines, perimeter, landing edges, and direction marker. Exclude yellow room dimensions, door arcs, and unrelated annotation by continuity and containment within the stair footprint.
2. Treat the point of the outgoing triangle as the upper endpoint. Set the run direction from the lower endpoint toward that point, then transform both the footprint and direction together.
3. Derive the footprint from the outer stair/landing edges rather than from tread extents alone. Preserve intermediate landings and turns instead of collapsing a U- or L-shaped stair into one straight rectangle.
4. On the source floor, verify the lower endpoint and first tread. On the destination floor, verify that the upper endpoint meets the stairwell opening or landing without a lateral offset.
5. Compare the same stair core across adjacent sheets using walls and slab openings as registration anchors. For a straight flight, its footprint should register with the matching opening. For an L-shaped flight, compare its marked landing and outgoing-triangle endpoint instead of requiring the whole rectangles to overlap: successive flights can use different legs of the same core. A mismatch at the destination is a transform or direction failure, not permission to move only the rendered stair.

Record the detected lower point, upper triangle point, run/turn shape, footprint, source floor, and destination floor. Add generator checks for endpoint registration and transformed direction whenever a preset contains stairs.

## Visual QA Matrix

Before considering an import complete, capture and inspect:

| View | Detects |
|---|---|
| focused 2D crop per room | wrong side/order, duplicates, omissions, wall gaps |
| entrance-height 3D per room | inward faces, fixture scale, occlusion, circulation |
| four exterior sides | missing walls/windows, reversed doors, cabinet fronts leaking outside |
| all-floors section | floor/ceiling ownership, story registration, stairs, roof footprint |
| selected-floor view | visibility ownership and unintended cross-floor objects |

Use nonblank canvas checks, but never substitute them for screenshot inspection. Compare against the source drawing and the user’s latest annotations.

## Project-Specific Memory

For Alt-4’s verified corrections and materials, read `docs/architect-import-rules.md`. Reuse its reasoning on another design only when the same drawing convention is demonstrated; do not transfer Alt-4 coordinates or room assumptions blindly.
