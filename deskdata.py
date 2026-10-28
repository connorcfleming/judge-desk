"""Read-only snapshot of the desk's logs/state for watch_scanner.py and ui/server.py.
Never reads .env, key files, or wallet keys. Never writes anything."""
import json,os,time,datetime
def _jl(path,n=400):
    try:
        with open(path,"rb") as f:
            f.seek(0,2);sz=f.tell();f.seek(max(0,sz-n*2500));lines=f.read().decode("utf-8","replace").splitlines()
    except OSError:return []
    out=[]
    for l in lines[-n:]:
        try:out.append(json.loads(l))
        except Exception:pass
    return out
def _j(path,default=None):
    try:return json.load(open(path))
    except Exception:return default
def _alive(pidf):
    try:pid=int(open(pidf).read().strip());os.kill(pid,0);return pid
    except Exception:return None
def _age(p):
    try:return round(time.time()-os.path.getmtime(p))
    except OSError:return None
_PC={}
def price(mint,ttl=30):
    """Free public DexScreener price lookup (no key), cached; None on failure."""
    import urllib.request
    c=_PC.get(mint)
    if c and time.time()-c[0]<ttl:return c[1]
    p=None
    try:
        r=json.load(urllib.request.urlopen(urllib.request.Request("https://api.dexscreener.com/tokens/v1/solana/"+mint,headers={"User-Agent":"desk-ui"}),timeout=6))
        p=float(r[0]["priceUsd"]) if r else None
    except Exception:pass
    _PC[mint]=(time.time(),p);return p
def kb(v):
    if not v:return None
    if isinstance(v,list):return ":".join(str(x.get("option",x)) if isinstance(x,dict) else str(x) for x in v)
    return str(v)
