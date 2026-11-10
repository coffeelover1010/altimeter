"""Repackage extracted tiles into six load-on-demand regional addons."""
import json
import re
import shutil

LABELS = {
    'EasternNorth': 'Eastern Kingdoms - North',
    'EasternSouth': 'Eastern Kingdoms - South',
    'KalimdorNorth': 'Kalimdor - North',
    'KalimdorSouth': 'Kalimdor - South',
    'OtherWorlds': 'Other world maps',
    'Instances': 'Dungeons, raids and battlegrounds',
}

def assemble(source, destination, root):
    destination.mkdir(exist_ok=True)
    for name in ('AltimeterForever', 'AltimeterHeightData'):
        shutil.copytree(source/name, destination/name, dirs_exist_ok=True)
    maps = {m['id']: m for m in json.loads((source/'coverage.json').read_text())['maps']}
    files = {key: [] for key in LABELS}
    database = (source/'AltimeterHeightData/Database.lua').read_text()
    pattern = re.compile(r'(\["(\d+):(\d+):(\d+)"\]=\{)"(AltimeterForever_W\d+_\d+_\d+)"')
    def tile(match):
        map_id, x, y = map(int, match.group(2, 3, 4))
        if map_id in (0, 1):
            key = ('Eastern' if map_id == 0 else 'Kalimdor') + ('North' if y < 32 else 'South')
        else:
            key = 'OtherWorlds' if maps[map_id]['instanceType'] == 0 else 'Instances'
        name = 'AltimeterData_' + key
        folder = destination/name
        folder.mkdir(exist_ok=True)
        filename = f'M{map_id}_T{x}_{y}.lua'
        shutil.copy2(source/match.group(5)/f'T{x}_{y}.lua', folder/filename)
        files[key].append(filename)
        return match.group(1) + '"' + name + '"'
    database, count = pattern.subn(tile, database)
    expected = len(json.loads((source/'manifest.json').read_text())['tiles'])
    if count != expected:
        raise RuntimeError(f'Index migration incomplete: {count} of {expected} tiles')
    (destination/'AltimeterHeightData/Database.lua').write_text(database)
    for key, names in files.items():
        if not names or len(names) != len(set(names)):
            raise RuntimeError(f'Empty or duplicate regional data: {key}')
        name = 'AltimeterData_' + key
        folder = destination/name
        (folder/(name+'.toc')).write_text(
            '## Interface: 16001\n## Title: Altimeter Data: '+LABELS[key]+'\n'
            '## Category: Altimeter\n## Group: AltimeterHeightData\n'
            '## IconTexture: Interface\\Icons\\INV_Misc_Map_01\n'
            '## LoadOnDemand: 1\n## Dependencies: AltimeterHeightData\n'
            + '\n'.join(sorted(names))+'\n')
        shutil.copy2(root/'height-module/LICENSE', folder/'LICENSE')
        print(f'{LABELS[key]}: {len(names)} tiles', flush=True)
    for name in ('manifest.json', 'calibration.json', 'coverage.json'):
        if (source/name).exists():
            shutil.copy2(source/name, destination/name)
    return [destination/'AltimeterForever', destination/'AltimeterHeightData'] + [destination/('AltimeterData_'+key) for key in LABELS]
