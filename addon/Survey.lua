local A = AltimeterForever
local S = {}
A.SurveyMath = S
local M = .9144
local sin, cos, sqrt, floor = math.sin, math.cos, math.sqrt, math.floor

-- World axes: north/west. Facing is counterclockwise; positive slider = right.
function S.Target(n,w,facing,degrees,metres)
    local angle=facing-degrees*math.pi/180
    return n+cos(angle)*metres/M,w+sin(angle)*metres/M
end
function S.Project(dn,dw,rotation,scale)
    local x,y=-dw,dn
    return (x*cos(rotation)+y*sin(rotation))*scale,(-x*sin(rotation)+y*cos(rotation))*scale
end
-- Clip strokes to an inscribed circle, including on custom minimap shapes.
function S.Clip(x1,y1,x2,y2,r)
    local dx,dy=x2-x1,y2-y1
    local a=dx*dx+dy*dy
    if a<1e-12 then return end
    local b=2*(x1*dx+y1*dy)
    local c=x1*x1+y1*y1-r*r
    local disc=b*b-4*a*c
    if disc<0 then return end
    local lo=math.max(0,(-b-sqrt(disc))/(2*a))
    local hi=math.min(1,(-b+sqrt(disc))/(2*a))
    if hi<=lo then return end
    return x1+lo*dx,y1+lo*dy,x1+hi*dx,y1+hi*dy
