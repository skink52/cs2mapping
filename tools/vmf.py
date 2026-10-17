import re
_tok=re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])|([^\s{}"]+)')
class Node:
    __slots__=('name','kv','ch')
    def __init__(s,name):s.name=name;s.kv=[];s.ch=[]
    def get(s,k,d=None):
        kl=k.lower()
        for a,b in s.kv:
            if a.lower()==kl:return b
        return d
    def set(s,k,v):
        kl=k.lower()
        for i,(a,b) in enumerate(s.kv):
            if a.lower()==kl:s.kv[i]=(a,v);return
        s.kv.append((k,v))
    def items(s):return list(s.kv)
def parse(text):
    root=Node('root');st=[root];pend=None;key=None
    for m in _tok.finditer(text):
        q,br,w=m.groups()
        if br=='{':
            n=Node(pend if pend is not None else key);st[-1].ch.append(n);st.append(n);pend=key=None
        elif br=='}':
            if key is not None:pend=None
            st.pop();key=None
        else:
            t=q if q is not None else w
            if key is None:key=t
            else:st[-1].kv.append((key,t));key=None
            pend=key
    return root
def dump(root):
    out=[]
    def w(n,d):
        ind='\t'*d
        out.append(f'{ind}{n.name}\n{ind}{{\n')
        for k,v in n.kv:out.append(f'{ind}\t"{k}" "{v}"\n')
        for c in n.ch:w(c,d+1)
        out.append(f'{ind}}}\n')
    for c in root.ch:w(c,0)
    return ''.join(out)
