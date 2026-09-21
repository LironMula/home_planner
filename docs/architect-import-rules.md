# Architect Import Rules

Compact record for applying the Alt-4 corrections to later architect designs.

## Transform

- Convert CAD centimetres to planner metres and invert the CAD Y axis.
- Build every floor in one shared local coordinate system.
- Place the house on the saved site, then rotate the complete house 180 degrees around the ground-slab center. Rotate item centers and rotations together; reverse roof tilt directions. Do not rotate site context.

## Openings And Fixtures

- Anchor windows and doors to CAD wall centerlines or explicit wall gaps, not nearby annotation geometry.
- For Alt-4 windows, use the center and orientation of each yellow CAD frame pair. Do not snap its center along the wall to the nearest surviving wall fragment, because that fragment usually ends at the window gap.
- Reconstruct a host-wall span behind every CAD window gap; the 3D cutout then preserves the wall above and below instead of dropping the complete edge.
- Alt-4 kitchen window: 3.85 m opening centered at `(11.51, 9.71)` before site placement.
- Alt-4 guest WC exterior: add a 0.80 m privacy window with a 1.75 m sill in the recovered exterior wall.
- Keep counters against the inside wall face. Place sinks inside the counter footprint.
- Alt-4 guest WC: entrance in the east wall, toilet north/right of entry, basin south/left of entry.
- Add a wall-mounted mirror above every non-kitchen sink, aligned to and facing inward from its nearest CAD wall.
- Add missing semantic objects, such as the guest-WC door, when the CAD symbol is exploded and cannot be collected reliably.
- Fit paired entrance leaves to the adjacent wall posts so they meet at the center; use dark wood for the main entrance and light cream for internal doors.
- Raise the integrated kitchen sink so its basin rim is flush with the 0.92 m work surface and its tap remains exposed.
- Use light-gray granite on the entrance floor and parquet on the living floor. Preserve those finishes on the upper face of each floor layer.
- Mark imported architectural slabs as structural so the Spaces toggle and wall-overlap suppression cannot hide them. Render every selected story as two separate surfaces: its own colored or finished floor above and an opaque white ceiling below. Both surfaces belong to that story, follow the 3D floor selector, and hide together with the Floor control.
- Store house walls as solid `#ffffff`; keep translucency only for glass and site/context geometry. Add a small white emissive contribution in 3D so white walls and ceilings remain visually white under scene lighting.
- Store Alt-4 stair treads and landings as solid white, using the same architectural-white 3D material and a restrained gray outline for 2D plan legibility.
- Fit adjoining roof sections exactly to the structural room footprint beneath them, with no perimeter overhang, gap, or overlap. The Alt-4 barrel roof rises exactly 2.00 m from its base edges to its crown.
- Recover the Alt-4 kitchen and guest-WC exterior edge as one continuous wall, then cut the kitchen window and high privacy window from that host wall.
- Reconstruct the 2.40 m wall span between the kitchen and outdoor dining area with a centered 2.10 m sliding window at counter height.
- Kitchen base-cabinet handles must face the room. In the final Alt-4 site orientation, use 180 degrees for the long run and 270 degrees for the perpendicular return after swapping its width/depth.
- Treat exploded green furniture linework as semantic objects: distinguish beds, X-marked closets, and desk-plus-chair symbols instead of assigning every rectangle to a generic table.
- In paired bedrooms, rebuild both sets of bed, closet, study desk, chair, and doorway. A study desk includes a monitor and books; internal doors use the light-cream finish.
- Pantry storage uses the two complete 4.15 m opposing cabinet runs. Orient both fronts toward the pantry and render one visible handle per door panel.
- Keep the two source sofas and coffee table as separate living-room objects, remove duplicate manual sofas, and place a rug beneath the group.
- Keep one rectangular table and six chairs outside the kitchen; omit the extra round lounge table and its three chairs.
- Preserve the Alt-4 salon perimeter as separate CAD segments: a solid wall behind the corner sofa, a completely open exterior span after the sofa, and the solid east TV wall. Do not reinterpret those cyan wall lines as windows; rotate the corner sofa 180 degrees to face into the salon.
- Keep separate window records for each yellow opening on the living floor; do not merge adjacent bedroom windows across the wall between their rooms.
- The master bed is 2.00 x 2.10 m with its head toward the walk-in closet and its feet toward the exterior. Put the wide waterfall artwork on the wall facing the bed, use a detailed warm wallpaper of leaves and abstract embracing hands on the neighbor wall, and retain the sliding window opening toward the porch.
- Recover the solid exterior wall band beside the master-bedroom porch window before mounting the waterfall artwork; never leave wall art floating across an unreconstructed opening.
- Reconstruct the master walk-in closet as two opposing 3.25 m ceiling-height open wardrobe banks, 0.45 m and 0.60 m deep, with a 0.90 m clear aisle. Center its light-cream door on that aisle rather than on the adjacent bedroom wall.
- Do not promote the exploded front edge of either open wardrobe into a structural wall; a false 1.80 m wall trace through the Alt-4 walk-in aisle must be suppressed.
- Reconstruct the walk-in entrance wall as a continuous host before cutting its centered 1.00 m door opening; do not attach the door to a short neighboring CAD fragment.
- Alt-4 master bathroom: use the 2.90 x 1.85 m enclosure. Put the full-depth dual rain shower immediately left of the translucent-white entrance, close it with a movable glass splash partition, place the drawer vanity and mirror to its right along the lower wall, and put the toilet after the door facing back toward the shower.
- Alt-4 living-floor bathroom: keep the entrance at the south edge, bath immediately left of the door, wood-base sink and mirror immediately right, toilet farther along the sink wall, and an open washer/dryer closet with upper storage beyond the bath.
- Decorative wall finishes are thin, wall-aligned elements and must not replace or suppress the structural wall behind them.

## Site Context

- Copy fence, road, trees, neighboring buildings, and garden furniture from `house_3d_view_alt4_ron_limor_yahal`.
- Copy grass regions, pool, and outdoor ninja set from `ruchama_20_v01_2026_05_30`.
- Site objects remain on the ground floor and are never included in the house rotation.

## QA

- Check every window center against its intended wall and verify its 3D cutout.
- For rotated host walls, project the window, snap target, wall cutout, and rendered pane through the same wall-local transform; never position the pane from the wall's unrotated bounding box. If more than one nearby wall fragment qualifies, render against the host whose projected center is closest to the saved opening center.
- Check door centers against wall gaps and verify swing direction after rotation.
- Check counters touch walls, sinks overlap counters, and sanitary fixtures remain inside their rooms.
- Check every repeated cabinet run for complete length, inward-facing fronts, panel divisions, and visible handles.
- Compare imported furniture symbols as a room set so duplicate sofas, missing desks, and incomplete wardrobes are caught together.
- Review all floors together for a shared footprint and review each floor separately for local alignment.
