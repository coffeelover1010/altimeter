"""Verify the packaged height module works without loading the gauge addon."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent/'cf-ui-research/python-tools'))
from lupa.lua51 import LuaRuntime

class ModuleTests(unittest.TestCase):
    def test_standalone_sample_and_dependency_graph(self):
        build=ROOT/'build-world'
        lua=LuaRuntime(unpack_returned_tuples=True)
        loaded=set()
        def load(name):
            if name in loaded:return True
            folder=build/name
            lines=(folder/(name+'.toc')).read_text().splitlines()
            for line in lines:
                if line.startswith('## Dependencies:'):
                    for dep in line.split(':',1)[1].split(','):
                        self.assertNotEqual(dep.strip(),'AltimeterForever')
                        load(dep.strip())
            loaded.add(name)
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    lua.execute((folder/line.strip()).read_text())
            return True
        lua.globals().C_AddOns=lua.table_from({'LoadAddOn':load})
        load('AltimeterHeightData')
        api=lua.globals().AltimeterHeightData
        self.assertEqual(api.apiVersion,1)
        result=api.Sample(-8540,1029.8,0)
        self.assertIsInstance(result[0],(float,int))
        self.assertAlmostEqual(result[0],15.119,places=2)
        self.assertNotIn('AltimeterForever',loaded)
        self.assertIsNone(lua.globals().AltimeterForeverFrame)
        self.assertGreater(len(loaded),1)
        self.assertIn('## Dependencies: AltimeterHeightData',(build/'AltimeterForever/AltimeterForever.toc').read_text())
        for toc in build.glob('AltimeterForever_W*/*.toc'):
            self.assertIn('## Dependencies: AltimeterHeightData',toc.read_text())

if __name__=='__main__':unittest.main(verbosity=2)
