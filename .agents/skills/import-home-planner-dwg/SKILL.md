---
name: import-home-planner-dwg
description: Import architect DWG or DXF floor plans into this Home Planner repository, infer rooms and architectural objects from layered or exploded CAD, and validate 2D/3D alignment. Use for new architect designs and systematic corrections to imported designs; do not use for unrelated manual plan edits.
---

# Import Home Planner DWG

Translate the drawing as an architectural system, not as a bag of rectangles. Build a room-by-room constraint model before assigning element types or writing plan JSON.

## Project Context

- Treat `tools/build_architect_presets.py` as the source of truth for repeatable imports.
- Write generated plans under `plans/`; do not hand-fix JSON without making the equivalent generator change.
- Read `docs/architect-import-rules.md` when the source is Alt-4 or shares its drawing conventions.
- Read [references/inference-and-qa.md](references/inference-and-qa.md) before interpreting a new drawing or diagnosing broad import errors.

## Workflow

1. Inspect the DXF structurally with `ezdxf`: sheets, extents, layers, blocks, text, dimensions, linework, and repeated symbol geometry. Render focused layer and floor crops when semantics remain unclear.
2. Establish one coordinate contract before extracting objects: source units, sheet crop, Y direction, floor registration, north, site translation, and whole-house rotation. Apply the same transform to centers, rotations, roof directions, and opening hosts. Keep site context outside house-only transforms.
3. Reconstruct walls and room boundaries first. Recover missing wall spans from collinearity, thickness, endpoints, dimensions, and neighboring floors. Then place openings, fixed fixtures, furniture, finishes, roofs, and site objects in that order.
4. Build a floor-scoped room inventory. Identify each object by `(floorId, room, role)`; never resolve generic names such as `Sink 1` globally. Use stable semantic names for deliberate corrections.
5. Infer symbols as clusters. Combine enclosure, dimensions, nearby fixtures, wall contact, door access, repeated symbols, and room function. Color or layer is supporting evidence, not proof. Decode stair direction from the complete run: in drawings using this convention, yellow tread geometry defines the staircase and its outgoing triangle marks the upper end.
6. Convert user annotations such as “left of the door,” “after the sink,” or numbered arrows into explicit geometric constraints and generator validations.
7. Preserve intentional overlap only: sink in counter, mirror on wall, appliance in cabinet. Flag furniture intersections, fixtures crossing walls, detached openings, inaccessible doors, and faces or handles pointing outside the room.
8. Regenerate every sibling preset derived from the same source and add validations for the newly learned invariant. Avoid exact coordinates as a general rule unless they describe a verified source-specific correction.

## Required QA Gates

- Compare every floor independently against the source and compare all floors together for registration.
- Verify each stair footprint, run direction, upper end, and landing against the source. The upper end must register with the destination-floor opening or landing after the shared floor transform.
- Review each room as a complete checklist from its entrance, not object by object.
- Verify every door/window against its wall gap and its 3D cutout. Rotated walls, snapping, panes, and cutouts must share one wall-local transform; choose the closest valid host when several fragments qualify.
- Check active/front faces: cabinet handles, desks, toilets, sinks, doors, and appliances must face into the intended room.
- Run generator validation, JavaScript syntax checks, and `git diff --check`.
- Use browser screenshots at desktop size: focused 2D room crop, human-height 3D view from the entrance, exterior views where openings matter, and all-floor section view for floors/ceilings/roofs.
- Do not publish merely because generation succeeded. Finish visual QA and follow the repository’s publication authorization rules.

When evidence remains genuinely ambiguous after these checks, isolate the smallest ambiguous cluster and ask one concrete question with an annotated crop. Do not silently choose a semantic object from color alone.