def short(m):return (m[:4]+".."+m[-4:]) if m and len(m)>10 else (m or "")
def today():return datetime.datetime.now().strftime("%Y-%m-%d")
def snapshot(d=".",live_price=True):
    L=lambda f:os.path.join(d,"logs",f)
    t0=today();grad=_j(L("grad_ws.json"),{}) or {}
    leads=_jl(L("leads.jsonl"),5000);risk=_jl(L("risk.jsonl"));whale=_jl(L("whale.jsonl"))
    judge=_jl(L("judge.jsonl"),200);gate=_jl(L("gate.jsonl"));trades=_jl(L("trades.jsonl"));live=_jl(L("live.jsonl"),100)
    rk={r.get("lead_id"):r for r in risk};wh={w.get("lead_id"):w for w in whale};gt={g.get("lead_id"):g for g in gate}
    sym={}
    feed=[]
    for x in leads[-60:][::-1]:
        o=x.get("onchain_reason",{}) or {};src=list(o.get("sources",[]))
        if x.get("mint") in grad:src.insert(0,"pumpportal_migration")
        if (x.get("mint") or "").endswith("pump") and "pumpportal_migration" not in src and "pumpfun_grad" not in src and o.get("pump_amm") is False:src.append("bonding_curve")
        lid=x.get("lead_id");r=rk.get(lid,{});w=wh.get(lid,{});g=gt.get(lid,{})
        feed.append({"ts":x.get("ts"),"lead_id":lid,"symbol":x.get("symbol"),"mint":short(x.get("mint")),"age_h":o.get("age_h"),
          "mcap":o.get("mcap") or x.get("mcap"),"liq":o.get("liq_usd"),"vol_h1":o.get("vol_h1"),"qualified":x.get("qualified"),"sources":src,
          "risk":r.get("result"),"risk_fails":r.get("fails"),"whale":w.get("result"),"gate":g.get("decision"),"killed_by":kb(g.get("killed_by"))})
    for x in leads:sym[x.get("lead_id")]=x.get("symbol")
    jt=[]
    for j in judge[-30:][::-1]:
        a=j.get("answers") or {};g=gt.get(j.get("lead_id"),{})
        f=lambda k:(a.get(k) or {});jt.append({"ts":j.get("ts"),"symbol":j.get("symbol"),"mint":short(j.get("mint")),"model":j.get("model"),
          "action":f("action").get("option"),"action_p":f("action").get("p"),"organic":f("organic").get("option"),"organic_p":f("organic").get("p"),
          "late":f("late").get("option"),"exit_risk":f("exit_risk").get("option"),"gate":g.get("decision"),"killed_by":kb(g.get("killed_by"))})
    tw=lambda rows:[r for r in rows if str(r.get("ts","")).startswith(t0)]
    lt=tw(leads);funnel={"leads":len(lt),"qualified":sum(1 for x in lt if x.get("qualified")),
      "risk_checked":len(tw(risk)),"risk_dead":sum(1 for r in tw(risk) if r.get("result")=="dead"),
      "whale_confirm":sum(1 for w in tw(whale) if w.get("result")=="confirm"),"jev_judged":len(tw(judge)),
      "gate_buy":sum(1 for g in tw(gate) if g.get("decision")=="buy"),"gate_watch":sum(1 for g in tw(gate) if g.get("decision")=="watch"),
      "trades":len(tw(trades))}
    st=_j(os.path.join(d,"state.json"),{}) or {}
    pos=[]
    snaps=_j(L("snapshots.json"),{}) or {}
    for p in st.get("open_positions",[]):
        last=None
        s=snaps.get(p.get("mint")) if isinstance(snaps,dict) else None
        if isinstance(s,list) and s and isinstance(s[-1],dict):last=s[-1].get("price") or s[-1].get("price_usd")
        cur=last or (price(p.get("mint")) if live_price and p.get("mint") else None)
        e=p.get("entry");pnl=((cur/e-1)*100) if (cur and e) else None
        peak_pct=((p.get("peak")/e-1)*100) if (p.get("peak") and e) else None
        pos.append({"symbol":p.get("symbol"),"mint":short(p.get("mint")),"entry":e,"cost":p.get("cost"),"stage":p.get("stage"),
          "peak_pct":peak_pct,"pnl_pct":pnl,"price":cur,"pnl_usd":(p.get("qty",0)*cur-p.get("cost",0)+(p.get("realized") or 0)) if cur else None,"realized":p.get("realized"),"held_min":round((time.time()-p.get("opened",time.time()))/60)})
    jev=_j(os.path.join(d,"jev_spend.json"),{}) or {};be=_j(os.path.join(d,"birdeye_spend.json"),{}) or {}
    ew=[];
    try:ew=open(L("exit_watch.out")).read().splitlines()[-5:]
    except OSError:pass
    loops={n:{"pid":_alive(L(n+".pid")),"log_age_s":_age(L(n+".out"))} for n in ("exit_watch","grad_collector","snapshot_collector")}
    loops["grad_ws.json"]={"pid":None,"log_age_s":_age(L("grad_ws.json")),"mints_6h":len(grad)}
    whales=[{"ts":w.get("ts"),"symbol":sym.get(w.get("lead_id"),w.get("lead_id")),"result":w.get("result"),"hits":len(w.get("hits") or []),"checked":w.get("checked"),"rpc":w.get("rpc")} for w in whale[-25:][::-1]]
    tr=[{k:t.get(k) for k in ("ts","event","why","lead_id","price","usd")}|{"symbol":sym.get(t.get("lead_id"))} for t in trades[-20:][::-1]]
    lv=[{k:v.get(k) for k in ("ts","tag","event","err","impact_pct")}|{"sig":short(v.get("sig"))} for v in live[-10:][::-1]]
    return {"now":datetime.datetime.now().isoformat(timespec="seconds"),"bank":st.get("bank"),"watch_n":len(st.get("watch",[]) or []),
      "funnel":funnel,"feed":feed,"judge":jt,"whales":whales,"positions":pos,"trades":tr,"live":lv,
      "jev_spend":{"date":jev.get("date"),"calls":jev.get("calls"),"usd":jev.get("usd"),"cap_usd":1.0},
      "birdeye_spend":{k:be.get(k) for k in ("date","calls","usd") if k in be},"exit_watch_tail":ew,"loops":loops}
