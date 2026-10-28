import time
from common import *
def buy(lead,state,cfg):
    p=pairs_for(lead["mint"]);px=float(p[0]["priceUsd"]) if p and p[0].get("priceUsd") else None
    if not px:log("trades",{"lead_id":lead["lead_id"],"event":"buy_failed_no_price"});return False
    size=min(cfg["trade_max_usd"],state["bank"]*cfg["trade_pct"])
    if cfg.get("live_enabled") is True:
        import live_exec as L
        from wallet import keypair,sol_balance
        solpx=px_sol=float(p[0].get("priceUsd"))/float(p[0].get("priceNative") or 1) if p[0].get("quoteToken",{}).get("symbol")=="SOL" else None
        if not solpx:log("trades",{"lead_id":lead["lead_id"],"event":"LIVE_buy_abort_no_sol_price"});return False
        try:bal=sol_balance(str(keypair().pubkey()))
        except Exception as ex:log("trades",{"lead_id":lead["lead_id"],"event":"LIVE_buy_abort_balance_error","err":type(ex).__name__});return False
        lv=0.0
        for lp in state["open_positions"]:
            if lp.get("live") and lp.get("qty",0)>0:
                pp=pairs_for(lp["mint"]);lpx=float(pp[0]["priceUsd"]) if pp and pp[0].get("priceUsd") else lp["entry"]
                lv+=lp["qty"]*lpx
        total=bal*solpx+lv
        size=total*cfg.get("live_trade_pct",0.10)  # flat 10% of total live portfolio, no $ cap
        state["live_last_total_usd"]=total
        log("live",{"event":"LIVE_SIZING","lead_id":lead["lead_id"],"sol_bal":round(bal,4),"sol_px":round(solpx,2),"sol_usd":round(bal*solpx,2),"open_live_usd":round(lv,2),"total_usd":round(total,2),"size_usd":round(size,2)})
        tot=state.get("live_total_buys_usd",0)
        cap=cfg.get("live_max_total_buys_usd")
        if cap is not None and tot+size>cap:log("live",{"event":"LIVE_BUY_BLOCKED_100_CAP","lead_id":lead["lead_id"],"total":tot});return False
        r=L.swap(L.SOL,lead["mint"],int(size/solpx*1e9),send=True,tag="LIVE_BUY "+lead["lead_id"])
        if not r.get("ok"):log("trades",{"lead_id":lead["lead_id"],"event":"LIVE_buy_failed",**r});return False
        pos={"lead_id":lead["lead_id"],"mint":lead["mint"],"symbol":lead["symbol"],"live":True,"entry":px,"cost":size,"qty":size/px,"qty0":size/px,"raw_units":int(r["quote_out"]),"peak":px,"stage":0,"realized":0,"opened":time.time(),"sig":r["sig"]}
        state["live_total_buys_usd"]=state.get("live_total_buys_usd",0)+size;state.setdefault("live_positions",[]).append(pos);log("live",{"event":"LIVE_OPEN","symbol":pos["symbol"],"mint":pos["mint"],"usd":size,"price":px,"sig":r["sig"],"solscan":r.get("solscan")});state["open_positions"].append(pos);log("trades",{"event":"LIVE_BUY",**pos});return True
    pos={"lead_id":lead["lead_id"],"mint":lead["mint"],"symbol":lead["symbol"],"entry":px,"cost":size,"qty":size/px,"qty0":size/px,"peak":px,"stage":0,"realized":0,"opened":time.time()}
    state["bank"]-=size;state["open_positions"].append(pos);log("trades",{"event":"PAPER_BUY",**pos});return True
