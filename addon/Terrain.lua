AltimeterForever = {tiles = {}}
local A = AltimeterForever
local floor = math.floor
local alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
local digits = {}
for i = 1, #alphabet do digits[alphabet:byte(i)] = i - 1 end

function A.Number(v)
    return not (issecretvalue and issecretvalue(v)) and type(v) == "number"
        and v == v and v > -math.huge and v < math.huge
end

-- Each 24-bit milliyard offset occupies exactly four base64 characters.
local function vertex(chunk, i)
    local p = (i - 1) * 4 + 1
    local a, b, c, d = chunk[4]:byte(p, p + 3)
    a, b, c, d = digits[a], digits[b], digits[c], digits[d]
    if not (a and b and c and d) then return nil end
    return chunk[3] + (((a * 64 + b) * 64 + c) * 64 + d) / 1000
end

-- Four triangles meet at the centre of each cell. u=east, v=south.
function A.Interpolate(chunk, u, v)
    if not (A.Number(u) and A.Number(v)) or u < 0 or u >= 8 or v < 0 or v >= 8 then
        return nil, "outside chunk"
    end
    local col, row = floor(u), floor(v)
    if floor(chunk[5][row + 1] / 2^col) % 2 == 1 then return nil, "terrain hole" end
    u, v = u - col, v - row
    local i = row * 17 + col + 1
    local tl, tr, bl, br, mid = vertex(chunk, i), vertex(chunk, i + 1),
        vertex(chunk, i + 17), vertex(chunk, i + 18), vertex(chunk, i + 9)
    if not (tl and tr and bl and br and mid) then return nil, "corrupt terrain encoding" end
    if v <= u and v <= 1 - u then
        return tl * (1 - u - v) + tr * (u - v) + mid * (2 * v)
    elseif u >= v and u >= 1 - v then
        return tr * (u - v) + br * (u + v - 1) + mid * (2 - 2 * u)
    elseif v >= u and v >= 1 - u then
        return bl * (v - u) + br * (u + v - 1) + mid * (2 - 2 * v)
    end
    return tl * (1 - u - v) + bl * (v - u) + mid * (2 * u)
end

-- Index rectangles come from the extracted MCNK origins, not zone-map offsets.
-- Checking a small pilot index is cheap; no terrain decoding or per-frame work.
function A.Sample(north, west, mapID)
    if not (A.Number(north) and A.Number(west) and A.Number(mapID)) then return nil, "coordinates unavailable" end
    if not ((A.maps and A.maps[mapID]) or mapID == A.mapID) then return nil, "unsupported world map " .. mapID end
    local key, meta
    -- The extractor validates this lattice for every map/chunk. Neighbours
    -- account for stored float32 origins at tile edges; never scan the world.
    local tx,ty = floor(32-west/A.tileSize),floor(32-north/A.tileSize)
    for dy=-1,1 do
        for dx=-1,1 do
            local k=mapID .. ":" .. (tx+dx) .. ":" .. (ty+dy)
            local m=A.index[k]
            if m and north <= m[2] and north > m[2]-A.tileSize and west <= m[3] and west > m[3]-A.tileSize then
                key,meta=k,m
                break
            end
        end
        if key then break end
    end
    if not key then return nil, "outside extracted coverage" end
    if not A.tiles[key] then
        if InCombatLockdown and InCombatLockdown() then return nil, "tile load waits for combat to end" end
        local ok, reason = C_AddOns.LoadAddOn(meta[1])
        if not ok or not A.tiles[key] then return nil, "tile unavailable: " .. tostring(reason or meta[1]) end
    end
    local tile = A.tiles[key]
    local ix = math.min(15, floor((meta[3] - west) / A.chunkSize))
    local iy = math.min(15, floor((meta[2] - north) / A.chunkSize))
    local chunk = tile[iy * 16 + ix + 1]
    if not chunk then return nil, "missing chunk" end
    -- Evaluate the actual chunk mesh at its own stored float32 origin.
    local u = (chunk[2] - west) / A.step
    local v = (chunk[1] - north) / A.step
    -- Adjacent float32 origins can leave tiny gaps/overlaps. Only snap within
    -- the extractor's measured/validated 0.004-yard coordinate tolerance.
    local epsilon = .004 / A.step
    if u >= -epsilon and u <= 8 + epsilon then u = math.max(0, math.min(8 - 1e-10, u)) end
    if v >= -epsilon and v <= 8 + epsilon then v = math.max(0, math.min(8 - 1e-10, v)) end
    local z, reason = A.Interpolate(chunk, u, v)
    local water
    if z and chunk[7] then
        local col,row=floor(u),floor(v)
        for _,layer in ipairs(chunk[7]) do
            if layer[2][row+1] and floor(layer[2][row+1]/2^col)%2==1 then
                if water and math.abs(water-layer[1])>.00001 then
                    return z,reason,key,ix,iy,chunk[6],nil,"ambiguous ocean layers"
                end
                water=layer[1]
            end
        end
    end
    return z, reason, key, ix, iy, chunk[6], water
end
