# Forever-specific research and decisions

## 0.2.0 expansion update — supersedes the pilot-only limitations below

The readable prefix of local Map.db2 contains one **complete unencrypted section of 73 records**. Its remaining eight records are in three encrypted sections. The new `world_maps.py` parser validates WDC5 layout D43AFAC3, section bounds, field storage and name pointers; it decodes only the complete unencrypted section, never missing bytes or zero substitutions. This provides current-build map IDs, WDT IDs and OceanLiquidTypeIDs directly from the installed client. The original strict whole-file read still correctly rejects Map.db2 as incomplete.

`build_world.py` extracted 3,322 complete ADT tiles across 48 maps, grouped into 351 load-on-demand packs. All requested nonzero WDT terrain references on these 48 maps parsed successfully. Maps with WMO-only interiors, absent WDTs or unreadable WDT files are reported separately. Eight encrypted map records remain unidentified. This is not universal walkable-surface coverage.

Depth uses each map's OceanLiquidTypeID, actual MH2O existence masks and checked flat water surfaces. LiquidType WDC5 layout D1ECEEC9 and LiquidMaterial layout 98E5D7AA are verified locally. Ocean types 1250/1296 resolve through material 130 to vertex format 0. Legacy ocean type 2 uses the depth-only format special case. The latter distinction matters: depth bytes are not float32 water heights. Missing vertex offsets and depth-only layouts imply zero surface height only when the record's min/max also agree at zero. Height-bearing layers have every float32 height checked. Unsupported/nonflat records are rejected, not approximated. Format semantics were cross-checked against [TrinityCore's extractor](https://github.com/TrinityCore/TrinityCore/blob/master/src/tools/map_extractor/System.cpp) and [liquid structures](https://github.com/TrinityCore/TrinityCore/blob/master/src/tools/map_extractor/adt.h), then validated against the installed tables and files. No third-party source code is bundled.

All accepted ocean surfaces in this extraction are world Z=0. Maps without accepted ocean layers keep an explicitly labelled world reference. The automatic depth value is water-surface Z minus ADT terrain Z, never player Z. Lakes and rivers do not automatically inherit the ocean type or level. Cities stay hidden.

Runtime tile lookup now uses the validated map lattice and at most nine neighbouring index entries. It does not scan the worldwide index. Each visited 4x4-tile pack stays loaded until reload/logout; no unsupported addon-unload mechanism is used. Initial live evidence is limited to the user's report that the gauge increases while climbing natural Elwynn terrain. World expansion and depth switching still need live checks.

## Historical pilot investigation

Inspected 2026-11-09, before implementing the addon calculation: existing workspace and installed Forever `.flavor.info`, executable version, `.build.info`, build configuration, installed position-library usage, actual CASC files, client API documentation and current public terrain tooling. The workspace root is not a Git repository; no existing addon was changed. There was no root AGENTS.md.

## Owning local data

`_forever_/.flavor.info` identifies `wowf`; executable and active product build identify **1.60.1.70862**. The shared `Data` archive also contains Era, so extraction explicitly opens `World of Warcraft*wowf`, never whichever product happens to be first. Build key: `5ada954223f7c409ea172361f5c9e565`.

The [wowdev listfile release](https://github.com/wowdev/wow-listfile/releases/tag/202611072341) supplied filename-to-file-ID discovery only. It is not the height dataset. Root WDT file ID **775971**, `world/maps/azeroth/azeroth.wdt`, was read from this product. Its MAID records reference all pilot root ADTs. For example WDT (32,48) references **778027**, whose parsed first chunk is north=-8533.333984375, west=0, base height=233.5927734375 and area ID=12. MAI2 references tested on (32,48) and (31,49) resolve to BLP2 textures, not a replacement height mesh; these were not used as heights.

Every root ADT contains version 18 and 256 MCNK chunks, each with a 128-byte header and a 580-byte MCVT block (145 float32 offsets). Both high-resolution and legacy holes are supported. Unknown/malformed structures are rejected, not guessed. Format interpretation was cross-checked with [TrinityCore's ADT structures](https://github.com/TrinityCore/TrinityCore/blob/master/src/tools/map_extractor/adt.h), [its extractor](https://github.com/TrinityCore/TrinityCore/blob/master/src/tools/map_extractor/System.cpp) and [WoWMap's mesh reader](https://github.com/miceiken/WoWMap/blob/master/WoWMap/Layers/MapChunk.cs), then validated against the actual Forever headers. No third-party terrain code is bundled.

## APIs: signatures versus observed behavior

`research/MapDocumentation.lua` and `research/UnitDocumentation.lua` were extracted directly from this installed client. UnitPosition declares X, Y, Z and world map ID; C_Map provides player map coordinates and map-to-world conversion. The [Forever UI source mirror](https://github.com/Gethe/wow-ui-source/tree/forever/Interface/AddOns/Blizzard_APIDocumentationGenerated) was also consulted. **Signatures do not prove runtime values or absence of restrictions.**

The first UnitPosition component is treated as the north/south world coordinate, the second as west/east; this agrees with installed HereBeDragons' usage and the client map conversion conventions. The runtime compares these APIs when both are available. No combat or instance restriction is bypassed. API Z is diagnostic only. Whether Z is always zero on this exact build remains an open live question; no successful in-game probe has been recorded here.

## Coordinate derivation and interpolation

Use `N` for the first world component and `W` for the second. A tile has 16×16 chunks, each with an 8×8 grid of cells and a centre vertex in every cell. Tile span is 1600/3 yards, chunk span 100/3, cell span 25/6. These standard format dimensions are validated against the installed chunk header positions rather than assumed from the game flavour.

For tile column `tx`, row `ty`, chunk column `ix`, row `iy`, the expected header basis is:

```
N = (32 - ty) * (1600/3) - iy * (100/3)
W = (32 - tx) * (1600/3) - ix * (100/3)
```

The parser verifies this for every chunk within 0.004 yard (float32 coordinate rounding). The manifest indexes **stored actual tile origins**, not an arbitrary global shift. Runtime local cell coordinates are derived from each selected **stored chunk origin**:

```
u = (chunkWest  - playerWest)  / (25/6)
v = (chunkNorth - playerNorth) / (25/6)
```

At boundaries only, up to 0.004 yard is allowed for float32-origin gaps/overlaps; it snaps to the selected mesh edge. This is documented spatial tolerance, not height precision. Extremely steep terrain can amplify horizontal error. Total live measurement error is not known.

MCVT rows alternate 9 outer and 8 centre vertices. For cell column c,row r, zero-based top-left index is `17*r+c`, top-right +1, bottom-left +17, bottom-right +18 and centre +9. Heights are MCNK base Z + MCVT float32 offset. Select one of four centre-fan triangles using local u,v, then apply its barycentric weights. Bilinear interpolation would ignore the centre and is not used. Hole bits suppress the corresponding cell.

## Sea-level evidence

Local file ID **1371380**, LiquidType.db2, uses WDC5 layout **D1ECEEC9**, a layout explicitly listing this Forever build in [WoWDBDefs](https://github.com/wowdev/WoWDBDefs/blob/master/definitions/LiquidType.dbd). Its structural layout was checked against the [DBCD reader](https://github.com/wowdev/DBCD/blob/master/DBCD.IO/Readers/WDC5Reader.cs). The narrow calibration reader verifies the actual header, section shape and name encoding before using record 1250, named **PBRWater - Generic - Ocean**. Its sound-bank field is 0, so an old rule equating only SoundBank=1 with ocean would be wrong for this Forever data.

Tiles (28,47), (28,48), (29,48), file IDs 777222/777227/777427, contain 256+256+189 such ocean layers. Their inspected format-42, full 8×8-cell records contain 81 float32 height values plus depth values; all 56,781 heights and all layer min/max values are exactly 0. The tool rejects different layouts, bounds, formats or nonzero heights. SHA-256/build identities bind this evidence to the generated pilot. This establishes **world Z=0 as the regional static harbour ocean datum**, without claiming every map shares it. Inland lakes and rivers have different heights.

## Public atlas investigation

The supplied [60.tools terrain map 451](https://www.60.tools/map/terrain/451) is **Development Land**, not Elwynn. Its terrain atlas advertises beta **1.60.1.69893**, distinct from the site's general database header and from this install. The browser-delivered `terrain-atlas-DpLwswvO.js` requests `/maps/atlas/<build>/<map>/map.json` and `<x>-<y>.bin`. Its terrain loader accepts 33×33 or 129×129 float32 grids and builds two triangles per grid cell; this is not the full 145-vertex-per-chunk centre-fan mesh. Public files are downloadable, but no reusable data license was verified and the build/geometry do not meet this task's accuracy requirement. None of its height payloads was used. Its landmark metadata helped choose a conservative pilot extent.

## Forever versus Era

Read-only comparison with installed Era **1.15.9.70576**, using the same pilot file IDs where present, found **27/40 tiles and 2,473/10,240 chunks differ in heights and/or holes**. See `research/era-comparison.json`. This is a geometry comparison, not merely byte-hash differences caused by textures. No Era data was inserted into the addon. Comparison does not establish anything about uninspected world regions.

## Precise remaining blockers

- **Live validation requires a running Forever character and user observations.** We did not drive the game or claim an in-game test. Diagnostics are installed to collect coordinates and Z across ground, hill and jump samples. The requested end-to-end success criterion remains open until those tests pass.
- Local Map.db2 file ID **1349477** opens but strict CascReadFile fails with **error 6002**, after 9,652 of 10,209 bytes. CascLib identifies this error as `ERROR_FILE_ENCRYPTED`. No zero-filling, key guessing, or unrelated Map table is substituted. The pilot's Azeroth/world-0 association is supported by filename/WDT/header/atlas evidence and still needs the live map-ID check. Full Map.db2 metadata is required before claiming generic multi-world generation. UiMapAssignment.db2 and LiquidType.db2 were readable, but the runtime uses the installed client's own map conversion rather than adding a DB2-zone-offset dependency.
- Expansion is gated on the initial live proof of concept. This release contains only one map's pilot extent. Other continents, phase-specific geometry, object meshes and indoor floors are unsupported.

The extractor itself is not blocked: all pilot terrain files and the regional water calibration were successfully read from the authorized local install. All work used file reads and permitted addon APIs.
