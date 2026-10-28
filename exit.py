import time
from common import *
def _px(mint):
    p=pairs_for(mint);return float(p[0]["priceUsd"]) if p and p[0].get("priceUsd") else None
def manage(state,cfg,price_fn=None):
    e=cfg["exits"];price_fn=price_fn or _px
    for pos in list(state["open_positions"]):
        px=price_fn(pos["mint"])
        if not px:continue
        pos["peak"]=max(pos["peak"],px);g=100*(px/pos["entry"]-1)
        def sell(q,why):
            """returns True only if the sell happened (paper always; live only if swap ok). qty untouched on failure."""
            q=min(q,pos["qty"]);v=q*px
            if q<=0:return False
            if pos.get("live"):
                if cfg.get("live_enabled") is not True:
                    log("trades",{"event":"LIVE_SELL_SKIPPED_LIVE_DISABLED","why":why,"lead_id":pos["lead_id"]});return False
                import live_exec as L
                raw=int(pos["raw_units"]*q/pos["qty0"]) if q<pos["qty"] else int(pos["raw_units"]*pos["qty"]/pos["qty0"])
                r=L.swap(pos["mint"],L.SOL,raw,send=True,tag=f"LIVE_SELL {why} "+pos["lead_id"])
                log("trades",{"event":"LIVE_SELL_ATTEMPT","why":why,"lead_id":pos["lead_id"],**r})
                log("live",{"event":"LIVE_CLOSE" if q>=pos["qty"] else "LIVE_PARTIAL_CLOSE","why":why,"symbol":pos["symbol"],"mint":pos["mint"],"ok":r.get("ok"),"sig":r.get("sig"),"solscan":r.get("solscan"),"err":r.get("err") or r.get("why"),"est_usd":v})
                if not r.get("ok"):return False
            pos["qty"]-=q;pos["realized"]=pos.get("realized",0)+v
            if not pos.get("live"):state["bank"]+=v
            if why in("hard_stop","trailing_stop"):state.setdefault("cooldown",{})[pos["mint"]]=time.time()
            log("trades",{"event":"LIVE_SELL" if pos.get("live") else "PAPER_SELL","observed_price_fill":True,"why":why,"lead_id":pos["lead_id"],"mint":pos["mint"],"price":px,"qty":q,"usd":v,"qty_left":pos["qty"]})
            return True
        if g<=e["hard_stop_pct"]:sell(pos["qty"],"hard_stop")
        else:
            q0=pos.get("qty0") or pos["qty"]
            # stage only advances when the sell actually filled (a failed live sell is retried next tick)
            if pos["stage"]==0 and g>=e["take_half_at_pct"]:
                if sell(q0/2,"half_at_+50"):pos["stage"]=1
            for i,l in enumerate(e["ladder_rest"]):
                if pos["stage"]==i+1 and g>=l["at_pct"]:
                    q=q0*l["sell_frac_of_orig"] if "sell_frac_of_orig" in l else pos["qty"]*l["sell_frac_of_rest"]
                    if sell(q,f"ladder_{l['at_pct']}"):pos["stage"]+=1
                    else:break
            pg=100*(pos["peak"]/pos["entry"]-1);tr=e["trail_from_peak_pct"]
            for t in e.get("trail_tiers",[]):
                if pg>=t["peak_gain_pct"]:tr=t["trail_pct"]
            armed=pos["stage"]>=1 or pg>=e.get("trail_arm_pct",e["take_half_at_pct"])
            if armed and pos["qty"]>0 and px<=pos["peak"]*(1-tr/100):sell(pos["qty"],"trailing_stop")
        if pos["qty"]<=1e-12:
            pos["closed_ts"]=time.time();state["open_positions"].remove(pos);state["closed"].append(pos)
