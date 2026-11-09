"""Verify the pilot harbour's static ocean datum from the same local Forever build.

Intentionally narrow: reject different DB2 layouts or ocean vertex formats.
This establishes a regional static water datum, not character height or global sea level.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from terrain import Casc, build_info, chunks


def ocean_name(data):
    if len(data) < 244 or data[:4] != b'WDC5' or struct.unpack_from('<I',data,156)[0] != 0xD1ECEEC9:
        raise ValueError('Unsupported LiquidType DB2 layout')
    count, fields, size, strings = struct.unpack_from('<4I',data,136)
    if (fields,size) != (21,40) or struct.unpack_from('<I',data,200)[0] != 1:
        raise ValueError('Unsupported LiquidType record/section shape')
    key, offset, n, ss, end, ids, rel, sparse, copies = struct.unpack_from('<Q8I',data,204)
    if key or n != count or ss != strings or ids != count*4 or rel or sparse or copies:
        raise ValueError('Unsupported LiquidType section')
    if offset + count*size + strings + ids != len(data):
        raise ValueError('LiquidType size mismatch')
    if struct.unpack_from('<HHIIIII',data,328) != (0,32,0,0,0,0,0):
        raise ValueError('Unexpected LiquidType name encoding')
    for i in range(count):
        record_id = struct.unpack_from('<I',data,offset+count*size+strings+i*4)[0]
        if record_id == 1250:
            pos = offset+i*size
            ptr = pos+struct.unpack_from('<i',data,pos)[0]
            if not offset+count*size <= ptr < offset+count*size+strings:
                raise ValueError('Invalid LiquidType name offset')
            name = data[ptr:data.index(0,ptr,offset+count*size+strings)].decode()
            if name != 'PBRWater - Generic - Ocean':
                raise ValueError('Liquid 1250 is no longer the expected ocean')
            return name
    raise ValueError('Ocean liquid type absent')


def ocean_layers(data):
    p = dict(chunks(data))['MH2O']
    count = 0
    for idx in range(256):
        off, n, attrs = struct.unpack_from('<3I',p,idx*12)
        for i in range(n):
            kind, fmt, lo, hi, ox, oy, w, h, mask, vertices = struct.unpack_from('<HHff4BII',p,off+i*24)
            if kind != 1250:
                continue
            # These pilot records are full 9x9 height + depth vertices.
            # Verify every height and reject rather than infer other formats.
            if (fmt,lo,hi,ox,oy,w,h) != (42,0.,0.,0,0,8,8) or vertices < 3072 or vertices+405 > len(p):
                raise ValueError('Ocean layer differs from supported zero-height pilot format')
            if any(v != 0 for v in struct.unpack_from('<81f',p,vertices)):
                raise ValueError('Ocean vertex height differs from zero')
            count += 1
    if not count:
        raise ValueError('No ocean reference layers')
    return count


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dll',required=True)
    ap.add_argument('--storage',required=True)
    ap.add_argument('--build',type=Path,required=True)
    args=ap.parse_args()
    manifest=json.loads((args.build/'manifest.json').read_text())
    if manifest['buildKey'] != build_info(args.storage)['Build Key'] or manifest['mapID'] != 0:
        raise ValueError('Calibration build/map mismatch')
    source=Casc(args.dll,args.storage,'wowf')
    report=dict(buildKey=manifest['buildKey'],worldZ=0,scope='Stormwind Harbour static ocean',tiles=[])
    try:
        liquid=source.read(1371380)
        report['liquidName']=ocean_name(liquid)
        report['liquidSHA256']=hashlib.sha256(liquid).hexdigest()
        for xy in [(28,47),(28,48),(29,48)]:
            tile=next(t for t in manifest['tiles'] if (t['x'],t['y'])==xy)
            data=source.read(tile['fileID'])
            if hashlib.sha256(data).hexdigest() != tile['sha256']:
                raise ValueError('Terrain file changed since extraction')
            report['tiles'].append(dict(x=xy[0],y=xy[1],fileID=tile['fileID'],layers=ocean_layers(data)))
    finally:
        source.close()
    if manifest['buildKey'] != build_info(args.storage)['Build Key']:
        raise ValueError('Client changed during calibration')
    (args.build/'calibration.json').write_text(json.dumps(report,indent=2))
    (args.build/'AltimeterForever/Reference.lua').write_text(
        f'AltimeterForever.reference={{z=0, name="Harbour sea datum", buildKey="{manifest["buildKey"]}"}}\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
