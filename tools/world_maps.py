"""Read only complete unencrypted Map.db2 sections from the local product.

No missing bytes are filled or interpreted. Layout is pinned to the inspected
Forever layout, with field storage and section bounds checked before decoding.
"""
import ctypes as c
import hashlib
import struct


def read_prefix(source, fid):
    h=c.c_void_p()
    if not source.lib.CascOpenFile(source.handle,fid,2,0x13,c.byref(h)):
        raise OSError(c.get_last_error(),f'Open {fid}')
    try:
        size=c.c_uint64()
        if not source.lib.CascGetFileSize64(h,c.byref(size)) or size.value>10_000_000:
            raise ValueError('Invalid table size')
        buf=c.create_string_buffer(size.value);got=c.c_uint32()
        ok=source.lib.CascReadFile(h,buf,size.value,c.byref(got))
        error=c.get_last_error() if got.value!=size.value or not ok else 0
        return buf.raw[:got.value],dict(fileID=fid,totalBytes=size.value,readBytes=got.value,error=error)
    finally:source.lib.CascCloseFile(h)


def decode_maps(b):
    if len(b)<204 or b[:4]!=b'WDC5' or struct.unpack_from('<I',b,156)[0]!=0xD43AFAC3:
        raise ValueError('Unsupported Forever Map layout')
    total,fields,size,strings=struct.unpack_from('<4I',b,136)
    flags=struct.unpack_from('<H',b,172)[0]
    sections=struct.unpack_from('<I',b,200)[0]
    if fields!=26 or flags!=4 or not 1<=sections<32:raise ValueError('Unsupported Map shape')
    headers=[struct.unpack_from('<Q8I',b,204+i*40) for i in range(sections)]
    o=204+sections*40+fields*4
    cols=[struct.unpack_from('<HHIIIII',b,o+i*24) for i in range(fields)]
    p=o+24*fields;pal={}
    for kind in (3,4):
        for i,col in enumerate(cols):
            if col[3]==kind:
                pal[i]=struct.unpack_from('<'+'I'*(col[2]//4),b,p);p+=col[2]
    rows=[];unread=[];previous=0
    # String addressing spans all logical records, including unread sections.
    for section in headers:
        key,offset,n,ss,end,ids,rel,sparse,copies=section
        section_end=offset+n*size+ss+ids
        if key or section_end>len(b):
            unread.append(dict(records=n,reason='encrypted or unreadable section',offset=offset))
            previous+=n
            continue
        if ids!=n*4 or rel or sparse or copies:raise ValueError('Unsupported Map section metadata')
        for i in range(n):
            pos=offset+i*size;bits=int.from_bytes(b[pos:pos+size],'little')
            map_id=struct.unpack_from('<I',b,offset+n*size+ss+i*4)[0]
            def value(j):
                off,width,extra,kind,a,w,card=cols[j]
                v=(bits>>off)&((1<<width)-1)
                if kind==3:return pal[j][v]
                if kind==5 and v&(1<<(width-1)):return v-(1<<width)
                if kind not in (0,1,5):raise ValueError('Unsupported field compression')
                return v
            def string(j):
                if cols[j]!=(j*32,32,0,0,0,0,0):raise ValueError('Unexpected name encoding')
                q=pos+j*4+struct.unpack_from('<i',b,pos+j*4)[0]-(total-n)*size
                if not offset+n*size<=q<section_end-ids:raise ValueError('Name outside section strings')
                return b[q:b.index(0,q,section_end-ids)].decode()
            rows.append(dict(id=map_id,directory=string(0),name=string(1),wdt=value(21),oceanType=value(22),instanceType=value(8)))
        previous+=n
    if previous!=total:raise ValueError('Record count mismatch')
    return rows,unread


def discover(source):
    data,report=read_prefix(source,1349477)
    rows,unread=decode_maps(data)
    report.update(sha256=hashlib.sha256(data).hexdigest(),unreadSections=unread)
    return rows,report,data
