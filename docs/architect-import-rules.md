# Architect Import Rules

Compact record for applying the Alt-4 corrections to later architect designs.

## Transform

- Convert CAD centimetres to planner metres and invert the CAD Y axis.
- Build every floor in one shared local coordinate system.
- Place the house on the saved site, then rotate the complete house 180 degrees around the ground-slab center. Rotate item centers and rotations together; reverse roof tilt directions. Do not rotate site context.

## Openings And Fixtures

- Anchor windows and doors to CAD wall centerlines or explicit wall gaps, not nearby annotation geometry.
- Reconstruct a host-wall span behind every CAD window gap; the 3D cutout then preserves the wall above and below instead of dropping the complete edge.
- Alt-4 kitchen window: 3.85 m opening centered at `(11.51, 9.71)` before site placement.
- Alt-4 guest WC exterior: add a 0.80 m privacy window with a 1.75 m sill in the recovered exterior wall.
- Keep counters against the inside wall face. Place sinks inside the counter footprint.
- Alt-4 guest WC: entrance in the east wall, toilet north/right of entry, basin south/left of entry.
- Add a wall-mounted mirror above every non-kitchen sink, aligned to and facing inward from its nearest CAD wall.
- Add missing semantic objects, such as the guest-WC door, when the CAD symbol is exploded and cannot be collected reliably.
- Fit paired entrance leaves to the adjacent wall posts so they meet at the center; use dark wood for the main entrance and light cream for internal doors.
- Raise the integrated kitchen sink so its basin rim is flush with the 0.92 m work surface and its tap remains exposed.
- Use light-gray granite on the entrance floor and parquet on the living floor. Render an opaque ceiling only while the camera is inside that floor.
- Place the master bed from its full green CAD footprint and hang the wide waterfall-and-woods artwork on its head wall.

## Site Context

- Copy fence, road, trees, neighboring buildings, and garden furniture from `house_3d_view_alt4_ron_limor_yahal`.
- Copy grass regions, pool, and outdoor ninja set from `ruchama_20_v01_2026_05_30`.
- Site objects remain on the ground floor and are never included in the house rotation.

## QA

- Check every window center against its intended wall and verify its 3D cutout.
- Check door centers against wall gaps and verify swing direction after rotation.
- Check counters touch walls, sinks overlap counters, and sanitary fixtures remain inside their rooms.
- Review all floors together for a shared footprint and review each floor separately for local alignment.
