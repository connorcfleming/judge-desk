import json,time,os,urllib.request
D=os.path.dirname(os.path.abspath(__file__))
def P(f):return os.path.join(D,f)
def load(f):return json.load(open(P(f)))
def save(f,o):
    # atomic write (tmp + rename) so a crash/kill mid-write can't corrupt state.json
    t=P(f)+".tmp%d"%os.getpid();json.dump(o,open(t,"w"),indent=1);os.replace(t,P(f))
def get(url):
    r=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=20).read())
def log(name,rec):
    rec={"ts":time.strftime("%Y-%m-%dT%H:%M:%S%z"),**rec}
    open(P(f"logs/{name}.jsonl"),"a").write(json.dumps(rec)+"\n")
SRC={}
def src(name,ok,err=None):SRC[name]={"ok":ok,"err":err}
def pairs_for(mint):
    try:
        d=get(f"https://api.dexscreener.com/token-pairs/v1/solana/{mint}");src("dexscreener_pairs",True)
        return sorted(d,key=lambda p:(p.get("liquidity") or {}).get("usd",0),reverse=True)
    except Exception as e:src("dexscreener_pairs",False,str(e));return []
import fcntl
class Lock:
    def __enter__(self):self.f=open(P("state.lock"),"w");fcntl.flock(self.f,fcntl.LOCK_EX);return self
    def __exit__(self,*a):fcntl.flock(self.f,fcntl.LOCK_UN);self.f.close()
COOLDOWN_S=86400