end
-- Linear intersections on triangles avoid ambiguous saddle cells.
-- Vertices contain north, west and elevation in metres.
function S.Contour(a,b,c,level)
    if not (a[3] and b[3] and c[3]) then return end
    local hits={}
    for _,edge in ipairs({{a,b},{b,c},{c,a}}) do
        local p,q=edge[1],edge[2]
        if (p[3]<level and q[3]>=level) or (q[3]<level and p[3]>=level) then
            local t=(level-p[3])/(q[3]-p[3])
            hits[#hits+1]={p[1]+t*(q[1]-p[1]),p[2]+t*(q[2]-p[2])}
        end
    end
    if #hits==2 then return hits[1][1],hits[1][2],hits[2][1],hits[2][2] end
end
local outdoor={ [0]=466+2/3,400,333+1/3,266+2/3,200,133+1/3 }
local indoor={ [0]=300,240,180,120,80,50 }
function S.ViewRadius()
    if C_Minimap and C_Minimap.GetViewRadius then
        local ok,r=pcall(C_Minimap.GetViewRadius)
        if ok and A.Number(r) and r>0 then return r end
    end
    local pins=LibStub and LibStub("HereBeDragons-Pins-2.0",true)
    if pins and pins.GetMinimapView then
        local r=pins:GetMinimapView()
        if A.Number(r) and r>0 then return r end
    end
    local zoom=Minimap:GetZoom()
    local outside,inside=tonumber(GetCVar("minimapZoom")),tonumber(GetCVar("minimapInsideZoom"))
    -- Equal CVars are ambiguous. Never invent a scale or change user zoom.
    if outside==inside then return nil end
    local diameter=(zoom==outside and outdoor or indoor)[zoom]
    return diameter and diameter/2
end

function A.CreateSurvey(owner,refresh)
    local survey={direction=0,distance=50,lines={},contours={}}
    local panel=CreateFrame("Frame","AltimeterSurveyPanel",owner,"BackdropTemplate")
    panel:SetSize(280,278);panel:SetPoint("TOPLEFT",owner,"TOPRIGHT",8,0)
    panel:SetClampedToScreen(true);panel:EnableMouse(true)
    panel:SetBackdrop({bgFile="Interface\\Buttons\\WHITE8X8",edgeFile="Interface\\Tooltips\\UI-Tooltip-Border",
        edgeSize=16,insets={left=4,right=4,top=4,bottom=4}})
    panel:SetBackdropColor(.025,.03,.035,.97);panel:Hide()
    local overlay=CreateFrame("Frame",nil,Minimap)
    overlay:SetAllPoints(Minimap);overlay:SetFrameLevel(Minimap:GetFrameLevel()+5)
    overlay:EnableMouse(false);overlay:Hide()
    survey.panel=panel
    local function label(text,y)
        local f=panel:CreateFontString(nil,"OVERLAY","GameFontHighlightSmall")
        f:SetPoint("TOPLEFT",14,y);f:SetWidth(252);f:SetJustifyH("LEFT");f:SetText(text)
        return f
    end
    label("Sample terrain ahead",-15)
    local close=CreateFrame("Button",nil,panel,"UIPanelCloseButton")
    close:SetPoint("TOPRIGHT",0,0)
    close:SetScript("OnClick",function() survey:Close();refresh() end)
    local function slider(key,title,y,low,high)
        local caption=label("",y)
        local control=CreateFrame("Slider","AltimeterSurvey"..key,panel,"OptionsSliderTemplate")
        control:SetPoint("TOPLEFT",20,y-22);control:SetSize(238,16)
        control:SetMinMaxValues(low,high);control:SetValueStep(1);control:SetObeyStepOnDrag(true)
        _G[control:GetName().."Low"]:SetText(tostring(low))
        _G[control:GetName().."High"]:SetText(tostring(high))
        local function changed(_,value)
            survey[key]=floor(value+.5)
            caption:SetText(title..": "..survey[key]..(key=="distance" and " m" or " degrees (0 = ahead)"))
            if panel:IsShown() then refresh() end
        end
        control:SetScript("OnValueChanged",changed)
        control:SetValue(survey[key]);changed(control,survey[key])
    end
    slider("direction","Direction",-44,-180,180)
    slider("distance","Distance",-105,0,200)
    local check=CreateFrame("CheckButton",nil,panel,"InterfaceOptionsCheckButtonTemplate")
    check:SetPoint("TOPLEFT",10,-165);check.Text:SetText("Terrain contours (10 m elevation)")
    check:SetScript("OnClick",function(self)
        survey.showContours=self:GetChecked();survey.cache=nil;refresh()
    end)
    local reading=label("",-198)
    local legend=label("",-235)
    panel:SetScript("OnHide",function() overlay:Hide();survey.cache=nil end)
    function survey:IsOpen() return panel:IsShown() and owner:IsShown() end
    function survey:Close() panel:Hide();overlay:Hide();self.cache=nil end
    function survey:Toggle()
        if panel:IsShown() then self:Close() else panel:Show() end
        refresh()
    end
    function survey:Target(r)
        if not self:IsOpen() then return end
        local ok,facing=pcall(function() return GetPlayerFacing and GetPlayerFacing() end)
        if not ok or not A.Number(facing) then return "Facing unavailable" end
        r.playerNorth,r.playerWest=r.north,r.west
        r.playerHeight=A.Sample(r.north,r.west,r.map)
        r.north,r.west=S.Target(r.north,r.west,facing,self.direction,self.distance)
        r.surveyFacing=facing;r.remote=true
    end
    function survey:Stroke(x1,y1,x2,y2,width,red,green,blue,alpha)
        x1,y1,x2,y2=S.Clip(x1,y1,x2,y2,self.clipRadius)
        if not x1 or self.used>=800 then return end
        self.used=self.used+1
        local l=self.lines[self.used]
        if not l then l=overlay:CreateLine(nil,"OVERLAY");self.lines[self.used]=l end
        l:SetStartPoint("CENTER",overlay,x1,y1);l:SetEndPoint("CENTER",overlay,x2,y2)
        l:SetThickness(width);l:SetColorTexture(red,green,blue,alpha);l:Show()
    end
    function survey:BuildContours(r,radius,datum)
        local now=GetTime()
        local cache=self.cache
        if cache and cache.map==r.map and cache.datum==datum and cache.radius==radius
            and now-cache.time<2 and math.abs(cache.n-r.playerNorth)<radius/4
            and math.abs(cache.w-r.playerWest)<radius/4 then return end
        self.contours={}
        self.cache={map=r.map,datum=datum,radius=radius,time=now,n=r.playerNorth,w=r.playerWest}
        local step=radius/8
        local rows={}
        for i=0,16 do
            rows[i]={}
            for j=0,16 do
                local n,w=r.playerNorth-radius+i*step,r.playerWest-radius+j*step
                local z=A.Sample(n,w,r.map)
                rows[i][j]={n,w,z and (z-datum)*M}
            end
        end
        local function triangle(a,b,c)
            if not (a[3] and b[3] and c[3]) then return end
            local lo,hi=math.min(a[3],b[3],c[3]),math.max(a[3],b[3],c[3])
            for level=math.ceil(lo/10)*10,hi,10 do
                if #self.contours>=600 then return end
                local n1,w1,n2,w2=S.Contour(a,b,c,level)
                if n1 then self.contours[#self.contours+1]={n1,w1,n2,w2,level} end
            end
        end
        for i=0,15 do for j=0,15 do
            local a,b,c,d=rows[i][j],rows[i+1][j],rows[i+1][j+1],rows[i][j+1]
            triangle(a,b,c);triangle(a,c,d)
        end end
    end
    function survey:Render(r,datum)
        overlay:Hide()
        if not self:IsOpen() then return end
        for _,l in ipairs(self.lines) do l:Hide() end
        self.used=0
        if not r.remote or r.reason or not r.height then
            reading:SetText(r.reason or "Position unavailable");legend:SetText("");return
        end
        local delta=r.playerHeight and string.format("Height difference: %+.1f m",(r.height-r.playerHeight)*M) or "Local terrain unavailable"
        reading:SetText(string.format("%d m away | %+.0f degrees\n%s",self.distance,self.direction,delta))
        local radius=S.ViewRadius()
        if not radius then legend:SetText("Minimap scale unavailable; try another zoom.");return end
        local pixels=math.min(Minimap:GetWidth(),Minimap:GetHeight())/2
        if pixels<=0 then return end
        self.clipRadius=pixels-3
        local scale=pixels/radius
        local rotation=GetCVar("rotateMinimap")=="1" and r.surveyFacing or 0
        local function project(n,w) return S.Project(n-r.playerNorth,w-r.playerWest,rotation,scale) end
        local interval=10
        if interval/M*scale<7 then interval=50 end
        local step=interval/M
        for k=math.ceil((r.playerNorth-radius)/step),floor((r.playerNorth+radius)/step) do
            local n=k*step
            local x1,y1=project(n,r.playerWest-radius*2)
            local x2,y2=project(n,r.playerWest+radius*2)
            self:Stroke(x1,y1,x2,y2,1,.7,.8,.85,(k*interval)%50==0 and .40 or .16)
        end
        for k=math.ceil((r.playerWest-radius)/step),floor((r.playerWest+radius)/step) do
            local w=k*step
            local x1,y1=project(r.playerNorth-radius*2,w)
            local x2,y2=project(r.playerNorth+radius*2,w)
            self:Stroke(x1,y1,x2,y2,1,.7,.8,.85,(k*interval)%50==0 and .40 or .16)
        end
        if self.showContours then
            self:BuildContours(r,radius,datum)
            for _,c in ipairs(self.contours) do
                local x1,y1=project(c[1],c[2]);local x2,y2=project(c[3],c[4])
                self:Stroke(x1,y1,x2,y2,1,.95,.72,.30,c[5]%50==0 and .8 or .45)
            end
        end
        local x,y=project(r.north,r.west)
        self:Stroke(0,0,x,y,1,.3,1,1,.8)
        local outside=x*x+y*y>(self.clipRadius-5)^2
        if not outside then
            self:Stroke(x-4,y,x+4,y,2,.3,1,1,1)
            self:Stroke(x,y-4,x,y+4,2,.3,1,1,1)
        end
        legend:SetText(string.format("Grid: %d m | %s",interval,outside and "Point beyond minimap" or "Cyan cross: sample")..
            (self.showContours and "\nGold: approximate 10 m contours" or ""))
        overlay:Show()
    end
    return survey
end
