import struct
class Wad:
    def __init__(s, path):
        d = open(path,'rb').read(); s.data=d
        t,n,o = struct.unpack('<4sII', d[:12])
        s.lumps=[]
        for i in range(n):
            p,sz,nm = struct.unpack('<II8s', d[o+16*i:o+16*i+16])
            s.lumps.append((nm.rstrip(b'\0').decode('ascii','replace').upper(), d[p:p+sz]))
    def get(s,name,start=0):
        for i in range(start,len(s.lumps)):
            if s.lumps[i][0]==name: return s.lumps[i][1]
def load_map(path):
    w=Wad(path); L={}
    for nm,dat in w.lumps: L[nm]=dat
    m={}
    m['name']=w.lumps[0][0]
    m['things']=[dict(zip(('x','y','angle','type','flags'),struct.unpack('<hhHHH',L['THINGS'][i:i+10]))) for i in range(0,len(L['THINGS']),10)]
    m['lines']=[dict(zip(('v1','v2','flags','special','tag','s1','s2'),struct.unpack('<HHHHHHH',L['LINEDEFS'][i:i+14]))) for i in range(0,len(L['LINEDEFS']),14)]
    for l in m['lines']:
        if l['s2']==0xFFFF: l['s2']=-1
        if l['s1']==0xFFFF: l['s1']=-1
    def nm8(b): return b.rstrip(b'\0').decode('ascii','replace').upper()
    m['sides']=[]
    D=L['SIDEDEFS']
    for i in range(0,len(D),30):
        xo,yo,up,lo,mid,sec=struct.unpack('<hh8s8s8sH',D[i:i+30])
        m['sides'].append(dict(xoff=xo,yoff=yo,upper=nm8(up),lower=nm8(lo),mid=nm8(mid),sector=sec))
    m['verts']=[struct.unpack('<hh',L['VERTEXES'][i:i+4]) for i in range(0,len(L['VERTEXES']),4)]
    m['sectors']=[]
    D=L['SECTORS']
    for i in range(0,len(D),26):
        fh,ch,ft,ct,light,sp,tag=struct.unpack('<hh8s8shhh',D[i:i+26])
        m['sectors'].append(dict(floor=fh,ceil=ch,ftex=nm8(ft),ctex=nm8(ct),light=light,special=sp,tag=tag))
    m['segs']=[dict(zip(('v1','v2','angle','line','side','offset'),struct.unpack('<HHhHhh',L['SEGS'][i:i+12]))) for i in range(0,len(L['SEGS']),12)]
    m['ssectors']=[struct.unpack('<HH',L['SSECTORS'][i:i+4]) for i in range(0,len(L['SSECTORS']),4)]
    m['nodes']=[struct.unpack('<hhhhhhhhhhhhHH',L['NODES'][i:i+28]) for i in range(0,len(L['NODES']),28)]
    m['reject']=L.get('REJECT',b'')
    return m
