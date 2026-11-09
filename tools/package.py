"""Assemble the local-use install ZIP; verifies TOC files and writes hashes."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
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
folders=[main,module]+sorted(p for p in build.iterdir() if p.is_dir() and p.name.startswith('AltimeterForever_W'))
entries=[]
for folder in folders:
    toc=folder/(folder.name+'.toc')
    if folder not in (main,module):
        toc.write_text(toc.read_text().replace('## Dependencies: AltimeterForever','## Dependencies: AltimeterHeightData'))
        shutil.copy2(root/'height-module/LICENSE',folder/'LICENSE')
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
target=release/'Altimeter-0.2.0-70862.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in entries:
        name=p.relative_to(build).as_posix()
        z.write(p,name)
        files.append(dict(path=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    for name in ['README.md','RESEARCH.md','VALIDATION.md','CURSEFORGE.md','LICENSE']:
        z.write(root/name,'AltimeterForever-docs/'+name)
    for name in ['manifest.json','calibration.json','coverage.json']:
        if (build/name).exists():z.write(build/name,'AltimeterForever-docs/'+name)
(release/'file-hashes.json').write_text(json.dumps(files,indent=2))
with zipfile.ZipFile(target) as z:
    if z.testzip() is not None:raise RuntimeError('ZIP integrity failure')
print(f'{target}: {target.stat().st_size:,} bytes, {len(folders)} addon folders; ZIP integrity passed')

# Separate distributions let other authors use the height module without the UI.
for label,selected in [('Altimeter-addon',[p for p in entries if p.parent==main]),
                       ('Altimeter-HeightData',[p for p in entries if p.parent!=main])]:
    archive=release/(label+'-0.2.0-70862.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in selected:z.write(p,p.relative_to(build).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise RuntimeError('ZIP integrity failure')
    print(f'{archive}: ZIP integrity passed')
