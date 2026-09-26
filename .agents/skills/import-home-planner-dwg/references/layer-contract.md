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

Identify balcony candidates from A14 geometry outside the AREA floor footprint (A14 AND NOT AREA). Check bounded platform edges, access from the interior, adjacency, and railings before classifying them. A14 also contains stair treads, people, cars, and other symbols in this drawing, so set subtraction generates candidates, not automatic balcony slabs. Preserve balcony slabs and railings as distinct from enclosed indoor rooms and roofs.

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

Validate source overlays and human-height 3D views before publishing the separately named v2 save. Update only the requested alternative; retain existing saves and their registry entries.
