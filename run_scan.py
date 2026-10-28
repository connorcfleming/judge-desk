"""Two-phase scan. See README_JEV.md.
  python3 run_scan.py phase1  -> exits/death-check, search, risk, whale, writes pending/jev_requests.json
  (routine calls JEV_EVALUATE_STATE per request, writes pending/jev_responses.json)
  python3 run_scan.py phase2  -> maps Jev answers, gate, sniper; Jev missing/failed => pass"""
import sys,time,json,os
from common import *
from search import search,lead_for_mint;from risk import risk;from whale import whale;from judge_rules_dryrun import dossier,judge as rule_judge
from gate import gate;import sniper,exit as ex,jev,snapshots
REQ=P("pending/jev_requests.json");RES=P("pending/jev_responses.json")
WATCH_GRACE_S=120      # scans run every 15 min and phase2 stamps the watch time a little after phase1; without grace the 30-min re-ask slips to 45 min
WATCH_STALE_S=3*3600   # watch that could not be re-asked for 3h -> pass (logged)
PASS_NO_REASK_S=86400  # a passed mint is not re-asked for 24h ("never re-ask for a different answer"); it is in death_watch
def _price(p):
    try:return float(p[0]["priceUsd"]) if p and p[0].get("priceUsd") else None
    except Exception:return None
def death_check(st,now=None):
    now=now or time.time()
    for m,w in list(st["death_watch"].items()):
        if now-w["t"]>=86400:
            p=pairs_for(m)
            if not SRC.get("dexscreener_pairs",{}).get("ok"):
                if now-w["t"]<86400*2:continue          # API error: retry next scan, don't call it dead
                p=[]
            liq=(p[0].get("liquidity") or {}).get("usd",0) if p else 0;px=_price(p);px0=w.get("price")
            chg=round(100*(px/px0-1),2) if px and px0 else None
            log("death_check",{"mint":m,"lead_id":w.get("lead_id"),"symbol":w.get("symbol"),"passed_ts":w["t"],"liq_then":w["liq"],"liq_now":liq,
                "price_then":px0,"price_now":px,"chg_24h_pct":chg,"green_24h":(chg>0) if chg is not None else None,
                "dead":liq<0.2*(w["liq"] if isinstance(w["liq"],(int,float)) and w["liq"] else 1),"no_pairs":not p})
            del st["death_watch"][m]
def live_size_est(st,cfg):
    """size estimate for the dossier (exit_risk question). LIVE: 10% of last measured total portfolio; else paper size."""
    if cfg.get("live_enabled") is True and st.get("live_last_total_usd"):return round(st["live_last_total_usd"]*cfg.get("live_trade_pct",0.10),2)
    if cfg.get("live_enabled") is True:
        try:
            from wallet import keypair,sol_balance
            bal=sol_balance(str(keypair().pubkey()))
            sp=get("https://api.dexscreener.com/tokens/v1/solana/So11111111111111111111111111111111111111112")
            solusd=float(sorted(sp,key=lambda p:(p.get("liquidity") or {}).get("usd",0))[-1]["priceUsd"])
            return round(bal*solusd*cfg.get("live_trade_pct",0.10),2)   # open live positions not added here (estimate only)
        except Exception:pass
    return round(min(cfg["trade_max_usd"],st["bank"]*cfg["trade_pct"]),2)
def phase1():
    with Lock():
        cfg=load("config.json");st=load("state.json");ex.manage(st,cfg);death_check(st)
        save("state.json",st)
    leads,raw=search(cfg);held={p["mint"] for p in st["open_positions"]};reqs=[];kills=conf=skip=0;now=time.time()
    inl={L["mint"] for L in leads};due=0
    for k,w in list(st["watch"].items()):        # due watch leads search did not surface again -> re-ask anyway
        m=w.get("mint")
        if m and m not in inl and m not in held and now-w["t"]>=cfg["gate"]["watch_recheck_min"]*60-WATCH_GRACE_S:
            L=lead_for_mint(m)
            if L:leads.append(L);inl.add(m);due+=1
    size=live_size_est(st,cfg)
    for L in leads:
        k=L["mint"][:8]
        try:snapshots.record(L["mint"],pair=L["pair_data"])
        except Exception:pass
        if L["mint"] in held:skip+=1;log("gate",{"lead_id":L["lead_id"],"decision":"skip","killed_by":"already_held_no_rejudge"});continue
        if k in st["watch"] and now-st["watch"][k]["t"]<cfg["gate"]["watch_recheck_min"]*60-WATCH_GRACE_S:skip+=1;continue
        dw=st["death_watch"].get(L["mint"])
        if dw and now-dw["t"]<PASS_NO_REASK_S and k not in st["watch"]:skip+=1;continue
        rk=risk(L)
        try:snapshots.record(L["mint"],holders=rk.get("checks",{}).get("holders_now"))
        except Exception:pass
        if rk["result"]=="dead":kills+=1;continue
        wh=whale(L,rk);conf+=wh["result"]=="confirm"
        d=dossier(L,rk,wh,size)
        try:
            import birdeye;d=birdeye.apply(d,L["mint"])
        except Exception:pass
        log("judge_dryrun",{"lead_id":L["lead_id"],"rule_answers":rule_judge(d),"note":"comparison only"})
        if not jev.can_call(sum(1 for r in reqs if r["call"])):log("judge",{"lead_id":L["lead_id"],"judge":"jev","error":"daily_cap_reached"});d["_budget_blocked"]=True
        call=None
        if not d.get("_budget_blocked"):call=jev.call_args({k2:v for k2,v in d.items() if not k2.startswith("_")})
        reqs.append({"lead_id":L["lead_id"],"mint":L["mint"],"symbol":L["symbol"],"price_usd":_price([L["pair_data"]]),"call":call,"dossier":d})
    json.dump(reqs,open(REQ+".tmp","w"),indent=1);os.replace(REQ+".tmp",REQ)
    if os.path.exists(RES):os.remove(RES)
    print(json.dumps({"phase":1,"raw":raw,"leads":len(leads),"watch_rechecks_added":due,"skipped_held_watch_or_passed":skip,"risk_kills":kills,"whale_confirms":conf,"jev_requests":sum(1 for r in reqs if r["call"]),"budget_blocked":sum(1 for r in reqs if not r["call"]),"requests_file":REQ,"spend_today":jev.spend(),"sources":SRC}))
