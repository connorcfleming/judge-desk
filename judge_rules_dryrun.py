"""Judge. No LLM API key found on the box -> DETERMINISTIC RULE-BASED judge from dossier only."""
from common import *
JUDGE_KIND="rule-based DRY-RUN ONLY (never used for decisions)"
QUESTIONS={"organic":"Is the move organic - holders growing from many independent buyers, not one wallet walking price up? yes/no",
 "late":"Is it late - has most of the move already happened before reaching the desk? yes/no",
 "exit_risk":"Exit risk 1-5 (1 = deep liquidity, 5 = our size is a big part of the pool)?",
 "action":"Action: buy / watch / pass?"}
M="missing"
def _wh(wh):
    """WHALE result + which tracked wallets bought and when (facts only)"""
    if not isinstance(wh,dict):return {"result":M}
    out={"result":wh.get("result",M)}
    hits=wh.get("hits")
    out["wallets"]=[{"label":h.get("label"),"address":h.get("address"),"via":h.get("via"),"last_activity_min_ago":h.get("min_ago",M)} for h in hits] if hits else []
    if wh.get("reason"):out["note"]=wh["reason"]
    return out
def dossier(lead,rk,wh,size):
    import snapshots as S
    p=lead["pair_data"];tx=p.get("txns",{});c=rk.get("checks",{});mint=lead.get("mint")
    hn=c.get("holders_now");h1=S.nearest(mint,3600,15*60,"holders") if mint else None
    pm5=S.nearest(mint,300,120,"m5") if mint else None
    age=lead["onchain_reason"].get("age_h")
    return {"lead_id":lead["lead_id"],"chain":"solana","age_h":age if age is not None else M,
     "mcap":p.get("marketCap") or p.get("fdv") or M,"liquidity_usd":(p.get("liquidity") or {}).get("usd",M),
     "holders_now":hn if hn is not None else M,"holders_1h_ago":h1 if h1 is not None else M,
     "price_change_1h_pct":(p.get("priceChange") or {}).get("h1",M),
     "buys_sells_m5":[tx.get("m5",{}).get("buys",M),tx.get("m5",{}).get("sells",M)],"buys_sells_prev_m5":pm5 if pm5 is not None else M,
     "buys_sells_h1":[tx.get("h1",{}).get("buys",M),tx.get("h1",{}).get("sells",M)],
     "top10_pct":c.get("top10_pct",M),"dev_pct":c.get("dev_pct",M),
     "risk":{"result":rk["result"],"checks":c},"whale":_wh(wh),
     "social_mentions_hr_now":M,"social_mentions_hr_1h_ago":M,"our_size_usd":size if size is not None else M}
from judge_core import judge
