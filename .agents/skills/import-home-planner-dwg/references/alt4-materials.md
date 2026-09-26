# Alt-4 Colors And Finishes

## Authority And Transfer

The user designates the existing Alt-4 as the appearance authority for the fresh
Alt-4 v2 import. Read `plans/architect-alt-4-sheet-1.json` before assigning styles.
The inventory below was checked on 2026-09-26 against that file and
`plans/architect-alt-4-sheet-11.json`: their sets of 56 distinct style profiles
match, although their object counts and geometry differ. Recheck the actual
files on later imports; these tables are a verified reference, not permission
to overwrite newer saved choices.

- The saved role-specific appearance wins over older prose, CAD entity colors,
  and generic generator defaults. CAD colors identify drawing semantics; they
  are not paint specifications.
- Match by floor, room, and role. A pantry cabinet, bedroom wardrobe, and open
  closet are different profiles even when all provide storage. Indoor chairs
  and garden chairs also differ. Do not use the first matching element kind.
- Transfer `color`, `opacity`, `finish`, and `type1` where applicable. Preserve
  the relevant `openingStyle` and `glass` behavior for an independently verified
  opening type. Do not convert a solid door into glazing just to match a color.
- Reconstruct geometry from the DWG. A style donor supplies no coordinates,
  dimensions, rotations, wall hosts, stair handedness, or source-floor choice.
  In particular, do not copy the old detailed-basement layout into v2's
  user-selected AREA-contoured basement.
- A missing role needs an explicit, documented style choice or clarification.
  Do not add an object solely because it exists in the old style inventory.
- Opacity below 1 is intentional in many saved furniture profiles, not just
  glass. Keep those saved values; structural house walls and stair treads are
  explicitly opaque. View-control opacity is a separate runtime multiplier.

## Floors And Structure

| Role | Saved color | Saved opacity | Finish or qualification |
|---|---|---|---|
| Basement floor | `#7c3aed` | Not stored on floor | `finish: null` |
| Ground/entrance floor | `#0f766e` | Not stored on floor | `light-gray-granite` |
| Living floor | `#2563eb` | Not stored on floor | `parquet` |
| Floor 2 | `#b45309` | Not stored on floor | `finish: null` |
| Floor-2 outdoor terraces | `#d9dee5` | 1 in 3D | Flat light-gray surface, open to sky; never inherit the orange floor swatch |
| Structural slab plan fill | `#d9dee5` | 0.94 | Not the rendered floor-finish color |
| House walls | `#fefdfa` | 1 | Established 90% white / 10% cream appearance |
| Stairs and landings | `#3d2418` | 1 | `type1: dark-wood` |
| Flat roof | `#91857d` | 0.88 | Appearance only; independently verify roof existence and footprint |
| Round tiled roof | `#ad5636` | 0.9 | Appearance only; independently verify roof geometry |
| Plan boundary guides | `#94a3b8` | 0.12 | Guides, not structural walls |

The renderer uses the floor's color for an untextured structural floor, but
`applyFloorFinish` replaces that tint with white under its texture. Thus the
ground floor must appear as light-gray granite, not teal; the living floor must
appear as parquet, not blue. Preserve the finish names, not a screenshot-sampled
lit color. The slab's 2D gray fill is a third, separate value.

Ceiling undersides are renderer-owned pure white (`#ffffff`), opaque,
double-sided, unshaded, and not tone-mapped (`applyCeilingWhiteMaterial`). Never
reuse the floor texture or the cream wall material for them.

`applyArchitecturalWallMaterial` supplies the wall tint and a matching emissive
contribution (0.28). Its edge color is `#7d858c`, opacity 0.96. The requested
physical edge width is 2 cm. Current code stores that width as metadata and uses
`LineBasicMaterial` with `linewidth: 2`; that does **not** prove a world-space
2 cm strip renders on every WebGL implementation. Check actual edge visibility
and width separately; do not claim the metadata alone satisfies that requirement.

## Doors And Glazing

| Role | Color | Opacity | Saved variant |
|---|---|---|---|
| Ordinary internal doors | `#f3ead7` | 0.9 | Standard door |
| Living-floor bedroom, shared-bathroom, and master-suite entries | `#f3ead7` | 0.94 | Standard door |
| Paired main entrance leaves | `#4a2c1b` | 0.96 | Dark wood |
| Ordinary windows | `#45a9d8` | 0.62 | Standard window |
| Salon and master-bedroom movable windows | `#45a9d8` | 0.62 | `openingStyle: sliding` |
| Kitchen exterior sliding glass door | `#45a9d8` | 0.62 | `openingStyle: sliding`, `glass: true` |
| Master bathroom entrance | `#fefdfa` | 0.5 | `openingStyle: translucent` |
| Movable shower partition element | `#9bdff0` | 0.52 | `sliding-window-opening`, `type1: shower-partition` |

Do not substitute the sink's cyan `#70b7c8` for exterior glazing. The translucent
bathroom door is neither a normal cream door nor a blue exterior window.

## Kitchen And Storage

