#!/usr/bin/env python3
"""Read-only: print a compact JSON summary of the desk right now (no secrets).
  python3 export_snapshot.py [--dir .] [--out file.json] [--no-price]"""
import argparse,json,os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import deskdata
ap=argparse.ArgumentParser();ap.add_argument("--dir",default=".");ap.add_argument("--out");ap.add_argument("--no-price",action="store_true");a=ap.parse_args()
s=deskdata.snapshot(a.dir,live_price=not a.no_price)
jt={}
for j in s["judge"]:jt.setdefault(j.get("symbol"),j)
try:
    w=json.load(open(os.path.join(a.dir,"wallets.json")));wc=len(w.get("wallets",w)) if isinstance(w,dict) else len(w)
except Exception:wc=None
out={"now":s["now"],"bank":s["bank"],"watch_n":s["watch_n"],"funnel_today":s["funnel"],
 "leads":[{k:x[k] for k in("ts","symbol","mint","age_h","liq","sources","qualified","risk","whale","gate","killed_by")}|
   {"judge":(lambda j:j and {"action":j["action"],"p":j["action_p"],"organic":j["organic"],"late":j["late"],"exit_risk":j["exit_risk"]})(jt.get(x["symbol"]))} for x in s["feed"][:30]],
 "open_positions":s["positions"],"recent_trades":s["trades"][:10],"whale_wallets_tracked":wc,
 "jev_spend":s["jev_spend"],"loops":s["loops"]}
txt=json.dumps(out,default=str,separators=(",",":"))
if a.out:open(a.out,"w").write(txt)
print(txt)
