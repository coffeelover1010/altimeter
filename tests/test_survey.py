"""Survey geometry and full gauge/control lifecycle under Lua 5.1, not live UI QA."""
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'cf-ui-research/python-tools'))
from lupa.lua51 import LuaRuntime

UI = r'''
objects={}; SlashCmdList={}; now=0; facing=0; mapID=1; uiMap=1439
build='70862'; radius=100; rotating='0'; sampleCalls=0; missing=false
local methods={}
local function object(name,parent)
    local o=setmetatable({name=name,parent=parent,scripts={},children={},shown=true}, {__index=methods})
    objects[#objects+1]=o
    if name then _G[name]=o end
    if parent then parent.children[#parent.children+1]=o end
    return o
end
for _,name in ipairs({'SetSize','SetWidth','SetPoint','SetAllPoints','SetClampedToScreen',
    'EnableMouse','SetBackdrop','SetBackdropColor','SetBackdropBorderColor','SetJustifyH',
    'SetMinMaxValues','SetValueStep','SetObeyStepOnDrag','SetFrameLevel','SetThickness',
    'SetColorTexture','SetFont','SetTextColor','SetMovable','RegisterForDrag',
    'SetScale','RegisterEvent','SetAutoFocus','ClearFocus','ClearAllPoints',
    'StartMoving','StopMovingOrSizing'}) do methods[name]=function() end end
function methods:GetName() return self.name end
function methods:GetFrameLevel() return 1 end
function methods:GetWidth() return 200 end
function methods:GetHeight() return 200 end
function methods:GetZoom() return 3 end
function methods:GetPoint() return 'CENTER',UIParent,'CENTER',0,0 end
function methods:SetText(v) self.text=v end
function methods:GetText() return self.text end
function methods:SetChecked(v) self.checked=v end
function methods:GetChecked() return self.checked end
function methods:SetScript(k,v) self.scripts[k]=v end
function methods:SetValue(v) self.value=v; if self.scripts.OnValueChanged then self.scripts.OnValueChanged(self,v) end end
function methods:CreateFontString() return object(nil,self) end
function methods:CreateTexture() return object(nil,self) end
function methods:CreateLine() local o=object(nil,self);o.line=true;return o end
function methods:SetStartPoint(_,_,x,y) self.x1=x;self.y1=y end
function methods:SetEndPoint(_,_,x,y) self.x2=x;self.y2=y end
function methods:IsShown() return self.shown end
function methods:IsVisible() return self.shown and (not self.parent or self.parent:IsVisible()) end
local function hidden(o)
    if o.scripts.OnHide then o.scripts.OnHide(o) end
    for _,c in ipairs(o.children) do hidden(c) end
end
function methods:Hide() if self.shown then self.shown=false;hidden(self) end end
function methods:Show() self.shown=true end
function CreateFrame(kind,name,parent,template)
    local o=object(name,parent)
    if template=='OptionsSliderTemplate' then object(name..'Low',o);object(name..'High',o) end
    if template=='InterfaceOptionsCheckButtonTemplate' then
        o.Text=object(nil,o)
        if parent==AltimeterSurveyPanel then contourCheck=o end
    end
    if parent==Minimap then overlay=o end
    return o
end
UIParent=object();Minimap=object(nil,UIParent)
function GetPlayerFacing() return facing end
function GetBuildInfo() return '1.60.1',build end
function GetTime() return now end
function time() return 1 end
function GetCVar(k) if k=='rotateMinimap' then return rotating end return k=='minimapZoom' and '3' or '1' end
function UnitPosition() return 1000,2000,0,mapID end
C_Map={GetBestMapForUnit=function() return uiMap end}
C_Minimap={GetViewRadius=function() return radius end}
C_Timer={NewTicker=function(_,cb) tick=cb;return {Cancel=function()end} end}
function print() end
'''


class SurveyTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(UI)
        self.lua.execute((ROOT / 'height-module/Terrain.lua').read_text())
        self.lua.execute('''
            AltimeterForever.build='70862';AltimeterForever.version='test'
            AltimeterForever.maps={[1]={seaLevel=0}}
            AltimeterForever.Sample=function(n,w,map)
                sampleCalls=sampleCalls+1
                if missing then return nil,'terrain hole' end
                return n/10,nil,'test',0,0,1
            end
        ''')
        for name in ('Gauge.lua', 'Survey.lua', 'Core.lua'):
            self.lua.execute((ROOT / 'addon' / name).read_text())
        self.lua.execute('AltimeterForeverFrame.scripts.OnEvent()')
        self.g = self.lua.globals()
        self.s = self.g.AltimeterForever.SurveyMath

    def texts(self):
        return {o.text for o in self.g.objects.values() if isinstance(o.text, str)}

    def test_cardinal_targets_metres_and_rotation(self):
        for facing in (0, math.pi/2, math.pi, 3*math.pi/2):
            n, w = self.s.Target(0, 0, facing, 0, 91.44)
            self.assertAlmostEqual(math.hypot(n,w),100)
            x,y=self.s.Project(n,w,facing,1)
            self.assertAlmostEqual(x,0,places=9)
            self.assertAlmostEqual(y,100)
        n,w=self.s.Target(0,0,0,90,91.44)
        self.assertAlmostEqual(n,0,places=9)
        self.assertAlmostEqual(w,-100)

    def test_clipping_and_contour_intersections(self):
        self.assertEqual(self.s.Clip(-20,0,20,0,10),(-10,0,10,0))
        self.assertIsNone(self.s.Clip(20,20,30,30,10))
        self.assertIsNone(self.s.Clip(0,0,0,0,10))
        t=self.lua.table_from
        result=self.s.Contour(t([0,0,0]),t([10,0,20]),t([0,10,0]),10)
        self.assertEqual(result,(5,0,5,5))
        self.assertIsNone(self.s.Contour(t([0,0,0]),t([10,0]),t([0,10,0]),10))

    def test_open_turn_sliders_close_and_drag(self):
        self.assertIn('+91.4 m',self.texts())
        self.lua.execute("SlashCmdList.ALTIMETERFOREVER('survey')")
        self.assertTrue(self.g.overlay.shown)
        self.assertIn('REMOTE TERRAIN',self.texts())
        self.assertIn('+96.4 m',self.texts())  # 50 metres north on 1:10 slope
        self.lua.execute('AltimeterSurveydistance:SetValue(0)')
        self.assertIn('+91.4 m',self.texts())
        self.lua.execute('AltimeterSurveydistance:SetValue(50); AltimeterSurveydirection:SetValue(180)')
        self.assertIn('+86.4 m',self.texts())
        self.lua.execute("facing=math.pi; rotating='1'; tick()")
        self.assertIn('+96.4 m',self.texts())
        self.lua.execute("SlashCmdList.ALTIMETERFOREVER('survey')")
        self.assertFalse(self.g.overlay.shown)
        self.assertIn('+91.4 m',self.texts())
        self.lua.execute('''
            local f=AltimeterForeverFrame
            f.scripts.OnMouseDown(f,'LeftButton');f.scripts.OnDragStart(f)
            f.scripts.OnDragStop(f);f.scripts.OnMouseUp(f,'LeftButton')
        ''')
        self.assertFalse(self.g.AltimeterSurveyPanel.shown)
        self.lua.execute("local f=AltimeterForeverFrame;f.scripts.OnMouseDown(f,'LeftButton');f.scripts.OnMouseUp(f,'LeftButton')")
        self.assertTrue(self.g.AltimeterSurveyPanel.shown)

    def test_unavailable_build_city_and_hidden_cleanup(self):
        self.lua.execute("SlashCmdList.ALTIMETERFOREVER('survey');missing=true;tick()")
        self.assertFalse(self.g.overlay.shown)
        self.assertIn('-- m',self.texts())
        self.lua.execute('missing=false;tick()')
        self.assertTrue(self.g.overlay.shown)
        calls=self.g.sampleCalls
        self.lua.execute("build='different';tick()")
        self.assertEqual(self.g.sampleCalls,calls)
        self.assertFalse(self.g.overlay.shown)
        self.lua.execute("build='70862';tick();uiMap=1453;tick()")
        self.assertFalse(self.g.overlay.shown)
        self.lua.execute("uiMap=1439;tick();SlashCmdList.ALTIMETERFOREVER('hide')")
        self.assertFalse(self.g.overlay.shown)

    def test_contour_budget_cache_and_stroke_bounds(self):
        self.lua.execute("SlashCmdList.ALTIMETERFOREVER('survey');contourCheck:SetChecked(true);contourCheck.scripts.OnClick(contourCheck)")
        calls=self.g.sampleCalls
        self.lua.execute('now=.25;tick()')
        self.assertEqual(self.g.sampleCalls-calls,2)  # only origin + target, cached contours
        self.lua.execute('now=3;tick()')
        self.assertEqual(self.g.sampleCalls-calls,293)  # 289 mesh vertices, 4 point samples
        lines=[o for o in self.g.overlay.children.values() if o.line and o.shown]
        self.assertGreater(len(lines),10)
        self.assertLessEqual(len(lines),800)
        for o in lines:
            self.assertLessEqual(math.hypot(o.x1,o.y1),97.000001)
            self.assertLessEqual(math.hypot(o.x2,o.y2),97.000001)

    def test_off_map_point_and_missing_facing(self):
        self.lua.execute("SlashCmdList.ALTIMETERFOREVER('survey');AltimeterSurveydistance:SetValue(200)")
        self.assertTrue(any('Point beyond minimap' in t for t in self.texts()))
        self.lua.execute('facing=nil;tick()')
        self.assertFalse(self.g.overlay.shown)
        self.assertIn('Facing unavailable',self.texts())


if __name__ == '__main__':
    unittest.main(verbosity=2)