def phase2():
    reqs=json.load(open(REQ));res=json.load(open(RES)) if os.path.exists(RES) else {}
    T={"buy":0,"watch":0,"pass":0};trades=[]
    with Lock():
        cfg=load("config.json");st=load("state.json");now=time.time()
        for r in reqs:
            lid=r["lead_id"];raw=res.get(lid);a=None
            if raw and isinstance(raw,dict) and raw.get("answers"):
                jev.record(int((raw.get("usage") or {}).get("input_tokens",jev.EST_TOKENS)));a=jev.map_answers(raw)
            if a is None:a={"error":"jev_failed_or_missing" if r.get("call") else "jev_budget_blocked","action":{"option":"pass","p":1.0}}
            log("judge",{"lead_id":lid,"mint":r["mint"],"symbol":r.get("symbol"),"price_usd":r.get("price_usd"),"judge":"jev","model":(raw or {}).get("model") if isinstance(raw,dict) else None,"dossier":r["dossier"],"raw_response":raw,"answers":a})
            T[a["action"]["option"]]=T.get(a["action"]["option"],0)+1
            dec=gate(lid,a,cfg,st) if "error" not in a else (log("gate",{"lead_id":lid,"decision":"pass","killed_by":["judge_failure",a["error"]]}) or "pass")
            k=r["mint"][:8];cd=st.get("cooldown",{}).get(r["mint"])
            if dec=="buy" and cd and time.time()-cd<COOLDOWN_S:
                log("gate",{"lead_id":lid,"decision":"pass","killed_by":["cooldown_after_stop",round((COOLDOWN_S-(time.time()-cd))/3600,1),"h_left"]});dec="pass"
            if dec=="buy":
                st["watch"].pop(k,None)
                if any(p["mint"]==r["mint"] for p in st["open_positions"]):log("gate",{"lead_id":lid,"decision":"skip","killed_by":"already_held"});continue
                try:ok=sniper.buy({"lead_id":lid,"mint":r["mint"],"symbol":r["symbol"]},st,cfg)
                except Exception as e:ok=False;log("trades",{"lead_id":lid,"event":"buy_exception","err":type(e).__name__+": "+str(e)[:120]})
                if ok:trades.append(r["symbol"])
            elif dec=="watch":st["watch"][k]={"t":now,"asked":st["watch"].get(k,{}).get("asked",0)+1,"mint":r["mint"],"lead_id":lid}
            else:
                st["watch"].pop(k,None)
                st["death_watch"][r["mint"]]={"t":now,"liq":r["dossier"]["liquidity_usd"],"price":r.get("price_usd"),"lead_id":lid,"symbol":r.get("symbol")}
        for k,w in list(st["watch"].items()):        # watch that could never be re-asked -> pass, logged
            if now-w["t"]>WATCH_STALE_S:
                log("gate",{"lead_id":w.get("lead_id",k),"decision":"pass","killed_by":["watch_not_reasked_3h"]});del st["watch"][k]
                if w.get("mint"):st["death_watch"].setdefault(w["mint"],{"t":now,"liq":None,"price":None,"lead_id":w.get("lead_id"),"symbol":None})
        save("state.json",st)
    os.rename(REQ,REQ+".done");os.path.exists(RES) and os.rename(RES,RES+".done")
    print(json.dumps({"phase":2,"judge":T,"trades":trades,"bank":round(st["bank"],2),"open":len(st["open_positions"]),"spend_today":jev.spend()}))
if __name__=="__main__":{"phase1":phase1,"phase2":phase2}[sys.argv[1] if len(sys.argv)>1 else "phase1"]()
