"""Expanded database, depth switching, and unit conversion regression checks."""
import hashlib
import json
import random
import struct
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT.parent/'cf-ui-research/python-tools'))
from lupa.lua51 import LuaRuntime
from terrain import parse_adt,STEP
from world_maps import decode_maps
from build_world import ocean_cells,verify_liquid_formats


class WorldTests(unittest.TestCase):
    def test_ocean_layout_and_cell_masks(self):
        types=(ROOT/'research/1371380.db2').read_bytes()
        materials=(ROOT/'research/LiquidMaterial.db2').read_bytes()
        self.assertEqual(verify_liquid_formats(types,materials),{2:2,1250:0,1296:0})
        broken=bytearray(materials);struct.pack_into('<I',broken,156,0)
        with self.assertRaises(ValueError):verify_liquid_formats(types,broken)
        p=bytearray(3072)
        struct.pack_into('<III',p,0,3072,1,0)
        p.extend(struct.pack('<HHff4BII',2,42,0.,0.,0,0,8,8,3096,0))
        p.extend((1<<11).to_bytes(8,'little'))
        data=b'O2HM'+struct.pack('<I',len(p))+p
        water,errors=ocean_cells(data,2)
        self.assertEqual(water,{1:[(0.,[0,8,0,0,0,0,0,0])]})
        self.assertFalse(errors)
        self.assertEqual(ocean_cells(data,1250)[0],{}) # no lake/ocean-type substitution

    def test_map_discovery_boundaries(self):
        b=(ROOT/'research/Map-readable-prefix.db2').read_bytes()
        maps,unread=decode_maps(b)
        self.assertEqual(len(maps),73)
        self.assertEqual(sum(s['records'] for s in unread),8)
        self.assertEqual(next(m for m in maps if m['id']==1)['wdt'],782779)
        with self.assertRaises((ValueError,struct.error)):decode_maps(b[:300])

    def test_every_generated_tile_against_local_geometry(self):
        manifest=json.loads((ROOT/'build-world/manifest.json').read_text())
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.execute((ROOT/'addon/Terrain.lua').read_text())
        lua.execute((ROOT/'build-world/AltimeterForever/Database.lua').read_text())
        a=lua.globals().AltimeterForever
        rng=random.Random(70862);wet=0;maxerror=0
        maps={m['id']:m for m in manifest['maps']}
        for i,t in enumerate(manifest['tiles']):
            raw=(ROOT/'local-data'/manifest['buildKey']/f'{t["fileID"]}.bin').read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),t['sha256'])
            chunks,_=parse_adt(raw,t['x'],t['y'])
            water,_=ocean_cells(raw,maps[t['mapID']]['oceanType'])
            key=f'{t["mapID"]}:{t["x"]}:{t["y"]}'
            pack=f'AltimeterForever_W{t["mapID"]}_{t["x"]//4}_{t["y"]//4}'
            lua.execute((ROOT/'build-world'/pack/f'T{t["x"]}_{t["y"]}.lua').read_text())
            # A randomly selected actual chunk in EVERY world tile, with all
            # four centre-fan triangles and a separately indexed water mask.
            ix,iy=rng.randrange(16),rng.randrange(16);c=chunks[ix,iy]
            col,row=rng.randrange(8),rng.randrange(8);vtx=row*17+col
            for (u,v),ids in [((.5,1/6),(vtx,vtx+1,vtx+9)),((5/6,.5),(vtx+1,vtx+18,vtx+9)),((.5,5/6),(vtx+17,vtx+18,vtx+9)),((1/6,.5),(vtx,vtx+17,vtx+9))]:
                result=a.Sample(c['north']-(row+v)*STEP,c['west']-(col+u)*STEP,t['mapID'])
                if c['holes'][row]&(1<<col):self.assertIsNone(result[0]);continue
                self.assertIsNotNone(result[0],(key,result))
                expected=sum(c['heights'][j] for j in ids)/3
                error=abs(result[0]-expected);maxerror=max(maxerror,error)
                self.assertLess(error,.000501)
                levels={z for z,mask in water.get(iy*16+ix+1,[]) if mask[row]&(1<<col)}
                if len(levels)==1:
                    self.assertEqual(result[6],next(iter(levels)));wet+=1
                else:self.assertIsNone(result[6])
            # Independent tiles for bounded test memory, not runtime eviction.
            a.tiles[key]=None
            if i%100==0:lua.execute('collectgarbage("collect")')
        print(f'{len(manifest["tiles"])} source hashes and world lookups passed; {wet} water samples; max error {maxerror:.9f} yd')

    def test_depth_display_and_no_stale_needle(self):
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.execute('''
          AltimeterForever={}; UIParent={}; SlashCmdList={}; objects={}; sampleHeight=-100; sampleWater=0
          local m={}
          function m:SetText(t) self.text=t end
          function m:SetScale(value) self.scale=value end
          function m:Hide() self.hidden=true end
          function m:Show() self.hidden=false end
          function m:SetScript(k,v) self[k]=v end
          local function object() local o=setmetatable({},{__index=m});table.insert(objects,o);return o end
          function m:CreateFontString() return object() end
          function m:CreateLine() return object() end
          function m:CreateTexture() return object() end
          setmetatable(m,{__index=function()return function()end end})
          function CreateFrame(kind,name,parent,template)
            local o=object()
            if name=='AltimeterForeverFrame' then f=o end
            if template=='InterfaceOptionsCheckButtonTemplate' then o.Text=object(); checkbox=o end
            if kind=='Button' and parent==f then closeButton=o end
            return o
          end
          function m:SetChecked(value) self.checked=value end
          function m:GetChecked() return self.checked end
          Settings={RegisterCanvasLayoutCategory=function(panel) settingsPanel=panel;return panel end,
            RegisterAddOnCategory=function()end}
          function GetBuildInfo()return '1.60.1','70862' end
          function time()return 1 end
          function print()end
          C_Timer={NewTicker=function(_,cb)tick=cb;return {Cancel=function()end}end}
          C_Map={GetBestMapForUnit=function()return 1439 end}
          function UnitPosition()return 6000,1000,0,1 end
        ''')
        lua.execute((ROOT/'addon/Terrain.lua').read_text())
        lua.execute((ROOT/'addon/Gauge.lua').read_text())
        lua.execute('''
          AltimeterForever.build='70862';AltimeterForever.version='1.60.1.70862'
          AltimeterForever.maps={[1]={seaLevel=0}}
          AltimeterForever.Sample=function()return sampleHeight,nil,'1:30:20',0,0,1,sampleWater end
        ''')
        lua.execute((ROOT/'addon/Core.lua').read_text())
        lua.execute('f.OnEvent()')
        lua.execute("AltimeterForever.SetSize('Small')")
        self.assertEqual(lua.globals().f.scale, .70)
        lua.execute("AltimeterForever.SetSize('Large'); f.OnEvent()")
        self.assertEqual(lua.globals().f.scale, 1)
        self.assertEqual(lua.globals().AltimeterForeverDB.size, 'Large')
        lua.execute("AltimeterForever.SetSize('Medium')")
        self.assertEqual(lua.globals().f.scale, .85)
        def texts():return {o.text for o in lua.globals().objects.values() if isinstance(o.text,str)}
        self.assertTrue({'DEPTH','SEABED','91.4 m','Sea floor depth'}<=texts())
        lua.execute('sampleWater=nil;tick()')
        self.assertTrue({'ALTIMETER','GROUND','-91.4 m'}<=texts())
        self.assertNotIn('Below sea level',texts())
        self.assertNotIn('DEPTH',texts())
        lua.execute('sampleHeight=102;tick()')
        self.assertIn('+93.3 m',texts())
        self.assertNotIn('Above sea level',texts())
        lua.execute('sampleHeight=nil;tick()')
        self.assertIn('-- m',texts())
        self.assertNotIn('+93.3 m',texts())
        lua.execute("SlashCmdList.ALTIMETERFOREVER('')")
        self.assertTrue(lua.globals().AltimeterForeverDB.hidden)
        self.assertTrue(lua.globals().f.hidden)
        lua.execute('f.OnEvent()') # saved preference survives login initialization
        self.assertTrue(lua.globals().f.hidden)
        lua.execute('checkbox:SetChecked(true); checkbox.OnClick(checkbox)')
        self.assertFalse(lua.globals().AltimeterForeverDB.hidden)
        self.assertFalse(lua.globals().f.hidden)
        lua.execute('closeButton.OnClick(); settingsPanel.OnShow()')
        self.assertTrue(lua.globals().AltimeterForeverDB.hidden)
        self.assertFalse(lua.globals().checkbox.checked)
        lua.execute("SlashCmdList.ALTIMETERFOREVER('')")
        self.assertFalse(lua.globals().f.hidden)



if __name__=='__main__':unittest.main(verbosity=2)
