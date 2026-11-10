"""Offline geometry and Lua 5.1 integration checks; never claims live testing."""
import base64
import json
import math
import random
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
# Optional workspace runtime. Else install lupa in the testing environment.
sys.path.insert(0, str(ROOT.parent / 'cf-ui-research' / 'python-tools'))
from lupa.lua51 import LuaRuntime
from terrain import parse_adt, parse_wdt, encode_heights, STEP, CHUNK, TILE
from calibrate import ocean_name, ocean_layers


def lua_setup():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute((ROOT / 'height-module/Terrain.lua').read_text())
    lua.execute((ROOT / 'build/AltimeterForever/Database.lua').read_text())
    return lua


def chunk_lua(lua, values, holes=None):
    base, text = encode_heights(values)
    return lua.table_from([0, 0, base, text, lua.table_from(holes or [0]*8), 12])


class TerrainTests(unittest.TestCase):
    def setUp(self):
        self.lua = lua_setup()
        self.a = self.lua.globals().AltimeterForever

    def test_center_vertex_not_bilinear(self):
        heights = [0.] * 145
        heights[9] = 100
        c = chunk_lua(self.lua, heights)
        self.assertEqual(self.a.Interpolate(c, .5, .5), 100)
        self.assertEqual(self.a.Interpolate(c, .5, .25), 50)
        self.assertEqual(self.a.Interpolate(c, .75, .5), 50)
        self.assertEqual(self.a.Interpolate(c, .5, .75), 50)
        self.assertEqual(self.a.Interpolate(c, .25, .5), 50)

    def test_plane_negative_heights_and_holes(self):
        heights = []
        for row in range(17):
            for col in range(8 if row % 2 else 9):
                x = col + (.5 if row % 2 else 0)
                heights.append(-50 + 2*x + 3*row/2)
        c = chunk_lua(self.lua, heights)
        for u, v in [(0,0),(.1,.3),(2.8,4.2),(7.999,7.999)]:
            self.assertAlmostEqual(self.a.Interpolate(c,u,v), -50+2*u+3*v, places=9)
        c[5][3] = 8
        self.assertEqual(self.a.Interpolate(c,3.2,2.2), (None,'terrain hole'))
        self.assertIsInstance(self.a.Interpolate(c,4.2,2.2), (int, float))
        self.assertEqual(self.a.Interpolate(c,8,0)[0], None)

    def test_real_geometry_triangle_centroids(self):
        manifest = json.loads((ROOT / 'build/manifest.json').read_text())
        rng = random.Random(70862)
        tested, max_error = 0, 0
        for tile in manifest['tiles']:
            path = ROOT / 'local-data' / manifest['buildKey'] / f'{tile["fileID"]}.bin'
            chunks, _ = parse_adt(path.read_bytes(), tile['x'], tile['y'])
            addon = f'AltimeterForever_T0_{tile["x"]}_{tile["y"]}'
            self.lua.execute((ROOT / 'build' / addon / 'Data.lua').read_text())
            key = f'0:{tile["x"]}:{tile["y"]}'
            for (ix, iy), chunk in chunks.items():
                # Test all four triangle centroids in one cell per actual chunk.
                col, row = rng.randrange(8), rng.randrange(8)
                i = row*17+col
                h = chunk['heights']
                triangles = [((.5,1/6),(i,i+1,i+9)), ((5/6,.5),(i+1,i+18,i+9)),
                             ((.5,5/6),(i+17,i+18,i+9)), ((1/6,.5),(i,i+17,i+9))]
                for (u,v), vertices in triangles:
                    got = self.a.Interpolate(self.a.tiles[key][iy*16+ix+1], col+u,row+v)
                    if chunk['holes'][row] & (1<<col):
                        self.assertEqual(got, (None,'terrain hole'))
                    else:
                        expected = sum(h[i] for i in vertices)/3
                        error = abs(got-expected)
                        self.assertLessEqual(error,.000501)
                        max_error = max(max_error,error)
                        # World lookup must agree with the actual MCNK vertex
                        # coordinates, not merely a duplicated tile formula.
                        sampled = self.a.Sample(chunk['north']-(row+v)*STEP,
                                                chunk['west']-(col+u)*STEP,0)
                        self.assertIsNotNone(sampled[0], sampled)
                        self.assertLessEqual(abs(sampled[0]-expected), .000501)
                    tested += 1
        print(f'Actual ADT: {tested} triangle/hole checks; max height error {max_error:.9f} yd')

    def test_corrupt_and_incompatible_input(self):
        m = json.loads((ROOT / 'build/manifest.json').read_text())
        data = (ROOT/'local-data'/m['buildKey']/f'{m["tiles"][0]["fileID"]}.bin').read_bytes()
        with self.assertRaises(ValueError): parse_adt(data[:-1],28,47)
        with self.assertRaises(ValueError): parse_adt(data,29,47)
        with self.assertRaises(ValueError): parse_wdt(b'bad')
        mutated = bytearray(data)
        mcvt = mutated.find(b'TVCM')
        struct.pack_into('<f',mutated,mcvt+8,math.nan)
        with self.assertRaises(ValueError): parse_adt(mutated,28,47)
        mutated = bytearray(data)
        struct.pack_into('<I',mutated,8,19)
        with self.assertRaises(ValueError): parse_adt(mutated,28,47)

    def test_local_ocean_calibration_and_rejection(self):
        data=(ROOT/'research/1371380.db2').read_bytes()
        self.assertEqual(ocean_name(data),'PBRWater - Generic - Ocean')
        damaged=bytearray(data);struct.pack_into('<I',damaged,156,0)
        with self.assertRaises(ValueError):ocean_name(damaged)
        m=json.loads((ROOT/'build/manifest.json').read_text())
        adt=(ROOT/'local-data'/m['buildKey']/'777222.bin').read_bytes()
        self.assertEqual(ocean_layers(adt),256)
        damaged=bytearray(adt)
        start=damaged.index(b'O2HM')+8
        layer=struct.unpack_from('<I',damaged,start)[0]
        vertices=struct.unpack_from('<I',damaged,start+layer+20)[0]
        struct.pack_into('<f',damaged,start+vertices,1.)
        with self.assertRaises(ValueError):ocean_layers(damaged)

    def test_tile_loading_boundaries_and_unknown(self):
        self.lua.execute('C_AddOns={}; InCombatLockdown=function() return false end')
        def load(name):
            self.lua.execute((ROOT/'build'/name/'Data.lua').read_text())
            return True
        self.lua.globals().C_AddOns.LoadAddOn = load
        self.assertEqual(self.a.Sample(-9000,500,999)[0],None)
        self.assertEqual(self.a.Sample(10000,10000,0)[0],None)
        self.lua.execute('InCombatLockdown=function() return true end')
        self.assertIn('combat',self.a.Sample(-9000,500,0)[1])
        self.lua.execute('InCombatLockdown=function() return false end')
        for key, meta in self.a.index.items():
            for dn,dw in [(0,0),(.01,.01),(TILE-.01,TILE-.01),(CHUNK-.01,CHUNK-.01),(CHUNK+.01,CHUNK+.01)]:
                result = self.a.Sample(meta[2]-dn,meta[3]-dw,0)
                self.assertTrue(result[0] is not None or result[1]=='terrain hole',result)

    def test_runtime_diagnostics_build_and_restrictions(self):
        self.lua.execute('''
          UIParent={}; SlashCmdList={}; messages={}; build="70862"; sampleZ=0
          local methods={}
          function methods:SetScript(k,v) self[k]=v end
          function methods:SetText(v) self.text=v end
          function methods:Show() self.hidden=false end
          function methods:Hide() self.hidden=true end
          function methods:CreateFontString() local f=setmetatable({},{__index=methods}); return f end
          function methods:CreateLine() return setmetatable({},{__index=methods}) end
          function methods:CreateTexture() return setmetatable({},{__index=methods}) end
          setmetatable(methods,{__index=function() return function() end end})
          function CreateFrame(kind,name,parent,template)
            local f=setmetatable({},{__index=methods})
            if name=='AltimeterForeverFrame' then testFrame=f end
            if template=='InterfaceOptionsCheckButtonTemplate' then
                f.Text=setmetatable({},{__index=methods})
            end
            return f
          end
          function GetBuildInfo() return "1.60.1",build end
          function print(s) table.insert(messages,s) end
          function time() return 123 end
          function InCombatLockdown() return false end
          function UnitPosition() return -9450,50,sampleZ,0 end
          C_Map={GetBestMapForUnit=function()return 37 end,
            GetPlayerMapPosition=function()return {} end,
            GetWorldPosFromMapPos=function()return 0,{GetXY=function()return -9450,50 end}end}
          C_Timer={NewTicker=function(_,fn) update=fn;return {Cancel=function()end}end}
          C_AddOns={}
        ''')
        def load(name):
            self.lua.execute((ROOT/'build'/name/'Data.lua').read_text())
            return True
        self.lua.globals().C_AddOns.LoadAddOn = load
        self.lua.execute((ROOT/'addon/Gauge.lua').read_text())
        self.lua.execute((ROOT/'addon/Core.lua').read_text())
        self.lua.execute('testFrame.OnEvent(); SlashCmdList.ALTIMETERFOREVER("sample ground")')
        db = self.lua.globals().AltimeterForeverDB
        ground = db.samples[1].height
        self.assertIsNotNone(ground)
        self.lua.execute('sampleZ=999; SlashCmdList.ALTIMETERFOREVER("sample jumping")')
        self.assertEqual(db.samples[2].height,ground)
        self.assertEqual(db.samples[2].z,999)
        self.lua.execute('C_Map.GetBestMapForUnit=function()return 1453 end; SlashCmdList.ALTIMETERFOREVER("sample city")')
        self.assertIsNone(db.samples[3].height)
        self.assertEqual(db.samples[3].reason,'disabled in city')
        self.assertTrue(self.lua.globals().testFrame.hidden)
        self.lua.execute('SlashCmdList.ALTIMETERFOREVER("show")')
        self.assertTrue(self.lua.globals().testFrame.hidden)
        self.lua.execute('C_Map.GetMapInfo=function(id) return {parentMapID=1453} end')
        self.assertEqual(self.a.CityMap(9999),1453)
        self.lua.execute('C_Map.GetMapInfo=nil; C_Map.GetBestMapForUnit=function()return 37 end; update()')
        self.assertFalse(self.lua.globals().testFrame.hidden)
        self.lua.execute('SlashCmdList.ALTIMETERFOREVER("hide"); update()')
        self.assertTrue(self.lua.globals().testFrame.hidden)
        self.lua.execute('SlashCmdList.ALTIMETERFOREVER("show"); table.remove(AltimeterForeverDB.samples,3)')
        self.lua.execute('build="99999"; SlashCmdList.ALTIMETERFOREVER("sample mismatch")')
        self.assertIsNone(db.samples[3].height)
        self.assertIn('build',db.samples[3].reason)
        self.lua.execute('build="70862"; UnitPosition=function() error("restricted") end; SlashCmdList.ALTIMETERFOREVER("sample fallback")')
        self.assertIn('estimated',db.samples[4].source)
        self.lua.execute('C_Map.GetBestMapForUnit=function() error("restricted") end; SlashCmdList.ALTIMETERFOREVER("sample unavailable")')
        self.assertIsNone(db.samples[5].height)
        self.lua.execute('SlashCmdList.ALTIMETERFOREVER("rate 0"); SlashCmdList.ALTIMETERFOREVER("datum nan")')
        self.assertEqual(db.interval,.25)
        self.assertEqual(db.datum,0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