| Role | Color | Opacity | Material selector |
|---|---|---|---|
| Kitchen work surfaces, including return | `#15171a` | 0.9 | `black-navy-gold` |
| Kitchen island base | `#d6c6ad` | 0.9 | `dark-wood-top` |
| Pantry north and tall side storage | `#9c8269` | 0.9 | `kitchen-tall-storage` |
| Pantry south storage | `#9c8269` | 0.9 | No `type1` |
| Refrigerator | `#d8dee8` | 1 | No `type1` |
| Oven | `#2c2e30` | 0.86 | No `type1` |
| Bedroom closets and floor-2 storage | `#8b6145` | 0.9 | No `type1` |
| Master walk-in open wardrobe banks | `#9b7653` | 0.96 | `open-closet` element |
| Bathroom laundry closet | `#a9825f` | 0.97 | `laundry-closet` element |

The kitchen `black-navy-gold` variant is required in addition to its base color:
both countertop and room-facing fronts use width bands of **80% `#15171a`,
10% `#17324d`, and 10% `#b89146`**. It is not a blended single paint color. Retain
the renderer's gold pulls and material properties.

The island's `dark-wood-top` variant selects the dark-walnut top `#3d2418`, with
board/grain details (`#6b4028`, `#24150f`, `#7b4b2d`). The saved base stays
`#d6c6ad`; do not recolor the whole island dark brown.

## Furniture, Bathrooms, And Decoration

| Role | Color | Opacity | Variant or appearance detail |
|---|---|---|---|
| Beds | `#94a3b8` | 0.9 | All saved beds |
| Indoor chairs | `#8ab17d` | 0.9 | Separate from garden chairs |
| Sofas and corner sofa | `#b7846f` | 0.9 | Preserve the distinct element kinds |
| Indoor tables and study desks | `#b08968` | 0.9 | Preserve desk modeling |
| Salon rug | `#b9a58e` | 0.82 | Rug |
| Salon TV | `#111827` | 1 | `type1: wall-mounted`; renderer supplies screen details |
| Basins and kitchen sinks | `#70b7c8` | 0.9 | Renderer supplies basin, tap, and cabinet submaterials |
| Master bathroom vanity | `#70b7c8` | 0.9 | `type1: drawer-vanity` |
| Mirrors | `#b9d5df` | 0.94 | Reflection plus renderer-owned frame |
| Ordinary toilets | `#e8edf2` | 0.9 | Do not overwrite role-specific white toilets |
| Living bathroom and master bathroom toilets | `#ffffff` | 0.98 | Role-specific override |
| Bath | `#d9f0f5` | 0.9 | Bath |
| Ordinary showers | `#9bd5e5` | 0.9 | Shower |
| Master dual shower | `#9bd5e5` | 0.92 | `type1: dual-rain` |
| Guest bathroom botanical wallpaper | `#eee6d8` | 0.98 | Default botanical variant |
| Master bedroom wallpaper | `#eadfd5` | 0.98 | `type1: embracing-leaves` |
| Master waterfall artwork | `#ffffff` | 0.9 | Existing artwork texture, not a plain white panel |

Wallpaper/artwork colors are backing colors, not substitutes for their visuals.
The guest wallpaper renderer adds green `#78906f` foliage and `#c9a878` flowers.
The master wallpaper uses `masterBedroomWallpaperTexture` for the warm leaves
and embracing hands. The waterfall uses `assets/master-bedroom-waterfall.png`.
Keep the existing renderer/assets and the 1 cm wall-mounted wallpaper thickness;
do not generate new artwork merely to restore its saved color.

## Site Palette

| Role | Color | Opacity | Qualification |
|---|---|---|---|
| Property border walls | `#22c55e` | 0.92 | Not house-wall paint |
| Trees | `#2f7d32` | 0.86 | Existing avocado-tree role |
| Neighbor buildings | `#8b95a1` | 0.86 | Default site building profile |
| White neighbor building | `#fafcff` | 0.86 | Preserve its distinct saved role |
| Roads | `#2f343b` | 0.86 | Site only |
| Grass | `#4f9d4e` | 0.86 | Site only |
| Pool | `#38bdf8` | 0.86 | `type1: round` |
| Outdoor exercise set | `#475569` | 0.86 | `ninja-set` |
| Garden dining table | `#b08968` | 0.86 | Different opacity from indoor tables |
| Garden chairs | `#647f56` | 0.9 | Different color from indoor chairs |

## Verification

1. Inventory the authoritative save by collection, element kind, floor/room
   role, and the full style tuple, including absent selectors. Compare profiles,
   not array order or total object counts across alternative saves.
2. Assign each newly reconstructed role a style donor or a documented unresolved
   choice. Copy only appearance fields; never let this step change geometry.
3. Compare new serialized style tuples to their donors, including opacity and
   finish/type selectors. Explicitly check both ordinary and special variants.
4. Inspect 2D and 3D independently: finishes, lighting, hardcoded submaterials,
   texture assets, and view opacity can make matching JSON look different.
5. Preserve the old saves. Do not call the rebuild material-verified until the
   new plan and its rendered finishes have also passed, not just this reference.
