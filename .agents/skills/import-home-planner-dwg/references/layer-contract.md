# Layer Contract For Alt-4

User-provided mapping for the fresh Alt-4 import, 2026-09-26. Match names case-insensitively, retaining their original spelling in provenance.

| Layer | Intended use |
|---|---|
| AREA | Floor outlines, areas, and staircase positions |
| A34 | Furniture and built-in cabinet assemblies |
| A24, A49 | Written dimensions and independent distance comparisons |
| A17 | Walls |
| A16 | Sanitary fixtures, basins, taps, and in-room furniture |
| A12 | Doors, including leaves and swing geometry |
| A14 | Window geometry |

Source inspection also found stair direction triangles and additional window-frame lines on **A13**. Inspect this as a supplemental evidence layer; it does not replace the user's AREA/A17 floor and wall mapping. A14 contains projected stair graphics, so do not classify an internal tread-supported gap as a window. Confirm stair direction using the actual arrow-bearing layer and compare against the arrival-floor sheet, but locate and shape the outgoing flight from the departure-floor AREA/A14 geometry. In Alt-4, upper-sheet A14 tread handles 1542/1543/139E depict a different side of the shared core than living-sheet AREA 1575 and treads 1D50/1D53/1D58/1D60; using those upper-sheet treads as the outgoing footprint mirrored the living-to-top stair.

Identify balcony candidates from A14 geometry outside the AREA floor footprint (A14 AND NOT AREA). Check bounded platform edges, access from the interior, adjacency, and railings before classifying them. A14 also contains stair treads, people, cars, and other symbols in this drawing, so set subtraction generates candidates, not automatic balcony slabs. Preserve balcony slabs and railings as distinct from enclosed indoor rooms and roofs.
Do not require balcony linework to polygonize into a closed cell: a three-sided A14 platform can remain open at its A17 facade gap. If an A49 balcony label falls inside it, close the platform only against the verified wall/jamb line, verify it stays outside AREA, and classify the access gap by sill and exterior circulation. Alt-4 living-floor master balcony uses A14 1CBB/1AEE/1CD5 and the adjacent 2.00 m A17 gap; that gap is a floor-level sliding glass door, not a 1 m-sill window.

## Verify Before Reconstruction

List layers directly from the DWG and inspect the layer-preserving DXF. Record entity counts, types, bounds, and representative rendered geometry per floor. A name in the layer table does not establish usable geometry. Inspect nested blocks, inherited layer 0 geometry, layouts, frozen/off layers, and references before declaring a layer empty. Apply block transforms and preserve effective layer ownership; dimension-block graphics are annotation, not structural walls.

Use AREA to locate distinct floors and stair cores before placing walls or objects. If AREA is absent, empty, or cannot establish those locations, ask the user to identify the floor/area and staircase layers. If another supplied layer conflicts with its stated role, show the relevant evidence and ask which layer to use. Do not silently substitute legacy A10/A11 wall heuristics or guess floor/stair rectangles.

Use A24/A49 dimension entities, overrides, text, extension points, and dimension-block geometry to establish units and compare clear wall-face distances. Compare multiple dimensions in each room, including asymmetric anchors. Do not rescale a whole floor to correct a local discrepancy.

Extract A17 wall geometry with the AREA perimeter as a spatial constraint. Pair wall faces and classify hatch boundaries where supported; exclude dimension strokes and furniture edges. Distinguish structural boundaries, room-area contours, stairwells, and roof outlines.

Place A12 doors against verified wall gaps before resolving windows. Use A14 frames and the remaining uncovered portions of the AREA house perimeter as window candidates. A missing contour segment alone is insufficient proof of glazing: exclude entrance doors, open passages, terraces, stair voids, and incomplete extraction. Verify candidate jambs, frame geometry, adjacent walls, and room context. Flag unresolved gaps instead of filling all of them with glass. A floor-level exterior circulation opening is a sliding glass door.

Cluster A34 furniture and A16 sanitation/in-room furniture within verified rooms. A16 is not plumbing-only: classify its objects from shape, blocks, dimensions, and room context. Retain recognizable appliance bays, counter/sink assemblies, and inward-facing fronts. Use dimensions and repeated source symbols to recover sizes and orientation. Deduplicate symbols occurring on both layers by their geometry and room role, while retaining intentional assemblies such as a basin inside a cabinet.

## Fresh Version And QA

Create source-handle provenance and a floor-by-floor audit of contours, stair endpoints, dimensions, walls, doors, windows, and fixtures. Keep unknowns explicit. Earlier user corrections supply useful semantic and visual checks, but old coordinate repairs must not override newly verified layer geometry. Preserve user-selected finishes separately from inferred architecture.

All geometry must share the same coordinate transform. In particular, rotate stair cutout polygons around the same center as the rendered flights and landing; using unrotated L-shaped rectangles still makes a wrong hole. Check both footprint shape and story ownership: an arriving stair opens the upper floor and the lower story ceiling, never the departing stair's own floor.

## Verified V2 Findings

