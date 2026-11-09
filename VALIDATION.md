# Release acceptance � 9 November 2026

The user confirmed: "nice all tested and ready to go" after testing the current UI and addon in-game. No per-map test log was supplied; this records acceptance without claiming exhaustive world coverage.

The historical pilot checklist below predates the world expansion. Current coverage and limits are documented in README.md and build-world/coverage.json.

# Validation record and field procedure

## 0.2.0 world expansion and depth

The expanded suite (`tests/test_world.py`) checks the local Map/LiquidType/LiquidMaterial layouts, refuses truncated or incompatible metadata, verifies cell-level ocean masks, tests the legacy depth-only ocean format, and exercises altitude/depth transitions in Lua 5.1. Display cases include 100 yards seabed depth → 91.4 m, dry terrain at -100 yards staying in altitude mode, 102 yards → +93.3 m, and unavailable data clearing the prior reading.

Every one of the 3,322 generated tiles is compared against its cached local source SHA-256 and sampled at four triangle centroids in a deterministically selected actual chunk. The runtime's world lookup, height result and ocean mask/level are checked. The original 40,960 pilot triangle checks remain available separately. Encoding tolerance is 0.0005 yard; this is not total live accuracy.

Live checks for this version: fully restart WoW to discover the 351 data packs; check that Darkshore now reads ground altitude. Walk or swim over ocean seabed and check that the face changes to DEPTH/SEABED, then returns on land. Diving straight down must not change the seabed-depth reading at the same horizontal position. Test a lake and below-zero dry ground to ensure neither is mistaken for ocean. Check that city hiding still applies. The expanded release is not claimed in-game validated.

The later expansion replaces the pilot expansion gate below. The user has since reported increasing readings while climbing natural Elwynn terrain, but has not supplied independent absolute-height validation.

## Offline result — 2026-11-09

Source: local Forever product `wowf`, version 1.60.1.70862. All 40 requested tiles extracted; zero missing or rejected tiles. All 10,240 chunk headers match the WDT coordinate basis within 0.004 yard. All 1,484,800 source heights are finite and round-trip through the encoding within 0.0005 yard.

Lua 5.1 tests check the real shipped calculation against the arithmetic means of the three actual ADT vertices at 40,960 triangle centroids/hole locations. The same checks exercise world-coordinate lookup against each chunk's stored origin. Largest observed height error was **0.000492767 yard**, excluding boundary snapping. This is **not measured player-position accuracy**.

Additional tests cover a centre-vertex spike that bilinear interpolation cannot reproduce, negative/sloping planes, hole masks, missing coverage, combat-deferred tile loads, tile/chunk boundaries, malformed and incompatible files, NaN heights, client-build mismatch, restricted API fallback, unavailable readings, diagnostics, and independence from player Z. Calibration tests reject changed layout or nonzero ocean vertices.

## Live status

**Not tested in-game.** No evidence yet proves that live player coordinates land on the correct Forever terrain triangles or that the user-visible movement criterion passes. UI loading, movement, timer overhead, SavedVariables and actual secret-value behavior remain live checks. Do not advance to whole-world coverage until these pass.

## First session

1. Restart WoW; enable the main addon and its tile modules. Enter outdoor Elwynn, on visible bare terrain away from objects. Run `/altitude debug`. Confirm build 70862, world map 0, finite north/west coordinates, a pilot tile, and no API mismatch. Record the location in the sample note.
2. Run `/altitude sample ground`. Move uphill on the same visible terrain surface and run `/altitude sample uphill`. Return downhill and sample again. Terrain elevation should track the route, without assuming that a visually uphill path cannot include a flat patch.
3. Stand still and sample `standing`, then sample `jumping` in mid-jump. Repeat at higher ground. Terrain should remain the same at the same horizontal position. Inspect whether API Z stays zero, changes, or becomes unavailable. A single zero is insufficient to prove that Z is always zero.
4. `/reload` to save observations. Inspect `AltimeterForever.lua` under account SavedVariables. Compare recorded world coordinates against the source ADT triangle geometry using the matching file ID/hash in the manifest. Agreement between two position APIs is useful but does not by itself validate the world-to-terrain association.
5. Confirm subzone/landmark placement at several separated points: Goldshire, Northshire, Eastvale, Stormwind gate and harbour. This catches swapped axes, wrong world-map identity and offsets. Do not infer a correction from one point or silently change origins.

## Full pilot checklist

| Case | Required observation |
| --- | --- |
| Flat bare ground | Stable terrain value; compare actual triangle vertices |
| Hills/mountains | Correct signed changes along the sampled coordinates; inspect steep triangles |
| Harbour coast/beach | Compare terrain with extracted ocean datum, not character swimming offset |
| Underwater seabed | Negative terrain elevations where actual ADT vertices are below zero |
| Adjacent tile boundaries | Sample both sides; investigate any discontinuity against source edge vertices |
| Chunk/cell boundaries | Check continuity where the real mesh shares an edge; permit actual source seams |
| Bridge/building/roof | Reading describes underlying terrain; never label it walkable surface or player altitude |
| Cave entrance | ADT hole reports unavailable; interior terrain, if present, does not represent the cave floor |
| Jump/fall/swim | Player Z must not replace terrain; horizontal motion may legitimately change terrain |
| Instance/other continent | Unavailable, without stale values |
| New tile in combat | If not previously loaded: unavailable, then recovers after combat |
| Client update | Build mismatch blocks readings |
| Restart/reload | Movable panel position/rate/datum persist; sample records remain readable |

Sea calibration uses 701 actual ocean layers (56,781 height vertices) from three harbour tiles. All inspected water heights and layer min/max fields are zero. This verifies the **static regional reference**, not universal sea-level consistency across uninspected maps.

## Expansion gate

After the pilot passes, use WDT/Map metadata from the same Forever build to select Eastern Kingdoms and Kalimdor, then inspect Forever-specific map definitions. `terrain.py --bounds xmin ymin xmax ymax --wdt-id ID --map-id ID` can generate a selected map, but this pilot runtime supports **one map manifest at a time**. Multi-continent indexing and installation must be implemented and tested before combining datasets. No claim of complete world coverage is made. Do not reuse Classic/Era geometry: 27 of the 40 pilot tiles differ from installed Era.
