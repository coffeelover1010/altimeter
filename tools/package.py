"""Assemble the local-use install ZIP; verifies TOC files and writes hashes."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
build=root/('build-world' if (root/'build-world/manifest.json').exists() else 'build')
for p in (root/'addon').iterdir():
    if p.is_file():shutil.copy2(p,build/'AltimeterForever'/p.name)
folders=sorted(p for p in build.iterdir() if p.is_dir() and p.name.startswith('AltimeterForever'))
for folder in folders:
    toc=folder/(folder.name+'.toc')
    for line in toc.read_text().splitlines():
        if line.strip() and not line.startswith('#') and not (folder/line.strip()).is_file():
            raise RuntimeError(f'Missing TOC entry {folder.name}/{line}')
release=root/'dist'
release.mkdir(exist_ok=True)
files=[]
target=release/'Altimeter-0.2.0-70862.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for folder in folders:
        for p in sorted(folder.rglob('*')):
            if p.is_file():
                name=p.relative_to(build).as_posix()
                z.write(p,name)
                files.append(dict(path=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    for name in ['README.md','RESEARCH.md','VALIDATION.md']:
        z.write(root/name,'AltimeterForever-docs/'+name)
    for name in ['manifest.json','calibration.json','coverage.json']:
        if (build/name).exists():z.write(build/name,'AltimeterForever-docs/'+name)
(release/'file-hashes.json').write_text(json.dumps(files,indent=2))
with zipfile.ZipFile(target) as z:
    if z.testzip() is not None:raise RuntimeError('ZIP integrity failure')
print(f'{target}: {target.stat().st_size:,} bytes, {len(folders)} addon folders; ZIP integrity passed')