- Some A49 labels use visual-order CP862 Hebrew whose bytes were decoded as CP1252. `tools/cad_text.py` recovers this specific encoding while preserving decimal digit order. Keep the original bytes/handle and check meaningful repeated labels; do not apply an assumed encoding conversion to every drawing.
- AREA is not uniformly a solid slab: living contour **164D** is explicitly labeled a **double-height void above the salon** (A49 189E/15BF). Remove its footprint from the living floor and ground ceiling, but keep the ceiling at the top of that void. A red area outline or crossed rectangle alone is not a room classification.
- Top-floor AREA **D08** describes only the 16.2 m2 bedroom. The user approved deriving the other enclosed top-floor areas from A17 and using the labeled A14 terraces as balconies. Do not give uncovered balconies indoor ceilings.
- Render block definitions before assigning meaning. In this source, **SS01 is a toilet**, **HARSA506 a basin**, **WASH a washing machine**, and **BLMLT a kitchen basin**. These are drawing-specific identifications, not universal block-name rules.
- Apply the complete INSERT matrix, including negative scales, OCS extrusion and block base point. Compute sizes in the native block frame, not a rotated world bounding box. Preserve reflection for asymmetric furnishings; rotation alone cannot reproduce a mirrored corner sofa. Convert each symbol's native front axis to the renderer's front axis explicitly.
- Merge collinear hatch vertices before interpreting wall ends. Align doors using paired jambs or an end-cap-to-wall-face intersection at a T-junction. Swing arcs may be several centimetres off the wall centerline; they supply swing direction, not the host's location.
- Reject apparent wall gaps backed by continuous parallel masonry: these can be recesses rather than glazing. Window width alone cannot distinguish a kitchen counter window from a floor-level patio door.
- Keep source checks and generated-model checks separate. A DIMENSION matching its own extension points only verifies source consistency, not the reconstructed room's clear width.
- Check active faces against the actual renderer, not a universal assumed local axis. In this renderer, beds/sofas/toilets and desks face local +Z, while closets, open wardrobes, laundry cabinets and refrigerators open toward -Z. A sink tap belongs behind its basin, and drawer fronts belong on the room-facing side. An asymmetric corner sofa also needs its verified native back/front axes in addition to its INSERT reflection.
- A CAD desk may already have a separate chair block. Suppress the renderer's built-in desk chair in that case. Treat counter-mounted kitchen basins as components, not an extra complete cabinet intersecting the worktop. Preserve appliance bays as solids or explicit components rather than repeating a refrigerator niche in every tall-storage segment.

## Sections And Vertical Constraints

The user supplied two roof cross-sections on 2026-09-26. Their native curves and
dimensions are recoverable in the same DXF. `tools/inspect_alt4_sections.py`
renders them; `tools/alt4_sections.py` verifies the paired measurements. Section
geometry also uses A10/A11/A13/A14, not just the A17 plan hatches. This is a
section-specific discovery, not permission to discard the user's wall-layer map.

- Both cuts show the same circular structural radius **586 cm**, confirmed by
  A49 labels 9C7/C82 and ARC entities 975/B6F. The inner radius is **566 cm**
  (858/C73); the finish radius is **591 cm** (9BF/C76). The shell is therefore
  **20 cm radially**, plus a 5 cm outer finish. Do not model this as a symmetric
  ellipse based only on the earlier approximate 2 m rise.
- Ground-to-living is **314 cm** (A04/173A). **279 cm** (82C/750) is the ground
  clear height; the remaining **35 cm** is the interstory zone (839/17D6).
  Using 279 cm as the story increment compresses the entire stack.
- Relative to ground finished floor, the structural roof crown is **9.00 m**,
  its center elevation is **3.14 m**, and the outer finish crown is **9.05 m**.
  Both cuts agree after accounting for their different drawing-sheet origins.
- The top story has different levels: **5.724 m** and **6.24 m** in the first
  section, separated by **51.6 cm**. Do not flatten these into one slab or infer
  their plan boundaries from an elevation value alone. Register the cut lines,
  step direction and room enclosures before assigning these levels to objects.
- The section ends trim the common circle differently. A profile radius or
  crown height does not independently prove a roof footprint, overhang, axis,
  or connection to the flat terrace. Verify all of them against both sections
  and the plan before generating roof surfaces and sloped wall tops.

The user clarified the top level on 2026-09-26: its A14 terraces are flat light
gray and open to sky, with no fourth-floor slab above them. Render one continuous
round-roof arc over the A17-derived enclosed wall contour only, extended 10 cm
for drip protection. Across that wall span the 591 cm finish radius gives about
2.05 m rise from the wall-edge baseline. Do not tile the enclosing bounding box
or create a flat top-story ceiling. The rendered ridge is centered on the
enclosed contour to honor this rise; record its offset from the source ridge
label rather than silently presenting the two as identical. Clip enclosed wall
tops against the roof underside and leave terrace walls outside the roof alone.

These section measurements are verified evidence; their integration into the
v2 renderer remains a separate QA gate. Preserve unknown registration and
split-level boundaries in the audit instead of marking the import complete.

Validate source overlays and human-height 3D views before publishing the separately named v2 save. Update only the requested alternative; retain existing saves and their registry entries.
