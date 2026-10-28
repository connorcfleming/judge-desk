import time
from common import *
# ---- fresh pump.fun graduations (added) ----
import json as _json,os as _os
_GC=P("logs/grad_cache.json")
def _gc_load():
    try:return _json.load(open(_GC))
    except Exception:return {"cool":{},"resp":{}}
def _gc_save(c):
    try:_json.dump(c,open(_GC,"w"))
    except Exception:pass
def _polite_get(name,url,ttl=60,cool=300,cap=1800,stale=True):
    """cached GET with cooldown after 429/403/errors; returns None on failure (fail-safe)"""
    c=_gc_load();t=time.time()
    r=c["resp"].get(url)
    if r and t-r["t"]<ttl:return r["d"]
    if c["cool"].get(name,0)>t:src(name,False,"cooldown");return r["d"] if stale and r and t-r["t"]<900 else None
    try:
        d=get(url);c["resp"][url]={"t":t,"d":d};src(name,True)
        c["cool"].pop(name,None);c["cool"].pop(name+"_n",None);_gc_save(c);return d
    except Exception as e:
        code=getattr(e,"code",None)
        prev=c["cool"].get(name+"_n",0)+1;c["cool"][name+"_n"]=prev
        c["cool"][name]=t+min(cool*(2**(prev-1)),cap) if code in (429,403) else t+60
        _gc_save(c);src(name,False,str(e)[:80]);return None
def grad_mints():
    """mints that recently graduated: pump.fun complete=true by last trade + DexScreener pumpswap search"""
    out={}
    try:   # PumpPortal websocket collector (grad_collector.py), last FRESH_H hours
        for m,ts in _json.load(open(P("logs/grad_ws.json"))).items():
            if time.time()-ts<FRESH_H*3600:out.setdefault(m,set()).add("pumpportal_migration")
    except Exception:pass
    fresh_n=len(out)
    d=_polite_get("pumpfun_grad","https://frontend-api-v3.pump.fun/coins?limit=50&sort=last_trade_timestamp&order=DESC&complete=true",cap=600,stale=False)
    if d is None and not fresh_n:   # stale (<=900s) cache only when nothing fresh exists
        r=_gc_load()["resp"].get("https://frontend-api-v3.pump.fun/coins?limit=50&sort=last_trade_timestamp&order=DESC&complete=true")
        d=r["d"] if r and time.time()-r["t"]<900 else None
    for x in d if isinstance(d,list) else []:
        if x.get("complete") and x.get("mint"):out.setdefault(x["mint"],set()).add("pumpfun_grad")
    for q in ("pumpswap","pump"):
        d=_polite_get("ds_search_"+q,"https://api.dexscreener.com/latest/dex/search?q="+q)
        for p in (d or {}).get("pairs") or [] if isinstance(d,dict) else []:
            if p.get("chainId")=="solana" and p.get("dexId") in ("pumpswap","raydium"):
                m=(p.get("baseToken") or {}).get("address")
                if m:out.setdefault(m,set()).add("ds_pumpswap_search")
    return out
