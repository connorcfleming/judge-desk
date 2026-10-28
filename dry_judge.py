"""Sample current leads through risk+judge WITHOUT gating/trading (logged to logs/judge_dryrun.jsonl)."""
import json
from common import *;from search import search;from risk import risk;from whale import whale;from judge_rules_dryrun import dossier,judge
cfg=load("config.json");leads,_=search(cfg)
for L in leads:
    rk=risk(L);d=dossier(L,rk,{"result":"quiet"},10);a=judge(d);log("judge_dryrun",{"lead_id":L["lead_id"],"dossier":d,"answers":a})
    print(L["symbol"],rk["result"],"1h%",d["price_change_1h_pct"],"bs_h1",d["buys_sells_h1"],"top10",d["top10_pct"],"liq",round(d["liquidity_usd"]),json.dumps(a))
