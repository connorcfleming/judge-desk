"""Per-mint scan snapshots (logs/snapshots.json) so the dossier can carry holders 1h ago and the previous 5-min window.
DexScreener only gives a rolling m5 window, so the previous window exists only when we have a snapshot ~5 min older."""
import time,json,os
from common import P
F=P("logs/snapshots.json");KEEP_S=3*3600
def _load():
    try:return json.load(open(F))
    except Exception:return {}
import fcntl
def record(mint,holders=None,pair=None,t=None):
    with open(F+".lock","w") as lk:   # serialize with snapshot_collector.py / phase1 (no lost writes)
        fcntl.flock(lk,fcntl.LOCK_EX);_record(mint,holders,pair,t)
def _record(mint,holders,pair,t):
    s=_load();t=t or time.time();m5=((pair or {}).get("txns") or {}).get("m5") or {}
    rec={"t":t}
    if isinstance(holders,(int,float)):rec["holders"]=holders
    if "buys" in m5 and "sells" in m5:rec["m5"]=[m5["buys"],m5["sells"]]
    s.setdefault(mint,[]).append(rec)
    for k in list(s):
        s[k]=[x for x in s[k] if t-x["t"]<=KEEP_S]
        if not s[k]:del s[k]
    tmp=F+".tmp%d"%os.getpid();json.dump(s,open(tmp,"w"));os.replace(tmp,F)
def nearest(mint,ago_s,tol_s,field,now=None):
    """value of field from the snapshot closest to now-ago_s, within tol_s; None if none"""
    now=now or time.time();best=None
    for x in _load().get(mint,[]):
        if field not in x:continue
        d=abs((now-x["t"])-ago_s)
        if d<=tol_s and (best is None or d<best[0]):best=(d,x[field])
    return best[1] if best else None
