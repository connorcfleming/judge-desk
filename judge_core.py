import math
M="missing"
def num(x):return x if isinstance(x,(int,float)) and not isinstance(x,bool) else None
def sig(x):return 1/(1+math.exp(-x))
def clip(p):return round(min(0.97,max(0.03,p)),2)
def shrink(p,miss):  # missing fields pull probability toward 0.5 (less confidence)
    return 0.5+(p-0.5)*max(0.2,1-0.15*miss)
def judge(d):
    try:
        b,s=map(num,d["buys_sells_h1"]);mb,ms=map(num,d["buys_sells_m5"]);top=num(d["top10_pct"]);ch=num(d["price_change_1h_pct"]);liq=num(d["liquidity_usd"]);dev=num(d["dev_pct"])
        # organic
        z=0;miss=0
        if b is not None and s is not None and b+s>0:z+=6*(b/(b+s)-0.5)+0.6*math.log10(max(b+s,1)/100)
        else:miss+=2
        if top is not None:z+=(20-top)/7
        else:miss+=1
        if dev is not None:z-=dev/5
        else:miss+=1
        if mb is not None and ms is not None and mb+ms>0:z+=2*(mb/(mb+ms)-0.5)
        else:miss+=1
        miss+=sum(d[k]==M for k in("holders_now","holders_1h_ago"))
        po=shrink(sig(z),miss)
        # late: big 1h move => late
        if ch is None:pl,lm=0.5,1
        else:pl,lm=sig((ch-40)/15),0
        pl=shrink(pl,lm+(d["buys_sells_prev_m5"]==M))
        # exit risk from size/liquidity
        frac=num(d["our_size_usd"])/liq if liq and num(d["our_size_usd"]) else None
        er=5 if frac is None else 1 if frac<0.0005 else 2 if frac<0.002 else 3 if frac<0.01 else 4 if frac<0.05 else 5
        per=0.5 if frac is None else clip(0.6+0.35*min(1,abs(math.log10(max(frac,1e-9))-math.log10([0.00022,0.001,0.0045,0.022,0.1][er-1]))))
        # action: probability buy is right
        pb=po*(1-pl)*(1 if er<=3 else 0.3)*(1 if d["risk"]["result"]=="clean" else 0)
        if ch is not None and ch<0:pb*=sig((ch+25)/8)  # falling knife: heavy 1h dump lowers buy
        pb=clip(pb**0.5) if pb>0 else 0.03
        act="buy" if pb>=0.6 else "watch" if pb>=0.4 else "pass"
        pa=pb if act=="buy" else clip(1-abs(pb-0.5)*2) if act=="watch" else clip(1-pb)
        return {"organic":{"option":"yes" if po>=0.5 else "no","p":clip(max(po,1-po))},
                "late":{"option":"yes" if pl>=0.5 else "no","p":clip(max(pl,1-pl))},
                "exit_risk":{"option":er,"p":per},"action":{"option":act,"p":clip(pa)}}
    except Exception as e:return {"error":str(e),"action":{"option":"pass","p":1.0}}
