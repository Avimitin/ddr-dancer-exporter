"""Extract a local DDR ARC to a specified workspace directory, including LZ77."""
import _bootstrap  # Local src/ discovery for direct invocation.
from pathlib import Path
import struct,sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from lz77 import Lz77
def extract(path,destination):
    path,destination=Path(path),Path(destination);destination.mkdir(parents=True,exist_ok=True)
    b=path.read_bytes();magic,version,count,kind=struct.unpack_from('<4I',b)
    assert magic==0x19751120 and version==1
    rows=[]
    for i in range(count):
        no,off,size,stored=struct.unpack_from('<4I',b,16+i*16)
        name=b[no:b.index(0,no)].decode('ascii');assert off+stored<=len(b)
        payload=b[off:off+stored]
        if stored<size:payload=Lz77().decompress(payload)
        assert len(payload)==size,(name,len(payload),size)
        output=destination/Path(name).name;output.write_bytes(payload)
        rows.append(dict(name=name,bytes=size,compressed=stored<size))
    (destination/'archive-manifest.json').write_text(json.dumps(rows,indent=2))
    return rows
if __name__=='__main__':print(json.dumps(extract(sys.argv[1],sys.argv[2]),indent=2))
