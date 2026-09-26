---
name: import-home-planner-dwg
description: Import architect DWG or DXF floor plans into this Home Planner repository, infer rooms and architectural objects from layered or exploded CAD, and validate 2D/3D alignment. Use for new architect designs and systematic corrections to imported designs; do not use for unrelated manual plan edits.
---

# Import Home Planner DWG

Translate the drawing as an architectural system, not as a bag of rectangles. Build a room-by-room constraint model before assigning element types or writing plan JSON.

## Project Context

- Keep generator changes with their target version: `tools/build_architect_presets.py` maintains the earlier presets; `tools/build_alt4_v2.py` is the separate layer-driven Alt-4 v2 reconstruction. Check the v2 audit's publication status before treating its unfinished geometry as validated.
- Write generated plans under `plans/`; do not hand-fix JSON without making the equivalent generator change.
- Read `docs/architect-import-rules.md` when the source is Alt-4 or shares its drawing conventions.
- Read [references/inference-and-qa.md](references/inference-and-qa.md) before interpreting a new drawing or diagnosing broad import errors.
- For Alt-4 colors and finishes, read [references/alt4-materials.md](references/alt4-materials.md). The existing Alt-4 save is authoritative over older skill notes or importer defaults. Transfer appearance by floor and semantic role, not old geometry or CAD layer colors.

## Workflow

1. Inspect the DWG layer table and a layer-preserving DXF structurally with `ezdxf`: sheets, extents, layers, blocks, text, dimensions, linework, and repeated symbol geometry. Verify that the conversion retains the original layer names and that the source files match. Read [references/layer-contract.md](references/layer-contract.md) for the user-specified Alt-4 layer mapping and the required layer-content checks. Render focused layer and floor crops when semantics remain unclear.
2. Establish one coordinate contract before extracting objects: source units, sheet crop, Y direction, floor registration, north, site translation, and whole-house rotation. Apply the same transform to centers, rotations, roof directions, and opening hosts. Keep site context outside house-only transforms. Record whether every manual correction is in source coordinates or final planner coordinates; never apply a final-coordinate repair before the shared transform or a source-coordinate repair after it.
3. Reconstruct walls and room boundaries first. Recover missing wall spans from collinearity, thickness, endpoints, dimensions, and neighboring floors. Treat exploded linework as evidence, not architecture: a new structural wall requires two supported endpoints and a room-boundary role. It must not be added merely to host a door, join furniture edges, or make a partial drawing look closed. Then place openings, fixed fixtures, furniture, finishes, roofs, and site objects in that order.
4. Build a floor-scoped room inventory. Identify each object by `(floorId, room, role)`; never resolve generic names such as `Sink 1` globally. Use stable semantic names for deliberate corrections.
5. Infer symbols as clusters. Combine enclosure, dimensions, nearby fixtures, wall contact, door access, repeated symbols, and room function. Color or layer is supporting evidence, not proof. Decode stair direction from the complete run: in drawings using this convention, yellow tread geometry defines the staircase and its outgoing triangle marks the upper end. Register every flight footprint to the shared stair core on the floors above and below; a correctly shaped flight at an offset origin is still incorrect.
6. Convert user annotations such as “left of the door,” “after the sink,” or numbered arrows into explicit geometric constraints and generator validations. For every room, trace the path from its entry through its circulation space before accepting its doors, closets, or fixtures.
7. Preserve intentional overlap only: sink in counter, mirror on wall, appliance in cabinet. Flag furniture intersections, fixtures crossing walls, detached openings, inaccessible doors, and faces or handles pointing outside the room. Check rotated footprints in world coordinates rather than their unrotated JSON boxes.
8. Reconcile dimensions locally, room by room. Use the written clear span between finished wall faces as the authoritative measurement; do not try to fix a 285 cm room by rescaling a complete floor. Compare at least one horizontal and one vertical dimension for each room cluster before placing furniture.
9. Regenerate only the requested designs and versions and add validations for the newly learned invariant. For a requested fresh start, create a separately named save (such as `architect-alt-4-v2`) and register it in `plans/projects.json`; preserve earlier saves and other alternatives. Re-extract geometry from the verified layers. Earlier repairs and saved-plan coordinates are QA evidence, not defaults to copy into a fresh import. Avoid exact coordinates as a general rule unless they describe a verified source-specific correction.
10. Reconcile appearance separately from geometry. Inventory the authoritative save's `color`, `opacity`, `finish`, and `type1` values by floor, room, and role, including opening variants. Resolve conflicts in favor of that save and add missing material rules to the skill. Preserve finish selectors and renderer assets, not just base hex colors. Report unmatched roles rather than silently using a generic furniture palette.
11. Inspect sections and elevations before accepting vertical geometry. Locate their native CAD entities, register the section cuts to the plan, and distinguish finished-floor elevations, clear heights, slab/finish depths, local split levels, roof radii, and roof rise. A plan-only layer contract does not establish roof geometry. Read the section-specific findings in [references/layer-contract.md](references/layer-contract.md) for Alt-4.