FRESH_H=2.0
def search(cfg):
    c=cfg["search"];mints={}
    for name,url in [("ds_profiles","https://api.dexscreener.com/token-profiles/latest/v1"),
                     ("ds_boosts_latest","https://api.dexscreener.com/token-boosts/latest/v1"),
                     ("ds_boosts_top","https://api.dexscreener.com/token-boosts/top/v1"),
                     ("rugcheck_new","https://api.rugcheck.xyz/v1/stats/new_tokens"),
                     ("rugcheck_trending","https://api.rugcheck.xyz/v1/stats/trending"),
                     ("pumpfun","https://frontend-api-v3.pump.fun/coins?limit=50&sort=created_timestamp&order=DESC")]:
        try:
            d=get(url);src(name,True)
            for t in d if isinstance(d,list) else []:
                if t.get("chainId","solana")!="solana":continue
                m=t.get("tokenAddress") or t.get("mint")
                if m:mints.setdefault(m,set()).add(name)
        except Exception as e:src(name,False,str(e)[:80])
    try:
        for m,ss in grad_mints().items():mints.setdefault(m,set()).update(ss)
    except Exception as e:src("grad",False,str(e)[:80])
    leads=[];now=time.time()*1000
    ml=list(mints)
    for i in range(0,len(ml),30):
        try:ps=get("https://api.dexscreener.com/tokens/v1/solana/"+",".join(ml[i:i+30]));src("ds_tokens",True)
        except Exception as e:src("ds_tokens",False,str(e)[:80]);continue
        best={};grad={}
        for p in ps:
            m=p["baseToken"]["address"]
            if m in mints and (p.get("liquidity") or {}).get("usd",0)>(best.get(m,{}).get("liquidity") or {}).get("usd",-1):best[m]=p
            if m in mints and p.get("dexId") in ("pumpswap","raydium") and p.get("pairCreatedAt") and (now-p["pairCreatedAt"])/3.6e6<FRESH_H:
                if m not in grad or p["pairCreatedAt"]>grad[m]["pairCreatedAt"]:grad[m]=p
        for m,p in best.items():
            age=(now-p["pairCreatedAt"])/3.6e6 if p.get("pairCreatedAt") else None
            liq=(p.get("liquidity") or {}).get("usd",0);vol=(p.get("volume") or {}).get("h1",0)
            tx=(p.get("txns") or {}).get("h1",{});n=tx.get("buys",0)+tx.get("sells",0)
            fresh=m in grad
            if fresh:
                p=grad[m];age=(now-p["pairCreatedAt"])/3.6e6
                liq=(p.get("liquidity") or {}).get("usd",0);vol=(p.get("volume") or {}).get("h1",0)
                tx=(p.get("txns") or {}).get("h1",{});n=tx.get("buys",0)+tx.get("sells",0)
            # age-scaled floors for pairs <60 min old: per-minute rate of the h1 floor, min 10 min window
            f=min(1.0,max(age*60,10)/60) if age is not None else 1.0
            reason={"age_h":round(age,2) if age is not None else None,"liq_usd":liq,"vol_h1":vol,"txns_h1":n,"sources":sorted(mints[m])}
            if fresh:reason.update({"fresh_graduation":True,"grad_dex":p.get("dexId"),"grad_age_min":round(age*60,1),"floor_scale":round(f,2)})
            # pump.fun bonding-curve coins show liq=0 on DexScreener: use curve market cap instead (RugCheck still decides risk)
            curve=p.get("dexId")=="pumpfun" and not liq
            if curve:reason.update({"bonding_curve":True,"mcap_usd":p.get("marketCap") or p.get("fdv") or 0})
            liq_ok=(reason.get("mcap_usd",0)>=c.get("min_curve_mcap_usd",c["min_liq_usd"])) if curve else liq>=c["min_liq_usd"]
            ok=age is not None and age<=c["max_age_h"] and liq_ok and vol>=c["min_vol_h1"]*f and n>=c["min_txns_h1"]*f
            rec={"lead_id":f"{m[:8]}-{int(now/1000)}","mint":m,"symbol":p["baseToken"].get("symbol"),"pair":p["pairAddress"],"onchain_reason":reason,"qualified":ok}
            log("leads",rec)
            if ok:rec["pair_data"]=p;leads.append(rec)
    leads.sort(key=lambda l:(not l["onchain_reason"].get("fresh_graduation"),-l["onchain_reason"]["vol_h1"]))
    return leads[:c["max_leads"]],len(mints)
def lead_for_mint(mint,sources=("watch_recheck",)):
    """build a lead for a specific mint (used to re-ask due watch leads that search didn't surface again)"""
    ps=pairs_for(mint)
    if not ps:return None
    p=ps[0];now=time.time()*1000;age=(now-p["pairCreatedAt"])/3.6e6 if p.get("pairCreatedAt") else None
    tx=(p.get("txns") or {}).get("h1",{})
    reason={"age_h":round(age,2) if age is not None else None,"liq_usd":(p.get("liquidity") or {}).get("usd",0),"vol_h1":(p.get("volume") or {}).get("h1",0),"txns_h1":tx.get("buys",0)+tx.get("sells",0),"sources":list(sources)}
    rec={"lead_id":f"{mint[:8]}-{int(now/1000)}","mint":mint,"symbol":p["baseToken"].get("symbol"),"pair":p["pairAddress"],"onchain_reason":reason,"qualified":True}
    log("leads",rec);rec["pair_data"]=p;return rec
