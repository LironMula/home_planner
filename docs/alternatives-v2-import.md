# Alt-3 And Alt-5 V2

Two separate saves are registered in Load GitHub:

- `architect-alt-3-v2`
- `architect-alt-5-v2`

The earlier alternatives are retained. Each new save was reconstructed from
its own native drawing through a fresh layer-preserving DXF conversion.
Alt-4 supplies semantic materials and the surrounding site, not internal house geometry.

## Site And Camera

Both alternatives use the saved `ruchama-18-20-external` surroundings. A final
180-degree house-only rotation aligns the garden-side facade and rear setback
with Alt-4. All floors, opening hosts, stairs, shaft/ceiling holes, fixtures,
and circular roof profiles share that transform; source dimensions do not change.
Roads, fences, trees, pool, and neighboring buildings retain their saved positions.
Lawns are trimmed at ground-floor slabs/terraces, and the seven-piece garden
dining assembly shifts 55 cm outward to keep the chairs clear of the facade.

The default camera stands 4 m outside each alternative's own front door,
at 1.6 m eye height, looking directly toward the entrance. This is an eye-level
entry view, not a copy of Alt-4's saved elevated overview.
The lens is an app-wide browser preference (17 mm by default), not part of a
project save. Loading a plan ignores legacy camera-mode fields.

Internal doors in Alt-3/4/5 v2 use warm taupe/greige `#a89b8c`, per the user's
finish selection. `tools/door_finishes.py` preserves source-reviewed exterior
doors and glass doors, and is shared by the generators. Existing leaf opacity
and opening styles remain unchanged.

Alt-5 kitchen corner correction: the A34 inner L edges were mistaken for two
complete counter bounds, omitting the 63 cm corner. The north run now reaches
the west frame face. A14 handles 117E/1188 and 10F2/10F5 form an L-shaped exterior
window, which the straight-gap detector missed because the corner has no A17
jamb. The recipe explicitly supplies both perpendicular window hosts and panes.
Window widths follow CAD; the 1 m sill and 1.2 m height remain display assumptions.
QA checks counter connectivity, corner coverage, and raycasts both rendered panes.

The Alt-5 living-floor master toilet also lost its window host at a stepped
facade. A14 18C8/FFD/185A and A17 18CA/1991 establish a 110 cm opening in a
25 cm exterior wall. Its recipe now restores the wall below/above the window;
1.2 m sill and 1 m glazing height are explicit display assumptions. Tests check
both wall-end connections and rendered opaque/glass/opaque vertical bands.

Alt-3/4/5 v2 entrance and living floors have user-requested 90 cm opening guards:
clear glass with a slim 4 cm warm-wood top rail (90 cm total, not 90 cm plus rail).
`tools/opening_guards.py` unions actual incoming stair flights/landings with
explicit elevator and double-height holes. It removes existing protective walls,
stair arrivals, and departing stair footprints from eligible edges. It does not
guard unused corners of stair bounding boxes or change other floor levels.
Run it after geometry edits to refresh the generated guards; both importers do
this after site registration. These are visualization details, not engineered
glazing, mounting, or building-code specifications.

`tools/alternative_site.py` also updates existing audited saves without rerunning
CAD extraction, and prevents a second rotation. The importer applies the same
registration after source-space validation. Layer-audit measurements remain in
source coordinates; the site transform is recorded separately in each plan/audit.
Source overlays invert that transform and omit the copied site objects.
Detach shared nested hole dictionaries before transforming split-level slabs:
an in-memory shared hole must not rotate a second time with its other owner.

## Source Decisions

- Both drawings have basement, ground, living, and top-floor sheets.
- Alt-5 has no native AREA layer. Alt-3 AREA is present on the ground and
  living sheets. Missing enclosures were derived from A17 walls and stairs
  from A14/A13/H, as authorized by the user.
- Source recipes retain CAD handles, raw centimetre coordinates, section
  registration, fixture roles, source discrepancies, and inferred details.
- Alt-3's elevator outlines differ slightly across sheets. The user
  authorized one continuous shaft aligned to its ground-floor outline.
- Stairs are reconstructed from individual flights and landings, with
  separate slab openings for the elevator and double-height spaces.
- Both top floors include a 51.6 cm split level. Floor, wall, furniture,
  opening, and lower-ceiling elevations follow the local level zones.
- Roofs share one circular profile per house, clipped to the top enclosure
  plus the requested 10 cm overhang. Alt-3's 586 cm is its finish radius;
  Alt-5's 586 cm is its structural radius. Terraces remain gray and open.
- Upper interior floors use parquet. Bathroom basins use standing-height
  fixtures with mirrors; tall upper fixtures fit beneath the curved roof.

## Limits

These are audited visualization models, not construction documents. Where
the drawings omit door swings or head heights, the model uses a documented
inference. Some hidden split-slab boundaries, exterior thresholds, and
appliance identities remain approximate. Source recipes enumerate these
cases rather than treating them as measured facts.

Alt-5's external basement stair arrival is unresolved and is not fabricated.
Undimensioned parapet heights and roof-mounted equipment are not inferred
as full-height walls or indoor furniture. Source-only discrepancies such as
the Alt-5 upper stair's 20 cm projected-edge difference remain recorded.

## Reproduction And QA

Use the local Python environment containing `ezdxf`, `shapely`, and
`matplotlib`:

```powershell
python tools/build_alternative_v2.py --alternative 3 --source <Alt-3-verified.dxf>
python tools/build_alternative_v2.py --alternative 5 --source <Alt-5-verified.dxf>
python tools/test_alternatives_v2.py
node tools/test_stair_surfaces.cjs
node tools/test_roof_sections.cjs
node tools/check_alternative_v2.cjs
```

`tools/render_alternative_overlay.py` produces CAD/model overlays for each
floor. Browser QA captures desktop floor, cutaway, human-height, four exterior,
and mobile fullscreen views; samples the WebGL canvas; checks fixture/floor
textures; and ray-tests stair/void openings. Browser results include the
tested plan's SHA-256 so stale results cannot approve a newer save.

The generated audits are `alt3-v2-layer-audit.json` and
`alt5-v2-layer-audit.json`. Regeneration resets their publication status;
only finalize after source and visual review with
`tools/finalize_alternative_audit.py --source-and-visual-reviewed 3 5`.
