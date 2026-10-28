#!/usr/bin/env python3
"""Free snapshot sampler (read-only, never trades, no keys). Fills logs/snapshots.json between 15-min scans so the
dossier's holders_1h_ago (needs a sample 60+-15 min old) and buys_sells_prev_m5 (needs one 5+-2 min old) are present.
Every 4 min: DexScreener tokens/v1 batch (<=30 mints/call) -> m5 buys/sells. Every 12 min: RugCheck report -> totalHolders
(<=20 mints, 1.5 s apart). Mints = recent leads (<=24h old, seen in leads.jsonl last 3h, qualified first) + watch + open.
Restart: cd /workspace/judge-desk && nohup python3 snapshot_collector.py >> logs/snapshot_collector.out 2>&1 &"""
import os,sys,time,json
from common import P,get,load
import snapshots as S
PID=P("logs/snapshot_collector.pid");TICK=240;HOLD_EVERY=3;MAXM=30;MAXH=20
if os.path.exists(PID):
    try:os.kill(int(open(PID).read()),0);print("already running");sys.exit(0)
    except (OSError,ValueError):pass
open(PID,"w").write(str(os.getpid()))
def mints():
    now=time.time();sc={}
    try:
        with open(P("logs/leads.jsonl"),"rb") as f:
            f.seek(max(0,os.path.getsize(P("logs/leads.jsonl"))-400000));lines=f.read().decode(errors="ignore").splitlines()[1:]
        for l in lines:
            try:j=json.loads(l)
            except Exception:continue
            a=j.get("onchain_reason",{}).get("age_h")
            if a is None or a>24:continue
            t=time.mktime(time.strptime(j["ts"][:19],"%Y-%m-%dT%H:%M:%S"))
            if now-t>3*3600:continue
            sc[j["mint"]]=max(sc.get(j["mint"],0),t+(10**6 if j.get("qualified") else 0))
    except Exception as e:print("leads err",e,flush=True)
    try:
        st=load("state.json")
        for w in st.get("watch",{}).values():
            if w.get("mint"):sc[w["mint"]]=9e12
        for p in st.get("open_positions",[]):sc[p["mint"]]=9e12
    except Exception:pass
    return [m for m,_ in sorted(sc.items(),key=lambda x:-x[1])][:MAXM]
n=0
while True:
    try:
        ms=mints();got=0
        if ms:
            d=get("https://api.dexscreener.com/tokens/v1/solana/"+",".join(ms));best={}
            for p in d or []:
                m=(p.get("baseToken") or {}).get("address")
                if m in ms and (p.get("liquidity") or {}).get("usd",0)>=(best.get(m,{}).get("liquidity") or {}).get("usd",-1):best[m]=p
            for m,p in best.items():S.record(m,pair=p);got+=1
        h=0
        if n%HOLD_EVERY==0:
            for m in ms[:MAXH]:
                try:
                    r=get(f"https://api.rugcheck.xyz/v1/tokens/{m}/report");th=r.get("totalHolders")
                    if isinstance(th,int):S.record(m,holders=th);h+=1
                except Exception:pass
                time.sleep(1.5)
        print(time.strftime("%F %T"),"mints",len(ms),"m5",got,"holders",h,flush=True)
    except Exception as e:print(time.strftime("%F %T"),"error",type(e).__name__,str(e)[:100],flush=True)
    n+=1;time.sleep(TICK)
