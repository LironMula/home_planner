# Alternative Reconstruction

Use `tools/build_alternative_v2.py` with the source-specific recipes
`tools/alt3_v2_source.json` and `tools/alt5_v2_source.json`. Earlier presets are
not geometry donors. The recipes retain evidence and uncertainty separately
from the generated-plan/browser audit.

- Inventory layers per sheet, not just per DWG. Native Alt-5 has no AREA;
  Alt-3 AREA exists on ground and living sheets, not its actual basement.
  The user authorized A17 enclosure inference and A14/A13/H stair geometry
  for these two imports. Missing contour layers in another drawing still
  require the layer-discovery question described in the layer contract.
- A17 hatches can span indoor walls, terrace parapets, and retaining walls.
  Split a mixed hatch at verified enclosure boundaries. A tiny indoor
  intersection does not justify extruding the entire hatch to story height.
- Absence of A12 on one sheet does not mean there are no doors. Alt-3's
  living sheet has verified bedroom/bathroom gaps but no door swings.
  Keep gap coordinates source-backed; label inferred leaves, swing direction,
  and head height separately. Leave circulation gaps open.
- Register section X to plan X using several matching wall stations and a
  plan ridge, never the absolute X of the section's arc center. Alt-3's
  586 cm radius describes the finish (581 cm structure, 561 cm underside),
  whereas Alt-5 uses 586 cm structure (591 cm finish, 566 cm underside).
  Transfer neither interpretation between alternatives without checking.
- Preserve split-level slab zones and local steps. These sources have
  5.724 m and 6.240 m upper indoor levels and a 51.6 cm change in three
  risers. Slab elevations, furniture, opening hosts, wall bottoms, and the
  ceiling below must agree. Plan going and section going can differ slightly;
  record the discrepancy instead of shifting the surrounding walls.
- Minor cross-floor shaft offsets are drafting evidence, not permission to
  move a structural reservation. For Alt-3 the user explicitly authorized
  alignment to the ground-floor elevator outline. Preserve that decision
  in its source recipe; do not silently normalize future sources.
- Exploded furniture needs the same completeness review as block furniture:
  beds with nightstands, dining/desk chairs, cabinet appliance bays, and
  bathroom basins. Source-backed bounds plus semantic type are preferable
  to filling an assembly's whole bounding rectangle with one generic item.

Run `tools/render_alternative_overlay.py`, `tools/test_alternatives_v2.py`,
and `tools/check_alternative_v2.cjs` after generation. Review source overlays,
human-height views, floor-only hole raycasts, and top-level roof/terrace views.
Source ambiguities retained in the audit are not validated design dimensions.
