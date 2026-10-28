from common import *
def risk(lead):
    checks={};fails=[]
    try:r=get(f"https://api.rugcheck.xyz/v1/tokens/{lead['mint']}/report");src("rugcheck_report",True)
    except Exception as e:
        src("rugcheck_report",False,str(e)[:80]);out={"lead_id":lead["lead_id"],"result":"dead","fails":["rugcheck_unavailable"],"checks":{}};log("risk",out);return out
    checks["mint_authority"]=r.get("mintAuthority");checks["freeze_authority"]=r.get("freezeAuthority")
    if r.get("mintAuthority"):fails.append("mint_authority_live")
    if r.get("freezeAuthority"):fails.append("freeze_authority_live")
    lp=[m.get("lp",{}).get("lpLockedPct") for m in (r.get("markets") or []) if m.get("lp")]
    lpv=max([x for x in lp if x is not None],default=None);checks["lp_locked_or_burned_pct"]=lpv
    names=" ".join((x.get("name","")+" "+x.get("description","")).lower() for x in r.get("risks") or [])
    pump="pump" in str([m.get("marketType") for m in r.get("markets") or []]).lower()
    checks["pump_amm_or_curve"]=pump
    if (lpv is None or lpv<90) and not pump:fails.append("lp_not_locked")
    pool=set()
    for m in r.get("markets") or []:
        for k in ("pubkey","liquidityA","liquidityB","liquidityAAccount","liquidityBAccount","mintLP"):
            v=m.get(k)
            if isinstance(v,str):pool.add(v)
        for sub in ("lp",):
            d=m.get(sub) or {}
            for k in ("lpMint","quoteMint","baseVault","quoteVault","owner"):
                v=d.get(k) if isinstance(d,dict) else None
                if isinstance(v,str):pool.add(v)
    pool|={"5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1","GpMZbSM2GgvTKHJirzeGfMFoaZ8UR2X7F4v8vHTvxFbL","39azUYFWPz3VHgKCf3VChUwbpURdCHRxjWVowf5jUJjg","1nc1nerator11111111111111111111111111111111"}
    th=[h for h in (r.get("topHolders") or []) if h.get("address") not in pool and h.get("owner") not in pool]
    checks["pool_holders_excluded"]=len(r.get("topHolders") or [])-len(th)
    top10=sum(h.get("pct",0) for h in th[:10]) if r.get("topHolders") else None
    checks["top10_pct"]=round(top10,2) if top10 is not None else "missing"
    if top10 is not None and top10>35:fails.append("top10_over_35pct")
    sup=(r.get("token") or {}).get("supply");cb=r.get("creatorBalance")
    dev=round(100*cb/sup,2) if sup and cb is not None else "missing";checks["dev_pct"]=dev
    if isinstance(dev,float) and dev>10:fails.append("dev_over_10pct")
    hp=any(k in names for k in ["honeypot","transfer fee","not sellable"]) or (r.get("transferFee") or {}).get("pct",0)>0
    checks["honeypot_or_fee"]=hp
    if hp:fails.append("honeypot_or_transfer_fee")
    bund=bool(r.get("graphInsidersDetected")) or "bundle" in names or "insider" in names
    checks["bundled_or_insiders"]=bund;checks["insiders_detected"]=r.get("graphInsidersDetected")
    if bund:fails.append("bundled_or_insider_buys")
    checks["rugged_flag"]=r.get("rugged")
    if r.get("rugged"):fails.append("rugged")
    checks["rugcheck_risks"]=[x.get("name") for x in r.get("risks") or []];checks["score_normalised"]=r.get("score_normalised")
    checks["holders_now"]=r.get("totalHolders")
    out={"lead_id":lead["lead_id"],"result":"dead" if fails else "clean","fails":fails,"checks":checks};log("risk",out);return out
