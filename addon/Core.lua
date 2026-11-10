local A = AltimeterForever
local frame = CreateFrame("Frame", "AltimeterForeverFrame", UIParent, "BackdropTemplate")
frame:SetPoint("CENTER", 0, 180)
frame:SetMovable(true)
frame:SetClampedToScreen(true)
frame:EnableMouse(true)
frame:RegisterForDrag("LeftButton")
local gauge = A.CreateGauge(frame)
local db, ticker, last
local survey, dragging
local function say(s) print("Altimeter: " .. s) end
local function safe(v) return A.Number(v) and v or nil end

-- Forever UI-map IDs; 1453 confirmed by the user's live harbour samples.
-- These are UI maps, not ADT area IDs. Follow parents for city interiors.
local cityMaps = {[1453]=true, [1454]=true, [1455]=true,
    [1456]=true, [1457]=true, [1458]=true}
function A.CityMap(id)
    local visited = {}
    for _ = 1, 12 do
        if not A.Number(id) or visited[id] then return nil end
        if cityMaps[id] then return id end
        visited[id] = true
        if not C_Map.GetMapInfo then return nil end
        local info = C_Map.GetMapInfo(id)
        id = info and info.parentMapID
    end
end

function A.Position()
    local r = {}
    if UnitPosition then
        local ok, n, w, z, m = pcall(UnitPosition, "player")
        if ok then r.north, r.west, r.z, r.map = safe(n), safe(w), safe(z), safe(m) end
    end
    -- Independent API observation, not an assumed hardcoded UI-map rectangle.
    local ok, id, n, w, m = pcall(function()
        local id = C_Map.GetBestMapForUnit("player")
        if not A.Number(id) then return end
        local p = C_Map.GetPlayerMapPosition(id, "player")
        if not p then return id end
        local map, world = C_Map.GetWorldPosFromMapPos(id, p)
        if not world then return id end
        local north, west = world:GetXY()
        return id, north, west, map
    end)
    if ok then
        r.uiMap, r.mapNorth, r.mapWest, r.mapWorld = safe(id), safe(n), safe(w), safe(m)
    end
    if r.north and r.west and r.map then
        r.source = "UnitPosition"
        if r.mapNorth and r.mapWest and r.mapWorld then
            r.delta = math.sqrt((r.north-r.mapNorth)^2 + (r.west-r.mapWest)^2)
            if r.map ~= r.mapWorld or r.delta > 2 then return r, "position APIs disagree" end
        end
    else
        -- Keep the map-only fallback explicitly estimated: map coordinates may be rounded.
        r.north, r.west, r.map = r.mapNorth, r.mapWest, r.mapWorld
        r.source = "map fallback (estimated)"
    end
    if not (r.north and r.west and r.map) then return r, "coordinates unavailable" end
    return r
end

local function update()
    local ok, err = pcall(function()
        local uiMap = C_Map.GetBestMapForUnit("player")
        local city = A.CityMap(uiMap)
        if city then
            last = {uiMap=safe(uiMap), city=city, reason="disabled in city"}
            gauge:SetUnavailable("Hidden in cities")
            frame:Hide()
            return
        end
        if db.hidden then frame:Hide() else frame:Show() end
        local r, reason = A.Position()
        last = r
        if r.map == 2980 or r.map == 2959 then
            r.reason="disabled in city"; gauge:SetUnavailable("Hidden in cities"); frame:Hide(); return
        end
        local _, build = GetBuildInfo()
        if tostring(build) ~= A.build then reason = "client build differs from terrain data" end
        if not reason and survey then reason = survey:Target(r) end
        if not reason then
            r.height, reason, r.tile, r.chunkX, r.chunkY, r.area, r.water, r.waterReason = A.Sample(r.north, r.west, r.map)
        end
        r.reason = reason
        if r.height then
            local map=A.maps and A.maps[r.map]
            local sea=map and map.seaLevel
            if sea==nil and A.reference and A.reference.buildKey==A.buildKey then sea=A.reference.z end
            local custom=db.customDatum or db.datum~=0
            local datum=custom and db.datum or (sea or 0)
            r.reference=datum
            if survey then survey:Render(r,datum) end
            -- Ocean presence is checked per terrain cell against its existence
            -- mask. Being below world zero alone never enables depth mode.
            r.depth=r.water and r.water>r.height and (r.water-r.height) or nil
            gauge:SetReading(r.depth or (r.height-datum),r.source~="UnitPosition",not custom and sea~=nil,r.depth~=nil,custom)
            if gauge.SetSurvey then gauge:SetSurvey(r.remote) end
        else
            if survey then survey:Render(r,0) end
            gauge:SetUnavailable(reason == "client build differs from terrain data" and "Data update needed" or "No terrain data")
        end
    end)
    if not ok then
        if survey then survey:Close() end
        last = {reason="API/terrain error", error=tostring(err)}
        gauge:SetUnavailable("Position unavailable")
    end
