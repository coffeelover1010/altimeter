# Altimeter Height Data

Independent, UI-free terrain sampling module for WoW addons. It does not
require the Altimeter gauge. Install AltimeterHeightData and the included
AltimeterForever_W* load-on-demand packs. Add `## Dependencies: AltimeterHeightData`
to your addon's TOC. Do not rename the generated packs: the index references them.

```lua
local heights = AltimeterHeightData
local _, build = GetBuildInfo()
if tostring(build) == heights.build then
    local north, west, _, mapID = UnitPosition("player")
    local z, reason, tile, chunkX, chunkY, areaID, waterZ, waterReason =
        heights.Sample(north, west, mapID)
    -- z and waterZ are world coordinates in yards; multiply distances by .9144 for metres.
end
```

`Sample` returns nil and a reason for unavailable terrain; do not substitute zero.
Check the client build before sampling. Calls may load a terrain pack; new packs
are deferred in combat. Loaded packs persist until reload. The API samples terrain,
not player height, object floors or character diving depth. Ocean water is optional.
`maps[mapID].seaLevel` is optional; absent means no established sea reference.
`apiVersion` is 1. The old AltimeterForever global is a compatibility alias used
by the current generated packs. Consumers should use AltimeterHeightData.

See LICENSE for the limited permission to reuse this module in other WoW addons.
