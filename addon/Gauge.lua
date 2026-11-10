local A = AltimeterForever

-- Native UI geometry: no image files or work performed every animation frame.
function A.CreateGauge(frame)
    frame:SetSize(220, 284)
    frame:SetScale(.85)
    frame:SetBackdrop({bgFile="Interface\\Buttons\\WHITE8X8", edgeFile="Interface\\Tooltips\\UI-Tooltip-Border",
        edgeSize=16, insets={left=4,right=4,top=4,bottom=4}})
    frame:SetBackdropColor(.025, .03, .035, .96)
    frame:SetBackdropBorderColor(.38, .40, .42, 1)
    local function text(size, x, y, r, g, b)
        local f = frame:CreateFontString(nil, "OVERLAY")
        f:SetFont(STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF", size)
        f:SetPoint("CENTER", frame, "CENTER", x, y)
        f:SetTextColor(r or .9, g or .91, b or .87)
        return f
    end
    local function line(x1, y1, x2, y2, width, r, g, b, layer)
        local l = frame:CreateLine(nil, layer or "ARTWORK")
        l:SetThickness(width)
        l:SetColorTexture(r, g, b, 1)
        l:SetStartPoint("CENTER", frame, x1, y1)
        l:SetEndPoint("CENTER", frame, x2, y2)
        return l
    end
    local cy = 15
    for _, ring in ipairs({{85,3,.24,.26,.28},{81,1,.55,.57,.55}}) do
        for i=0,63 do
            local a, b = i*math.pi/32, (i+1)*math.pi/32
            line(math.sin(a)*ring[1],cy+math.cos(a)*ring[1],math.sin(b)*ring[1],cy+math.cos(b)*ring[1],
                ring[2],ring[3],ring[4],ring[5])
        end
    end
    for i=0,49 do
        local angle = i*math.pi/25
        local major = i%5 == 0
        local inside = major and 65 or 71
        line(math.sin(angle)*inside,cy+math.cos(angle)*inside,math.sin(angle)*77,cy+math.cos(angle)*77,
            major and 2 or 1,.85,.87,.81)
        if major then
            text(15,math.sin(angle)*53,cy+math.cos(angle)*53):SetText(tostring(i/5))
        end
    end
    local title=text(11,0,118)
    local surface=text(9,0,-9,.58,.63,.60)
    text(9,0,-82,.58,.63,.60):SetText("METRES x 100")
    line(-73,-94,73,-94,1,.25,.28,.29)
    local needle = line(0,cy,0,cy+63,3,.96,.94,.77,"OVERLAY")
    local tail = line(0,cy,0,cy-12,3,.96,.94,.77,"OVERLAY")
    local hub = frame:CreateTexture(nil,"OVERLAY")
    hub:SetColorTexture(.65,.68,.64,1)
    hub:SetSize(7,7)
    hub:SetPoint("CENTER",frame,"CENTER",0,cy)
    local value = text(21,0,-111,.79,.94,.78)
    local caption = text(10,0,-131,.66,.71,.67)
    local hint = text(10,0,-131,.66,.71,.67)
    hint:SetText("Click to sample ahead; drag to move")
    hint:Hide()
    local close = CreateFrame("Button",nil,frame)
    close:SetSize(20,20)
    close:SetPoint("TOPRIGHT",frame,"TOPRIGHT",-4,-4)
    local cross = {}
    for i, direction in ipairs({1,-1}) do
        local stroke = close:CreateLine(nil,"OVERLAY")
        stroke:SetThickness(1.5)
        stroke:SetStartPoint("CENTER",close,-4,4*direction)
        stroke:SetEndPoint("CENTER",close,4,-4*direction)
        cross[i] = stroke
    end
    local function crossColor(r,g,b)
        for _, stroke in ipairs(cross) do stroke:SetColorTexture(r,g,b,1) end
    end
    crossColor(.66,.71,.67)
    close:SetScript("OnClick",function() if A.SetVisible then A.SetVisible(false) end end)
    local function hover(active)
        if active then hint:Show();caption:Hide() else hint:Hide();caption:Show() end
    end
    frame:SetScript("OnEnter",function() hover(true) end)
    frame:SetScript("OnLeave",function() hover(false) end)
    frame:SetScript("OnHide",function() hover(false) end)
    close:SetScript("OnEnter",function() hover(true);crossColor(.96,.94,.77) end)
    close:SetScript("OnLeave",function() hover(false);crossColor(.66,.71,.67) end)
    local gauge = {}
    function gauge:SetSurvey(active)
        if active then surface:SetText("REMOTE TERRAIN") end
    end
    function gauge:SetReading(height, estimated, seaReference, depthMode, customReference)
        height = height * .9144 -- WoW yards to metres; source/calibration stay in yards.
        title:SetText(depthMode and "DEPTH" or "ALTIMETER")
        surface:SetText(depthMode and "SEABED" or "GROUND")
        local angle = (height%1000)*2*math.pi/1000
        local x,y = math.sin(angle),math.cos(angle)
        needle:SetEndPoint("CENTER",frame,x*63,cy+y*63)
        tail:SetEndPoint("CENTER",frame,-x*12,cy-y*12)
        needle:Show(); tail:Show()
        value:SetText((estimated and "~ " or "") .. string.format(depthMode and "%.1f m" or "%+.1f m",height))
        if depthMode then value:SetTextColor(.55,.83,1) else value:SetTextColor(.79,.94,.78) end
        caption:SetText(depthMode and "Sea floor depth" or (seaReference and "" or (customReference and "Custom reference" or "World reference")))
    end
    function gauge:SetUnavailable(message)
        needle:Hide(); tail:Hide()
        title:SetText("ALTIMETER"); surface:SetText("GROUND")
        value:SetText("-- m")
        value:SetTextColor(.65,.67,.65)
        caption:SetText(message or "No terrain data")
    end
    gauge:SetUnavailable("Waiting for position")
    return gauge
end