end

local visibilityCheck
local sizes = {Small=.70, Medium=.85, Large=1}
function A.SetSize(name)
    if not db or not sizes[name] then return end
    db.size = name
    frame:SetScale(sizes[name])
end
function A.SetVisible(visible)
    if not db then return end
    db.hidden = not visible
    if visibilityCheck then visibilityCheck:SetChecked(not db.hidden) end
    update()
end

local function registerSettings()
    local panel = CreateFrame("Frame")
    panel.name = "Altimeter"
    local heading = panel:CreateFontString(nil,"ARTWORK","GameFontNormalLarge")
    heading:SetPoint("TOPLEFT",16,-16)
    heading:SetText("Altimeter")
    visibilityCheck = CreateFrame("CheckButton",nil,panel,"InterfaceOptionsCheckButtonTemplate")
    visibilityCheck:SetPoint("TOPLEFT",16,-48)
    visibilityCheck.Text:SetText("Show altimeter")
    visibilityCheck:SetScript("OnClick",function(self) A.SetVisible(self:GetChecked()) end)
    local function label(text,y,font)
        local region=panel:CreateFontString(nil,"ARTWORK",font or "GameFontHighlightSmall")
        region:SetPoint("TOPLEFT",16,y)
        region:SetWidth(560)
        region:SetJustifyH("LEFT")
        region:SetText(text)
        return region
    end
    local function button(text,x,y,callback)
        local control=CreateFrame("Button",nil,panel,"UIPanelButtonTemplate")
        control:SetSize(170,24)
        control:SetPoint("TOPLEFT",x,y)
        control:SetText(text)
        control:SetScript("OnClick",callback)
        return control
    end
    label("Size",-90,"GameFontNormal")
    local sizeButtons={}
    local function refresh()
        visibilityCheck:SetChecked(not db.hidden)
        for name,control in pairs(sizeButtons) do
            control:SetText((db.size==name and "Selected: " or "")..name)
        end
    end
    for i,name in ipairs({"Small","Medium","Large"}) do
        local choice=name
        sizeButtons[choice]=button(choice,16+(i-1)*180,-112,function() A.SetSize(choice);refresh() end)
    end
    panel:SetScript("OnShow",refresh)
    button("Reset position",16,-150,function()
        frame:ClearAllPoints();frame:SetPoint("CENTER",0,180);db.position=nil
    end)
    button("Automatic reference",196,-150,function()
        db.datum=0;db.customDatum=false;update()
    end)
    label("Help",-196,"GameFontNormal")
    label("Click the gauge to sample ahead; drag to move. /alt toggles visibility. The sampling panel adds a temporary minimap grid and optional contours. The gauge hides in capital cities.",-220)
    label("On land, ALTIMETER shows natural ground elevation in metres. Over mapped ocean, DEPTH shows water surface to seabed distance, not your character's diving depth.",-275)
    label("Each dial number is 100 metres; a full turn is 1,000 metres. The numeric reading gives the full value. ~ means estimated position. Buildings and cave floors are excluded. Unsupported areas show no data.",-330)
    label("Advanced settings",-400,"GameFontNormal")
    local function entry(x,y)
        local edit=CreateFrame("EditBox",nil,panel,"InputBoxTemplate")
        edit:SetSize(100,24);edit:SetPoint("TOPLEFT",x,y);edit:SetAutoFocus(false)
        return edit
    end
    label("Update interval (0.1-5 seconds)",-426)
    local rate=entry(260,-420)
    rate:SetText(tostring(db.interval))
    button("Apply interval",380,-420,function()
        SlashCmdList.ALTIMETERFOREVER("rate "..rate:GetText());rate:ClearFocus()
    end)
    label("Custom reference (world Z, yards)",-460)
    local datum=entry(260,-454)
    datum:SetText(tostring(db.datum))
    button("Apply reference",380,-454,function()
        SlashCmdList.ALTIMETERFOREVER("datum "..datum:GetText());datum:ClearFocus()
    end)
    label("Automatic reference restores the map's reference. World reference means no sea level is established for that map. Custom reference changes the altitude zero point.",-494)
    panel:SetScript("OnShow",function()
        refresh();rate:SetText(tostring(db.interval));datum:SetText(tostring(db.datum))
    end)
    if Settings and Settings.RegisterCanvasLayoutCategory then
        local category = Settings.RegisterCanvasLayoutCategory(panel,panel.name)
        Settings.RegisterAddOnCategory(category)
    elseif InterfaceOptions_AddCategory then
        InterfaceOptions_AddCategory(panel)
    end
end

