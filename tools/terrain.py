"""Strict, read-only Forever CASC -> independently loadable terrain tiles.

Python 3.10+, Windows x64 CascLib DLL. No network operations. No client writes.
"""
import argparse
import base64
import ctypes as c
import hashlib
import json
import math
import struct
from pathlib import Path

TILE = 1600 / 3
CHUNK = TILE / 16
STEP = CHUNK / 8


def chunks(data, start=0):
    while start < len(data):
        if start + 8 > len(data):
            raise ValueError("Truncated chunk header")
        tag = data[start:start + 4][::-1].decode('ascii')
        size, = struct.unpack_from('<I', data, start + 4)
        end = start + 8 + size
        if end > len(data):
            raise ValueError(f"Truncated {tag}")
        yield tag, data[start + 8:end]
        start = end


def parse_wdt(data):
    parts = dict(chunks(data))
    if parts.get('MVER') != struct.pack('<I', 18):
        raise ValueError('Unsupported WDT version')
    maid = parts.get('MAID', b'')
    if len(maid) != 4096 * 32:
        raise ValueError('WDT lacks complete MAID file ID table')
    return {(x, y): struct.unpack_from('<I', maid, (y * 64 + x) * 32)[0]
            for y in range(64) for x in range(64)}


def parse_adt(data, tx, ty):
    result, liquids = {}, []
    version = False
    for tag, p in chunks(data):
        if tag == 'MVER':
            version = p == struct.pack('<I', 18)
        elif tag == 'MCNK':
            if len(p) < 128:
                raise ValueError('Short MCNK')
            flags, ix, iy = struct.unpack_from('<3I', p)
            if ix > 15 or iy > 15 or (ix, iy) in result:
                raise ValueError('Invalid or duplicate MCNK index')
            area, = struct.unpack_from('<I', p, 52)
            north, west, base = struct.unpack_from('<3f', p, 104)
            # Verify the standard basis against every actual Forever header.
            if not all(math.isfinite(v) for v in (north, west, base)):
                raise ValueError('Nonfinite MCNK origin')
            if abs(north - ((32 - ty) * TILE - iy * CHUNK)) > .004 or abs(west - ((32 - tx) * TILE - ix * CHUNK)) > .004:
                raise ValueError('MCNK coordinate basis incompatible with WDT tile')
            sub = dict(chunks(p, 128))
            if len(sub.get('MCVT', b'')) != 580:
                raise ValueError('Missing/incompatible 145-vertex MCVT')
            heights = [base + h for h in struct.unpack('<145f', sub['MCVT'])]
            if not all(math.isfinite(h) for h in heights):
                raise ValueError('Nonfinite height')
            if flags & 0x10000:
                holes = list(p[20:28])
            else:
                low, = struct.unpack_from('<H', p, 60)
                holes = [sum(1 << x for x in range(8) if low & (1 << ((y // 2) * 4 + x // 2))) for y in range(8)]
            result[ix, iy] = dict(north=north, west=west, heights=heights, holes=holes, area=area)
        elif tag == 'MH2O':
            if len(p) < 3072:
                raise ValueError('Short MH2O')
            for idx in range(256):
                offset, count, attrs = struct.unpack_from('<3I', p, idx * 12)
                if count > 64 or (count and (offset < 3072 or offset + count * 24 > len(p))):
                    raise ValueError('Invalid liquid layer offsets')
                for layer in range(count):
                    kind, fmt, lo, hi, ox, oy, w, h, mask, vertices = struct.unpack_from('<HHff4BII', p, offset + layer * 24)
                    if not math.isfinite(lo) or not math.isfinite(hi):
                        raise ValueError('Nonfinite liquid level')
                    liquids.append(dict(chunk=idx, type=kind, format=fmt, minimum=lo, maximum=hi))
    if not version or len(result) != 256:
        raise ValueError('Requires v18 root ADT with 256 complete chunks')
    return result, liquids


def encode_heights(heights):
    base = math.floor(min(heights) * 1000) / 1000
    values = [round((h - base) * 1000) for h in heights]
    if any(v < 0 or v > 0xFFFFFF for v in values):
        raise ValueError('Height range exceeds encoding')
    raw = b''.join(v.to_bytes(3, 'big') for v in values)
    return base, base64.b64encode(raw).decode('ascii')


class Casc:
    def __init__(self, dll, storage, product):
        self.lib = c.WinDLL(str(Path(dll).resolve()), use_last_error=True)
        H, D = c.c_void_p, c.c_uint32
        signatures = {
            'CascOpenStorage': ([c.c_char_p, D, c.POINTER(H)], c.c_bool),
            'CascOpenFile': ([H, c.c_void_p, D, D, c.POINTER(H)], c.c_bool),
            'CascGetFileSize64': ([H, c.POINTER(c.c_uint64)], c.c_bool),
            'CascReadFile': ([H, c.c_void_p, D, c.POINTER(D)], c.c_bool),
            'CascCloseFile': ([H], c.c_bool), 'CascCloseStorage': ([H], c.c_bool),
        }
        for name, (args, ret) in signatures.items():
            f = getattr(self.lib, name)
            f.argtypes, f.restype = args, ret
        self.handle = H()
        if not self.lib.CascOpenStorage(f'{Path(storage).resolve()}*{product}'.encode('mbcs'), 2, c.byref(self.handle)):
            raise OSError(c.get_last_error(), 'CascOpenStorage')

    def read(self, file_id):
        h = c.c_void_p()
        if not self.lib.CascOpenFile(self.handle, file_id, 2, 0x13, c.byref(h)):
            raise OSError(c.get_last_error(), f'CascOpenFile FDID {file_id}')
        try:
            size = c.c_uint64()
            if not self.lib.CascGetFileSize64(h, c.byref(size)):
                raise OSError(c.get_last_error(), f'CascGetFileSize64 FDID {file_id}')
            if size.value > 64 * 1024 * 1024:
                raise ValueError('Unexpectedly large terrain file')
            buf, got = c.create_string_buffer(size.value), c.c_uint32()
            if not self.lib.CascReadFile(h, buf, size.value, c.byref(got)) or got.value != size.value:
                raise OSError(c.get_last_error(), f'CascReadFile FDID {file_id}; {got.value}/{size.value}')
            return buf.raw
        finally:
            self.lib.CascCloseFile(h)

    def close(self):
        self.lib.CascCloseStorage(self.handle)


def build_info(storage, product='wowf'):
    lines = (Path(storage) / '.build.info').read_text().splitlines()
    names = [v.split('!')[0] for v in lines[0].split('|')]
    records = [dict(zip(names, line.split('|'))) for line in lines[1:] if line]
    records = [r for r in records if r.get('Product') == product and r.get('Active') == '1']
    if len(records) != 1:
        raise ValueError('Need exactly one active Forever build')
    return records[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dll', required=True)
    ap.add_argument('--storage', required=True)
    ap.add_argument('--output', type=Path, required=True, help='New/empty directory for generated addon folders')
    ap.add_argument('--cache', type=Path, required=True)
    ap.add_argument('--wdt-id', type=int, default=775971)
    ap.add_argument('--map-id', type=int, default=0)
    ap.add_argument('--bounds', type=int, nargs=4, default=[28, 47, 35, 51], metavar=('XMIN', 'YMIN', 'XMAX', 'YMAX'))
    args = ap.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        ap.error('Output must be empty; generate in a new directory to avoid stale tiles')
    if not (0 <= args.bounds[0] <= args.bounds[2] < 64 and 0 <= args.bounds[1] <= args.bounds[3] < 64):
        ap.error('Bounds must be ordered within 0..63')
    info = build_info(args.storage)
    version, key = info['Version'], info['Build Key']
    args.output.mkdir(parents=True, exist_ok=True)
    cache = args.cache / key
    cache.mkdir(parents=True, exist_ok=True)
    source = Casc(args.dll, args.storage, 'wowf')
    manifest = dict(product='wowf', version=version, buildKey=key, mapID=args.map_id, wdtID=args.wdt_id,
                    quantizationYards=.001, status='offline geometry; live coordinate validation pending', tiles=[], failures=[])
    index = []
    def fetch(fid):
        # Always re-read the installed archive; cache is evidence, never a fallback.
        data = source.read(fid)
        (cache / f'{fid}.bin').write_bytes(data)
        return data
    try:
        wdt = fetch(args.wdt_id)
        manifest['wdtSHA256'] = hashlib.sha256(wdt).hexdigest()
        ids = parse_wdt(wdt)
        for ty in range(args.bounds[1], args.bounds[3] + 1):
            for tx in range(args.bounds[0], args.bounds[2] + 1):
                fid = ids[tx, ty]
                if not fid:
                    manifest['failures'].append(dict(x=tx, y=ty, reason='WDT has no root ADT'))
                    continue
                try:
                    data = fetch(fid)
                    terrain, liquids = parse_adt(data, tx, ty)
                    name = f'AltimeterForever_T{args.map_id}_{tx}_{ty}'
                    folder = args.output / name
                    rows = []
                    worst = 0
                    for (ix, iy), chunk in sorted(terrain.items(), key=lambda kv: (kv[0][1], kv[0][0])):
                        base, encoded = encode_heights(chunk['heights'])
                        decoded = base64.b64decode(encoded)
                        worst = max(worst, max(abs(h - (base + int.from_bytes(decoded[i*3:i*3+3], 'big') / 1000)) for i, h in enumerate(chunk['heights'])))
                        holes = ','.join(map(str, chunk['holes']))
                        rows.append(f'[{iy*16+ix+1}]={{{chunk["north"]:.9f},{chunk["west"]:.9f},{base:.3f},"{encoded}",{{{holes}}},{chunk["area"]}}},')
                    folder.mkdir()
                    (folder / f'{name}.toc').write_text(f'## Interface: 16001\n## Title: Altimeter terrain {args.map_id}/{tx}/{ty}\n## LoadOnDemand: 1\n## Dependencies: AltimeterForever\nData.lua\n')
                    tile_key = f'{args.map_id}:{tx}:{ty}'
                    (folder / 'Data.lua').write_text(f'AltimeterForever.tiles["{tile_key}"]={{\n' + '\n'.join(rows) + '\n}\n')
                    origin = terrain[0, 0]
                    index.append(f'["{tile_key}"]={{"{name}",{origin["north"]:.9f},{origin["west"]:.9f}}},')
                    manifest['tiles'].append(dict(x=tx, y=ty, fileID=fid, sha256=hashlib.sha256(data).hexdigest(),
                        maxEncodingError=worst, minimum=min(min(v['heights']) for v in terrain.values()),
                        maximum=max(max(v['heights']) for v in terrain.values()),
                        areas=sorted({v['area'] for v in terrain.values()}), liquids=liquids))
                    print(f'{tx},{ty}: {fid}, 256 chunks, encoding error {worst:.7f} yd', flush=True)
                except (ValueError, OSError) as e:
                    manifest['failures'].append(dict(x=tx, y=ty, fileID=fid, reason=str(e)))
                    print(f'{tx},{ty}: UNAVAILABLE: {e}', flush=True)
    finally:
        source.close()
    if build_info(args.storage)['Build Key'] != key:
        raise RuntimeError('Client updated during extraction; discard output')
    main_dir = args.output / 'AltimeterForever'
    main_dir.mkdir()
    (main_dir / 'Reference.lua').write_text('-- No verified water reference. Run tools/calibrate.py for the pilot.\n')
    (main_dir / 'Database.lua').write_text('local A=AltimeterForever\n' +
        f'A.build="{version.split(".")[-1]}"\nA.version="{version}"\nA.buildKey="{key}"\nA.mapID={args.map_id}\nA.tileSize={TILE:.12f}\nA.chunkSize={CHUNK:.12f}\nA.step={STEP:.12f}\nA.index={{\n' + '\n'.join(index) + '\n}\n')
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(f'{len(index)} tiles; {len(manifest["failures"])} unavailable. See manifest.json.')
    if not index:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
