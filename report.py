"""Evening report (9 PM ET). python3 report.py [YYYY-MM-DD]  -> prints the DESK block from logs + state."""
import sys,json,time,collections
from common import P,load
day=sys.argv[1] if len(sys.argv)>1 else time.strftime("%F")
def rows(n):
    try:return [json.loads(x) for x in open(P(f"logs/{n}.jsonl")) if x.strip()]
    except FileNotFoundError:return []
T=lambda r:r.get("ts","")[:10]==day
leads={r.get("mint") or r["lead_id"] for r in rows("leads") if T(r) and r.get("qualified")}   # unique mints
risk=[r for r in rows("risk") if T(r)];dead={r["lead_id"].split("-")[0] for r in risk if r["result"]=="dead"}   # unique mints (prefix)
conf={r["lead_id"].split("-")[0] for r in rows("whale") if T(r) and r.get("result")=="confirm"}
J={}
for r in rows("judge"):
    if T(r) and "answers" in r:J[r["lead_id"]]=r["answers"]["action"]["option"]
jc=collections.Counter(J.values())
G={}
for r in rows("gate"):
    if T(r) and r.get("decision") in("buy","watch","pass"):G[r["lead_id"]]=r
passed_clean={l for l,r in G.items() if r["decision"]=="pass"}   # only RISK-clean leads reach the gate
dc=[r for r in rows("death_check") if T(r)];died=sum(1 for r in dc if r.get("dead"))
tr=rows("trades");buys=[r for r in tr if T(r) and r.get("event") in("PAPER_BUY","LIVE_BUY")]
sells=[r for r in tr if T(r) and r.get("event") in("PAPER_SELL","LIVE_SELL")]
st=load("state.json")
W=L=0
for p in st.get("closed",[]):
    ct=p.get("closed_ts");lt=[r["ts"][:10] for r in tr if r.get("lead_id")==p["lead_id"] and r.get("event") in("PAPER_SELL","LIVE_SELL")]
    cd=time.strftime("%F",time.localtime(ct)) if ct else (lt[-1] if lt else None)
    if cd==day:
        if p.get("realized",0)>p.get("cost",0):W+=1
        else:L+=1
pbuy=sum(r.get("cost",0) for r in buys if r["event"]=="PAPER_BUY");psell=sum(r.get("usd",0) for r in sells if r["event"]=="PAPER_SELL")
bank_end=st["bank"];bank_start=bank_end-psell+pbuy
openv=sum(p.get("cost",0) for p in st["open_positions"] if not p.get("live"))
live=[r for r in rows("live") if T(r)]
print(f"DESK {day}")
print(f"leads found {len(leads)} unique mints, killed by RISK {len(dead)}, confirmed by WHALE {len(conf)}")
print(f"JUDGE buy {jc.get('buy',0)}, watch {jc.get('watch',0)}, pass {jc.get('pass',0)}")
print(f"passed but RISK-clean {len(passed_clean)}, dead within 24h {died} (of {len(dc)} 24h checks due today)")
print(f"trades executed {len(buys)} (paper {sum(1 for b in buys if b['event']=='PAPER_BUY')}, live {sum(1 for b in buys if b['event']=='LIVE_BUY')}) W/L {W}/{L}")
print(f"bank {bank_start:.2f} to {bank_end:.2f} (paper cash; +{openv:.2f} open paper at cost, {len(st['open_positions'])} open)")
if live:print(f"live events today {len(live)}: "+", ".join(sorted({r.get('event') or r.get('tag','?') for r in live})))
print("one thing that worked: <fill from the above>")
print("one thing to change: <fill from the above>")