## Structural Decision Rules

- Build a wall graph before adding semantic repairs. A wall is structural only when it continues a paired-face boundary, reaches verified wall/end points, or is required by a dimensioned room enclosure.
- Do not use a door swing arc as a wall locator. First identify the wall gap and its two jambs; then infer the leaf, hinge, and swing from the same opening cluster.
- A door must be attached to a real host wall and its swing must preserve the room's circulation path. A nearby wall fragment is not a valid host when its extension would cut a closet aisle, room, or passage.
- Keep an explicit `source`/`final` coordinate phase on helper names or comments. Manual final-layout repairs must run after the house transform; source repairs must run before it. Never mix these phases in one coordinate literal.
- For walk-in closets, prove the whole assembly at once: entry opening, both banks, their inward-facing fronts, written bank depths, and clear aisle. Do not convert wardrobe fronts into partitions or add a second door/divider unless the source has a separate dimensioned wall and gap.
- Preserve heterogeneous built-in runs as assemblies. When a dimensioned cabinet run contains a refrigerator, oven, washer, or other recognizable bay, retain both the complete enclosing run and an anchored semantic component for that bay. A generic closet normalization must not erase appliance identity, bay layout, height, or room ownership.
- When a source DWG cannot be inspected structurally, obtain a DXF conversion or use a rendered source crop with readable dimensions. Mark ambiguous clusters and ask one focused question instead of inventing architecture from a screenshot.

## Required QA Gates

- Compare every floor independently against the source and compare all floors together for registration.
- Verify each stair footprint, run direction, upper end, and landing against the source. The upper end must register with the destination-floor opening or landing after the shared floor transform. For L-shaped stairs, compare the marked landing and outgoing-triangle endpoint, not the full bounding rectangles: adjacent flights can occupy different legs of the same core. Cut the floor and ceiling opening from the union of the individual flights and landing; never use the enclosing stair bounding box, which removes ceiling from the unused corner. A floor slab is cut only by the flight arriving from the floor below; its ceiling is cut only by the flight departing upward. Never subtract both flights from the same horizontal surface.
- Review each room as a complete checklist from its entrance, not object by object.
- Verify every door/window against its wall gap and its 3D cutout. Rotated walls, snapping, panes, and cutouts must share one wall-local transform; choose the closest valid host when several fragments qualify.
- For every newly reconstructed wall, verify its endpoints meet the structural graph, it does not cross a room's usable circulation path, and it is not derived solely from furniture, a door arc, or annotation.
- Compare each room's written dimensions against the generated clear spans after every global transform. Use multiple asymmetric anchors per floor so a mirrored or shifted room cannot pass based on a matching slab alone.
- Review a suite or bathroom as an ordered route from the entrance. Confirm that each door is necessary, each closet or fixture stays in its source enclosure, and no duplicate entry wall or door has been inferred.
- Check active/front faces: cabinet handles, desks, toilets, sinks, doors, and appliances must face into the intended room.
- Review every kitchen/pantry cabinet run for its full source length, depth, height, panel layout, and integrated appliances; do not accept a generic cabinet surrogate when the source shows a refrigerator or other distinct bay.
- Run generator validation, JavaScript syntax checks, and `git diff --check`.
- Compare the new plan's material inventory against the authoritative save by semantic role. Check floor textures, pure-white ceiling undersides, wall tint, dark stair wood, kitchen band ratios, island top, glass opacity, and special bathroom/wardrobe finishes separately. A successful geometry check does not validate materials.
- Use browser screenshots at desktop size: focused 2D room crop, human-height 3D view from the entrance, exterior views where openings matter, and all-floor section view for floors/ceilings/roofs.
- Do not publish merely because generation succeeded. Finish visual QA and follow the repository’s publication authorization rules.

When evidence remains genuinely ambiguous after these checks, isolate the smallest ambiguous cluster and ask one concrete question with an annotated crop. Do not silently choose a semantic object from color alone.
