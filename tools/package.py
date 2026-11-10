"""Assemble the local-use install ZIP; verifies TOC files and writes hashes."""
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
version=re.search(r'^## Version: (.+)$', (root/'addon/AltimeterForever.toc').read_text(), re.M).group(1).strip()

def validate_archive(archive):
    with zipfile.ZipFile(archive) as z:
        names=set(z.namelist())
        folders={name.split('/',1)[0] for name in names if '/' in name}
        for folder in folders:
            if f'{folder}/{folder}.toc' not in names:
                raise RuntimeError(f'Addon folder lacks matching TOC: {folder}')
        if z.testzip() is not None:
            raise RuntimeError('ZIP integrity failure')

build=root/('build-world' if (root/'build-world/manifest.json').exists() else 'build')
main=build/'AltimeterForever'
module=build/'AltimeterHeightData'
module.mkdir(exist_ok=True)
for name in ('Database.lua','Reference.lua'):
    shutil.copy2(main/name,module/name)
for source,destination in ((root/'addon',main),(root/'height-module',module)):
    for p in source.iterdir():
        if p.is_file():shutil.copy2(p,destination/p.name)
shutil.copy2(root/'LICENSE',main/'LICENSE')
from regions import assemble
folders=assemble(build, root/'build-package', root)
build=root/'build-package'
main=build/'AltimeterForever'
module=build/'AltimeterHeightData'
entries=[]
for folder in folders:
    toc=folder/(folder.name+'.toc')
    names=[folder.name+'.toc','LICENSE']
    if folder==module:names.append('README.md')
    names += [line.strip() for line in toc.read_text().splitlines() if line.strip() and not line.startswith('#')]
    for name in names:
        p=folder/name
        if not p.is_file():raise RuntimeError(f'Missing entry {p}')
        entries.append(p)
release=root/'dist'
release.mkdir(exist_ok=True)
files=[]
target=release/f'Altimeter-{version}-70862.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in entries:
        name=p.relative_to(build).as_posix()
        z.write(p,name)
        files.append(dict(path=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    for name in ['README.md','RESEARCH.md','VALIDATION.md','CURSEFORGE.md','LICENSE']:
        z.write(root/name,'AltimeterForever/docs/'+name)
    for name in ['manifest.json','calibration.json','coverage.json']:
        if (build/name).exists():z.write(build/name,'AltimeterForever/docs/'+name)
    for p in sorted((root/'assets/gallery').glob('*.png')):
        z.write(p,'AltimeterForever/docs/assets/gallery/'+p.name)
(release/'file-hashes.json').write_text(json.dumps(files,indent=2))
validate_archive(target)
print(f'{target}: {target.stat().st_size:,} bytes, {len(folders)} addon folders; ZIP integrity passed')

# Separate distributions let other authors use the height module without the UI.
for label,selected in [('Altimeter-addon',[p for p in entries if p.parent==main]),
                       ('Altimeter-HeightData',[p for p in entries if p.parent!=main])]:
    archive=release/(label+f'-{version}-70862.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in selected:z.write(p,p.relative_to(build).as_posix())
    validate_archive(archive)
    print(f'{archive}: ZIP integrity passed')
