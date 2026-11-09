"""Generate all readable Forever ADT maps, grouped into 4x4-tile load-on-demand packs."""
import argparse
import hashlib
import json
import math
import shutil
import struct
from collections import Counter
from pathlib import Path
from terrain import Casc, build_info, chunks, parse_wdt, parse_adt, encode_heights, TILE, CHUNK, STEP
from world_maps import discover


def verify_liquid_formats(types, materials):
    # Layout-checked local DB2 evidence for material-based >=42 records.
    if types[:4]!=b'WDC5' or struct.unpack_from('<I',types,156)[0]!=0xD1ECEEC9:
        raise ValueError('Unsupported LiquidType layout')
    if materials[:4]!=b'WDC5' or struct.unpack_from('<I',materials,156)[0]!=0x98E5D7AA:
        raise ValueError('Unsupported LiquidMaterial layout')
    if struct.unpack_from('<4I',materials,136)!=(4,2,1,2) or struct.unpack_from('<Q8I',materials,204)!=(0,300,4,2,0,16,0,0,1):
        raise ValueError('Unsupported LiquidMaterial section')
    if struct.unpack_from('<HHIIIII',materials,276)!=(2,3,0,5,2,3,0):
        raise ValueError('Unsupported liquid vertex-format encoding')
    mats={struct.unpack_from('<I',materials,306+i*4)[0]:(materials[300+i]>>2)&7 for i in range(4)}
    dest,src=struct.unpack_from('<II',materials,322);mats[dest]=mats[src]
    n,f,size,strings=struct.unpack_from('<4I',types,136)
    key,off,count,ss,_,ids,rel,sparse,copies=struct.unpack_from('<Q8I',types,204)
    if key or (f,size)!=(21,40) or n!=count or ss!=strings or ids!=n*4 or rel or sparse or copies:
        raise ValueError('Unsupported LiquidType section')
    if struct.unpack_from('<HHIIIII',types,328+14*24)!=(266,8,0,1,42,8,0):
        raise ValueError('Unsupported liquid material encoding')
    formats={2:2} # Ocean type 2 is the defined depth-only special case.
    for i in range(n):
        id=struct.unpack_from('<I',types,off+n*size+strings+i*4)[0]
        if id in (1250,1296):
            material=(int.from_bytes(types[off+i*size:off+(i+1)*size],'little')>>266)&255
            formats[id]=mats[material]
    if formats!={2:2,1250:0,1296:0}:raise ValueError('Ocean formats changed; review required')
    return formats


