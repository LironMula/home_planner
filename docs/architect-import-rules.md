# Architect Import Rules

Compact record for applying the Alt-4 corrections to later architect designs.

## Transform

- Convert CAD centimetres to planner metres and invert the CAD Y axis.
- Build every floor in one shared local coordinate system.
- Place the house on the saved site, then rotate the complete house 180 degrees around the ground-slab center. Rotate item centers and rotations together; reverse roof tilt directions. Do not rotate site context.

## Openings And Fixtures

- Anchor windows and doors to CAD wall centerlines or explicit wall gaps, not nearby annotation geometry.
- Alt-4 kitchen window: 3.85 m opening centered at `(11.51, 9.71)` before site placement.
- Keep counters against the inside wall face. Place sinks inside the counter footprint.
- Alt-4 guest WC: entrance in the east wall, toilet north/right of entry, basin south/left of entry.
- Add missing semantic objects, such as the guest-WC door, when the CAD symbol is exploded and cannot be collected reliably.

## Site Context

- Copy fence, road, trees, neighboring buildings, and garden furniture from `house_3d_view_alt4_ron_limor_yahal`.
- Copy grass regions, pool, and outdoor ninja set from `ruchama_20_v01_2026_05_30`.
- Site objects remain on the ground floor and are never included in the house rotation.

## QA

- Check every window center against its intended wall and verify its 3D cutout.
- Check door centers against wall gaps and verify swing direction after rotation.
- Check counters touch walls, sinks overlap counters, and sanitary fixtures remain inside their rooms.
- Review all floors together for a shared footprint and review each floor separately for local alignment.
