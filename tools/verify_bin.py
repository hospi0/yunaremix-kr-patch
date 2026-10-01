import sys,struct; sys.stdout.reconfigure(encoding='utf-8'); sys.path.insert(0,'tools'); import iso, build, rules, binx
fh=open(build.OUT,'rb'); T=iso.tree(fh); l,s,_,_=T['111.BIN']; nb=iso.read_user(fh,l,(s+2047)//2048)[:s]
ob=open('work/disc/111.BIN','rb').read(); found={o:(r,s) for o,r,s,t in binx.scan(ob)}
rev={}
for ln in open('work/trans/charmap.tsv',encoding='utf-8').read().split('\n')[1:]:
    if ln: ch,h=ln.split('\t'); rev[bytes.fromhex(h)]=ch
def dec(b):
    o='';i=0
    while i<len(b):
        if b[i]>=0x81: p=bytes(b[i:i+2]); o+=rev.get(p) or p.decode('cp932'); i+=2
        else: o+=chr(b[i]); i+=1
    return o
bad=n=0
for ln in open('work/trans/bin_ko.tsv',encoding='utf-8').read().split('\n')[1:]:
    if not ln.strip(): continue
    o,t=ln.split('\t'); o=int(o,16); t=rules.norm(t)
    for r in found[o][0]:
        p=struct.unpack_from('>I',nb,r)[0]-0x06004000; x=nb[p:nb.index(0,p)]; n+=1
        if dec(x)!=t: bad+=1; print('불일치',hex(o),dec(x),t)
print('111.BIN 포인터',n,'불일치',bad)