local function start()
    if ticker then ticker:Cancel() end
    ticker = C_Timer.NewTicker(db.interval, update)
    update()
end

frame:SetScript("OnMouseDown", function() dragging=false end)
frame:SetScript("OnMouseUp", function(_,button)
    if button=="LeftButton" and not dragging and survey then survey:Toggle() end
end)
frame:SetScript("OnDragStart", function(self) dragging=true;self:StartMoving() end)
frame:SetScript("OnDragStop", function(self)
    self:StopMovingOrSizing()
    if not db then return end
    local point, _, relative, x, y = self:GetPoint()
    db.position = {point, relative, x, y}
end)
frame:RegisterEvent("PLAYER_LOGIN")
frame:SetScript("OnEvent", function()
    AltimeterForeverDB = type(AltimeterForeverDB) == "table" and AltimeterForeverDB or {}
    db = AltimeterForeverDB
    db.interval = A.Number(db.interval) and math.max(.1, math.min(5, db.interval)) or .25
    db.datum = A.Number(db.datum) and db.datum or 0
    db.size = sizes[db.size] and db.size or "Medium"
    A.SetSize(db.size)
    db.samples = type(db.samples) == "table" and db.samples or {}
    if db.position and type(db.position[1]) == "string" and type(db.position[2]) == "string" and A.Number(db.position[3]) and A.Number(db.position[4]) then
        pcall(function() frame:ClearAllPoints(); frame:SetPoint(db.position[1], UIParent, db.position[2], db.position[3], db.position[4]) end)
    end
    registerSettings()
    if A.CreateSurvey and not survey then survey=A.CreateSurvey(frame,update) end
    start()
end)

SLASH_ALTIMETERFOREVER1 = "/altitude"
SLASH_ALTIMETERFOREVER2 = "/alt"
SlashCmdList.ALTIMETERFOREVER = function(msg)
    if not db then return end
    local command, value = msg:match("^(%S*)%s*(.-)$")
    command = command:lower()
    if command == "" or command == "toggle" then
        A.SetVisible(db.hidden)
    elseif command == "rate" then
        local n = tonumber(value)
        if not A.Number(n) or n < .1 or n > 5 then say("rate must be 0.1 to 5 seconds"); return end
        db.interval = n; start(); say("Update interval: " .. n .. " seconds")
    elseif command == "datum" then
        local n = value == "reset" and 0 or tonumber(value)
        if not A.Number(n) or math.abs(n) > 100000 then say("datum <known world Z> or datum reset; this sets a custom reference, not verified sea level"); return end
        db.datum = n; db.customDatum=value~="reset"; update(); say(value=="reset" and "Automatic map reference restored" or ("Custom reference world Z: " .. n .. " yards"))
    elseif command == "debug" or command == "sample" then
        update()
        local r = last or {}
        local function fmt(v) return A.Number(v) and string.format("%.4f", v) or "nil" end
        say("data " .. A.version .. "; source=" .. tostring(r.source) .. "; map=" .. fmt(r.map) .. "; UI=" .. fmt(r.uiMap))
        say("north=" .. fmt(r.north) .. " west=" .. fmt(r.west) .. " API Z=" .. fmt(r.z) .. "; API delta=" .. fmt(r.delta))
        say("tile=" .. tostring(r.tile) .. "; chunk=" .. fmt(r.chunkX) .. "," .. fmt(r.chunkY) .. "; ADT Z=" .. fmt(r.height))
        say("ocean surface=" .. fmt(r.water) .. "; seabed depth=" .. fmt(r.depth) .. " yd; reference=" .. fmt(r.reference))
        if r.reason then say(r.reason .. (r.error and (": " .. r.error) or "")) end
        if command == "sample" then
            local _, build = GetBuildInfo()
            local record = {}
            for k, v in pairs(r) do record[k] = v end
            record.note, record.build, record.time, record.datum = value:sub(1,120), tostring(build), time(), db.datum
            db.samples[#db.samples + 1] = record
            if #db.samples > 200 then table.remove(db.samples, 1) end
            say("Sample saved. /reload or logout flushes it to SavedVariables.")
        end
    elseif command == "show" then A.SetVisible(true)
    elseif command == "survey" and survey then survey:Toggle()
    elseif command == "hide" then A.SetVisible(false)
    elseif command == "reset" then
        frame:ClearAllPoints(); frame:SetPoint("CENTER", 0, 180); db.position = nil; A.SetVisible(true)
    else
        say("/altitude survey; rate <seconds>; debug; sample <note>; datum <world Z|reset>; show; hide; reset")
        say("Automatically hidden in capital cities; elsewhere reads terrain ground, never player Z or object floors.")
        say("Over mapped ocean: seabed depth, not diving depth. Sea references are per map; unsupported areas show no data.")
    end
end
