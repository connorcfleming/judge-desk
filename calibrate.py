"""Sunday calibration. python3 calibrate.py [days=7]
Buy verdicts (Jev action=buy) bucketed by p: 0.70-0.79, 0.80-0.89, 0.90+ with trades and greens per bucket,
plus how many passes would have been green after 24h (logs/death_check.jsonl green_24h)."""
import sys,json,time
from common import P,load
days=int(sys.argv[1]) if len(sys.argv)>1 else 7;cut=time.time()-days*86400
def rows(n):
    try:return [json.loads(x) for x in open(P(f"logs/{n}.jsonl")) if x.strip()]
    except FileNotFoundError:return []
def ts(r):
    try:return time.mktime(time.strptime(r["ts"][:19],"%Y-%m-%dT%H:%M:%S"))
    except Exception:return 0
st=load("state.json");pos={p["lead_id"]:p for p in st.get("closed",[])+st.get("open_positions",[])}
B={"0.70-0.79":[0,0,0],"0.80-0.89":[0,0,0],"0.90+":[0,0,0]}  # verdicts, trades, greens
below=0
for r in rows("judge"):
    if ts(r)<cut:continue
    a=(r.get("answers") or {}).get("action") or {}
    if a.get("option")!="buy":continue
    p=a.get("p",0)
    if p<0.70:below+=1;continue
    k="0.90+" if p>=0.9 else "0.80-0.89" if p>=0.8 else "0.70-0.79";B[k][0]+=1
    q=pos.get(r["lead_id"])
    if q:
        B[k][1]+=1
        if q in st.get("closed",[]) and q.get("realized",0)>q.get("cost",0):B[k][2]+=1
print(f"CALIBRATION last {days}d")
for k,(v,t,g) in B.items():print(f"buy p {k}: verdicts {v}, trades {t}, greens {g} (closed green)")
print(f"buy verdicts p<0.70 (gated out): {below}")
dc=[r for r in rows("death_check") if ts(r)>=cut];gr=sum(1 for r in dc if r.get("green_24h"));known=sum(1 for r in dc if r.get("green_24h") is not None)
print(f"passes checked at 24h {len(dc)}: would have been green {gr} of {known} with price data; dead {sum(1 for r in dc if r.get('dead'))}")