def ocean_cells(data, ocean_type):
    """Only exact flat ocean layers of known layout; no inferred lake/river levels."""
    p=dict(chunks(data)).get('MH2O')
    result={};rejected=Counter()
    if p is None:return result,rejected
    for idx in range(256):
        off,count,_=struct.unpack_from('<3I',p,idx*12)
        for i in range(count):
            kind,fmt,lo,hi,ox,oy,w,h,mask,vertices=struct.unpack_from('<HHff4BII',p,off+i*24)
            if kind!=ocean_type:continue
            if fmt>=42:
                ox,oy,w,h=0,0,8,8
                fmt={2:2,1250:0,1296:0}.get(kind,-1)
            if fmt not in (0,1,2,3) or not (0<w<=8 and 0<h<=8 and ox+w<=8 and oy+h<=8):
                rejected['unsupported ocean format/bounds']+=1;continue
            if lo!=hi or not math.isfinite(lo):
                rejected['non-flat ocean']+=1;continue
            n=(w+1)*(h+1)
            if fmt==2 or vertices==0:
                if lo!=0:rejected['nonzero implicit ocean level']+=1;continue
            else:
                # Height-based known formats store the contiguous float32 heights first.
                if vertices+n*4>len(p):
                    rejected['missing ocean vertices']+=1;continue
                if any(abs(v-lo)>0.00001 for v in struct.unpack_from('<'+'f'*n,p,vertices)):
                    rejected['ocean heights disagree with flat level']+=1;continue
            mask_len=(w*h+7)//8
            if mask and mask+mask_len>len(p):raise ValueError('Truncated ocean existence mask')
            exists=int.from_bytes(p[mask:mask+mask_len],'little') if mask else (1<<(w*h))-1
            rows=[0]*8
            for y in range(h):
                for x in range(w):
                    if exists & (1<<(y*w+x)):rows[y+oy]|=1<<(x+ox)
            if any(rows):result.setdefault(idx+1,[]).append((lo,rows))
    return result,rejected


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dll',required=True);ap.add_argument('--storage',required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--cache',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists() and any(args.output.iterdir()):ap.error('Output must be empty')
    args.output.mkdir(parents=True,exist_ok=True)
    info=build_info(args.storage);key=info['Build Key'];version=info['Version']
    cache=args.cache/key;cache.mkdir(parents=True,exist_ok=True)
    source=Casc(args.dll,args.storage,'wowf')
    manifest=dict(product='wowf',version=version,buildKey=key,maps=[],tiles=[],failures=[],quantizationYards=.001)
    index=[];map_lines=[];packs={}
    def read(fid):
        b=source.read(fid);(cache/f'{fid}.bin').write_bytes(b);return b
    try:
        maps,report,raw=discover(source)
        liquid_types,liquid_materials=read(1371380),read(1132538)
        manifest['liquidFormats']=verify_liquid_formats(liquid_types,liquid_materials)
        manifest['liquidTypeSHA256']=hashlib.sha256(liquid_types).hexdigest()
        manifest['liquidMaterialSHA256']=hashlib.sha256(liquid_materials).hexdigest()
        manifest['mapDiscovery']=report
        (cache/'Map-readable-prefix.db2').write_bytes(raw)
        for world in maps:
            m=dict(world,tiles=0,waterLayers=0);manifest['maps'].append(m)
            if not world['wdt']:m['status']='No WDT (transport or non-terrain map)';continue
            try:
                wdt=read(world['wdt']);parts=dict(chunks(wdt))
                if struct.unpack_from('<I',parts['MPHD'])[0]&1:
                    m['status']='World-object interior; no terrain mesh';continue
                ids=parse_wdt(wdt)
                m['wdtSHA256']=hashlib.sha256(wdt).hexdigest()
            except (ValueError,OSError,KeyError,struct.error) as e:
                m['status']=str(e);continue
            levels=set();rejected=Counter()
            for (tx,ty),fid in ids.items():
                if not fid:continue
                try:
                    data=read(fid);terrain,_=parse_adt(data,tx,ty)
                    water,skip=ocean_cells(data,world['oceanType']);rejected.update(skip)
                    pack=f'AltimeterForever_W{world["id"]}_{tx//4}_{ty//4}'
                    folder=args.output/pack;folder.mkdir(exist_ok=True)
                    file=f'T{tx}_{ty}.lua';rows=[]
                    for (ix,iy),chunk in sorted(terrain.items(),key=lambda kv:(kv[0][1],kv[0][0])):
                        base,encoded=encode_heights(chunk['heights']);idx=iy*16+ix+1
                        ws=water.get(idx,[])
                        layers='{'+','.join('{'+repr(z)+',{'+','.join(map(str,mask))+'}}' for z,mask in ws)+'}'
                        holes=','.join(map(str,chunk['holes']))
                        rows.append(f'[{idx}]={{{chunk["north"]:.9f},{chunk["west"]:.9f},{base:.3f},"{encoded}",{{{holes}}},{chunk["area"]},{layers}}},')
                        for z,_ in ws:levels.add(z);m['waterLayers']+=1
                    tile_key=f'{world["id"]}:{tx}:{ty}'
                    (folder/file).write_text(f'AltimeterForever.tiles["{tile_key}"]={{\n'+'\n'.join(rows)+'\n}\n')
                    packs.setdefault(pack,[]).append(file)
                    origin=terrain[0,0]
                    index.append(f'["{tile_key}"]={{"{pack}",{origin["north"]:.9f},{origin["west"]:.9f}}},')
                    manifest['tiles'].append(dict(mapID=world['id'],x=tx,y=ty,fileID=fid,sha256=hashlib.sha256(data).hexdigest(),waterChunks=len(water)))
                    m['tiles']+=1
                except (ValueError,OSError,struct.error) as e:
                    manifest['failures'].append(dict(mapID=world['id'],x=tx,y=ty,fileID=fid,reason=str(e)))
            m['status']='Extracted' if m['tiles'] else 'No readable terrain tiles'
            m['oceanLevels']=sorted(levels);m['rejectedOceanLayers']=dict(rejected)
            # A sea reference applies only if all accepted ocean layers agree.
            sea=repr(next(iter(levels))) if len(levels)==1 else 'nil'
            map_lines.append(f'[{world["id"]}]={{name={json.dumps(world["name"])},seaLevel={sea}}},')
            print(f'{world["id"]} {world["name"]}: {m["tiles"]} tiles, {m["waterLayers"]} ocean layers, levels={sorted(levels)}',flush=True)
    finally:source.close()
    if build_info(args.storage)['Build Key']!=key:raise RuntimeError('Client build changed during extraction')
    for name,files in packs.items():
        (args.output/name/(name+'.toc')).write_text('## Interface: 16001\n## Title: Altimeter world terrain\n## LoadOnDemand: 1\n## Dependencies: AltimeterForever\n'+'\n'.join(files)+'\n')
    main=args.output/'AltimeterForever';main.mkdir()
    (main/'Database.lua').write_text(f'local A=AltimeterForever\nA.build="{version.split(".")[-1]}"\nA.version="{version}"\nA.buildKey="{key}"\nA.tileSize={TILE:.12f}\nA.chunkSize={CHUNK:.12f}\nA.step={STEP:.12f}\nA.maps={{\n'+'\n'.join(map_lines)+'\n}\nA.index={\n'+'\n'.join(index)+'\n}\n')
    (main/'Reference.lua').write_text('-- References are per map, in Database.lua.\n')
    for p in (Path(__file__).resolve().parents[1]/'addon').iterdir():
        if p.is_file():shutil.copy2(p,main/p.name)
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(f'COMPLETE: {len(manifest["tiles"])} tiles, {len(packs)} packs, {len(manifest["failures"])} tile failures',flush=True)


if __name__=='__main__':main()
