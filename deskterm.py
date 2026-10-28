"""Read-only 'desk terminal' data built from logs/state (extends deskdata.snapshot).
Never reads .env/keys. Network: DexScreener (free, one batch call per refresh, cached) and,
only if a PUBLIC wallet address is configured (env DESK_WALLET_PUBKEY or config.json 'wallet_pubkey'),
a public Solana RPC getBalance cached >=60s."""
import json,os,time,datetime,re,urllib.request,collections
import deskdata as dd
UA={"User-Agent":"desk-ui","Content-Type":"application/json"}
SOL="So11111111111111111111111111111111111111112"
_C={}
def _cached(key,ttl,fn):
    c=_C.get(key)
    if c and time.time()-c[0]<ttl:return c[1]
    try:v=fn()
    except Exception:v=c[1] if c else None
    _C[key]=(time.time(),v);return v
def _hm(ts):
    try:return datetime.datetime.strptime(ts[:19],"%Y-%m-%dT%H:%M:%S").strftime("%H:%M:%S")
    except Exception:return str(ts)[11:19]
def dex_batch(mints):
    """One DexScreener batch call (<=30 mints) per 30s; returns {mint:{price,h1,sym}}."""
    mints=sorted(set(m for m in mints if m))[:30]
    def f():
        r=json.load(urllib.request.urlopen(urllib.request.Request("https://api.dexscreener.com/tokens/v1/solana/"+",".join(mints),headers=UA),timeout=8))
        out={}
        for p in r:
            m=(p.get("baseToken") or {}).get("address")
            if m and m not in out:out[m]={"price":float(p.get("priceUsd") or 0) or None,"h1":(p.get("priceChange") or {}).get("h1")}
        return out
    return _cached("dex:"+",".join(mints),30,f) or {}
def wallet(d):
    pub=os.environ.get("DESK_WALLET_PUBKEY") or (dd._j(os.path.join(d,"config.json"),{}) or {}).get("wallet_pubkey")
    if not pub:return {"configured":False}
    def f():
        body=json.dumps({"jsonrpc":"2.0","id":1,"method":"getBalance","params":[pub]}).encode()
        r=json.load(urllib.request.urlopen(urllib.request.Request("https://api.mainnet-beta.solana.com",data=body,headers=UA),timeout=8))
        return r["result"]["value"]/1e9
    sol=_cached("bal:"+pub,60,f);px=(dex_batch([SOL]).get(SOL) or {}).get("price")
    return {"configured":True,"address":dd.short(pub),"sol":sol,"sol_usd":px,"usd":(sol*px) if (sol is not None and px) else None,"cached_s":60}
def build(d,live_price=True):
    L=lambda f:os.path.join(d,"logs",f);t0=dd.today()
    snap=dd.snapshot(d,live_price=live_price)
    leads=dd._jl(L("leads.jsonl"),3000);risk=dd._jl(L("risk.jsonl"),1500);whale=dd._jl(L("whale.jsonl"),800)
    judge=dd._jl(L("judge.jsonl"),400);gate=dd._jl(L("gate.jsonl"),1500);trades=dd._jl(L("trades.jsonl"),2000);live=dd._jl(L("live.jsonl"),500)
    sym={x.get("lead_id"):x.get("symbol") for x in leads};mint={x.get("lead_id"):x.get("mint") for x in leads}
    for j in judge:sym.setdefault(j.get("lead_id"),j.get("symbol"))
    S=lambda lid:"$"+str(sym.get(lid) or (lid or "?")[:8])
    today=lambda rows:[r for r in rows if str(r.get("ts","")).startswith(t0)]
    ev=[]
    def add(ts,agent,msg,lid=None,kind=None):ev.append({"ts":ts,"t":_hm(ts),"agent":agent,"msg":msg,"lead_id":lid,"kind":kind or agent})
    for x in leads[-400:]:
        o=x.get("onchain_reason") or {}
        add(x.get("ts"),"SEARCH",f"{'qualified' if x.get('qualified') else 'skipped'} {S(x.get('lead_id'))} age {o.get('age_h','?')}h liq ${round((o.get('liq_usd') or 0)/1e3)}k vol1h ${round((o.get('vol_h1') or 0)/1e3)}k [{','.join(o.get('sources') or [])}]",x.get("lead_id"),"SEARCH" if x.get("qualified") else "MUTED")
    for r in risk[-300:]:
        if r.get("result")=="dead":add(r.get("ts"),"RISK",f"killed {S(r.get('lead_id'))} — {', '.join(r.get('fails') or [])}",r.get("lead_id"),"KILL")
        else:add(r.get("ts"),"RISK",f"{r.get('result')} {S(r.get('lead_id'))} top10 {(r.get('checks') or {}).get('top10_pct')}%",r.get("lead_id"))
    for w in whale[-200:]:add(w.get("ts"),"WHALE",f"{w.get('result')} {S(w.get('lead_id'))} hits {len(w.get('hits') or [])}/{w.get('checked')}",w.get("lead_id"))
    for j in judge[-200:]:
        a=j.get("answers") or {};ac=a.get("action") or {}
        add(j.get("ts"),"JUDGE",f"{S(j.get('lead_id'))} {ac.get('option')} p{ac.get('p')} (organic {(a.get('organic') or {}).get('option')}, late {(a.get('late') or {}).get('option')}, exit_risk {(a.get('exit_risk') or {}).get('option')})",j.get("lead_id"))
    for g in gate[-300:]:
        k=dd.kb(g.get("killed_by"));dec=g.get("decision")
        add(g.get("ts"),"GATE",f"{dec} {S(g.get('lead_id'))}"+(f" — killed_by {k}" if k else ""),g.get("lead_id"),"BUY" if dec=="buy" else ("KILL" if k else "GATE"))
    for t in trades:
        e=t.get("event","");lid=t.get("lead_id")
        if "BUY" in e:add(t.get("ts"),"SNIPER",f"{e} {S(lid)} ${round(t.get('cost') or 0,2)} @ {t.get('entry')}",lid,"BUY")
        else:add(t.get("ts"),"EXIT",f"{e} {S(lid)} {t.get('why')} → ${round(t.get('usd') or 0,2)} @ {t.get('price')}",lid,"SELL")
    for v in live:add(v.get("ts"),"SNIPER",f"LIVE {v.get('tag')} {v.get('event')} sig {dd.short(v.get('sig'))}"+(f" err {v.get('err')}" if v.get("err") else ""),None,"LIVE")
    try:ew=open(L("exit_watch.out")).read().splitlines()
    except OSError:ew=[]
    last_ew=None
    for i,l in enumerate(ew[-400:]):
        m=re.match(r"(\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d) (.*)",l)
        if not m:continue
        ts=m[1]+"T"+m[2];last_ew=(ts,m[3])
        if "checked" in m[3] and i<len(ew[-400:])-1 and "error" not in m[3]:continue  # only latest heartbeat
        add(ts,"HEAD" if "checked" in m[3] else "EXIT",("exit_watch "+m[3]).replace("{'ok': True, 'err': None}","prices ok"),None,"KILL" if "error" in m[3] else "HEAD")
    ev.sort(key=lambda e:str(e["ts"])[:19]);term=ev[-200:]
    # agents
    def last(rows):return rows[-1] if rows else {}
    pos=snap.get("positions") or []
    def evlast(a):
        for e in reversed(ev):
            if e["agent"]==a:return e
        return {}
    lt=today(leads);rt=today(risk);wt=today(whale);jt=today(judge);gtd=today(gate);tt=today(trades)
    loops=snap.get("loops") or {}
    up=lambda n:bool((loops.get(n) or {}).get("pid"))
    ex=evlast("EXIT");exmsg=ex.get("msg")
    if pos:exmsg=" · ".join(f"{p['symbol']} {('%+.0f%%'%p['pnl_pct']) if p.get('pnl_pct') is not None else '?'} stage {p.get('stage')}" for p in pos)
    agents=[
     {"id":"SEARCH","icon":"⌕","msg":evlast("SEARCH").get("msg"),"ts":last(leads).get("ts"),"stat":f"{len(lt)} leads · {sum(1 for x in lt if x.get('qualified'))} qualified today","life":len(leads)},
     {"id":"RISK","icon":"⛨","msg":evlast("RISK").get("msg"),"ts":last(risk).get("ts"),"stat":f"{sum(1 for r in rt if r.get('result')=='dead')}/{len(rt)} killed today","life":len(risk)},
     {"id":"WHALE","icon":"◉","msg":evlast("WHALE").get("msg"),"ts":last(whale).get("ts"),"stat":f"{sum(1 for w in wt if w.get('result')=='confirm')} confirms / {len(wt)} today","life":len(whale)},
     {"id":"JUDGE","icon":"⚖","name":"Jev","msg":evlast("JUDGE").get("msg"),"ts":last(judge).get("ts"),"stat":f"{len(jt)} judged today · ${round((snap.get('jev_spend') or {}).get('usd') or 0,3)}/$1 spend","life":len(judge)},
     {"id":"GATE","icon":"⛩","msg":evlast("GATE").get("msg"),"ts":last(gate).get("ts"),"stat":f"{sum(1 for g in gtd if g.get('decision')=='buy')} buy · {sum(1 for g in gtd if g.get('decision')=='watch')} watch today","life":len(gate)},
     {"id":"SNIPER","icon":"⌖","msg":evlast("SNIPER").get("msg"),"ts":evlast("SNIPER").get("ts"),"stat":f"{sum(1 for t in tt if 'BUY' in t.get('event',''))} buys today · {len(live)} live tx","life":sum(1 for t in trades if 'BUY' in t.get('event',''))},
     {"id":"EXIT","icon":"⇥","msg":exmsg,"ts":last_ew[0] if last_ew else ex.get("ts"),"stat":f"{len(pos)} open · {sum(1 for t in tt if 'SELL' in t.get('event',''))} sells today","life":sum(1 for t in trades if 'SELL' in t.get('event','')),"up":up("exit_watch")},
     {"id":"HEAD","icon":"▤","name":"logger","msg":f"loops: "+", ".join(f"{n} {'up' if up(n) else 'DOWN'}" for n in ("exit_watch","grad_collector","snapshot_collector")),"ts":snap.get("now"),"stat":f"{len(ev)} events in window","life":None}]
    for a in agents:a["t"]=_hm(a["ts"]) if a.get("ts") else None
    healthy=up("exit_watch") and up("grad_collector") and up("snapshot_collector")
    # kills today
    kc=collections.Counter()
    for r in rt:
        if r.get("result")=="dead":
            for f in r.get("fails") or ["dead"]:kc["risk:"+f]+=1
    for g in gtd:
        k=g.get("killed_by")
        if isinstance(k,list) and len(k)==2 and isinstance(k[1],dict):kc[f"gate:{k[0]}={k[1].get('option')}"]+=1
        elif isinstance(k,list):kc["gate:"+":".join(map(str,k))]+=1
        elif k:kc["gate:"+str(k)]+=1
    kills=[{"rule":k,"n":n} for k,n in kc.most_common(12)]
    # ticker
    seen=[];
    for x in reversed(leads):
        if x.get("mint") and x["mint"] not in [s[0] for s in seen]:seen.append((x["mint"],x.get("symbol"),x.get("lead_id")))
        if len(seen)>=20:break
    px=dex_batch([s[0] for s in seen]+[SOL]) if live_price else {}
    ticker=[{"symbol":s[1],"lead_id":s[2],"price":(px.get(s[0]) or {}).get("price"),"h1":(px.get(s[0]) or {}).get("h1")} for s in seen]
    # paper equity from trades
    st=dd._j(os.path.join(d,"state.json"),{}) or {}
    bank=st.get("bank") or 0;buys=sum(t.get("cost") or 0 for t in trades if "BUY" in t.get("event",""));sells=sum(t.get("usd") or 0 for t in trades if "SELL" in t.get("event",""))
    start=bank+buys-sells;cash=start;opencost={};series=[]
    for t in trades:
        if "BUY" in t.get("event",""):cash-=t.get("cost") or 0;opencost[t.get("lead_id")]=t.get("cost") or 0
        else:
            cash+=t.get("usd") or 0
            if not any(p.get("lead_id")==t.get("lead_id") and p.get("qty",0)>0 for p in st.get("open_positions",[])):pass
        oc=sum(v for k,v in opencost.items() if any(p.get("lead_id")==k for p in st.get("open_positions",[])) or not any(c.get("lead_id")==k for c in st.get("closed",[])))
        series.append({"ts":t.get("ts"),"eq":round(cash+oc,4)})
    mark=sum((p.get("pnl_usd") or 0)+(p.get("cost") or 0) for p in pos)
    eq_now=bank+mark;series.append({"ts":snap.get("now"),"eq":round(eq_now,4)})
    closed=st.get("closed") or [];w=sum(1 for c in closed if (c.get("realized") or 0)>(c.get("cost") or 0));l=len(closed)-w
    lw=[v for v in live if v.get("event")=="sent" and not str(v.get("tag","")).startswith("TEST")]
    equity={"paper":{"label":"PAPER","start":round(start,2),"bank_cash":bank,"open_mark":mark,"equity":eq_now,"pnl":eq_now-start,"pnl_pct":(eq_now/start-1)*100 if start else None,"wins":w,"losses":l,"series":series},
            "live":{"label":"LIVE","wallet":wallet(d),"trades":len(lw),"wins":None,"losses":None,"note":"no live round-trips logged yet" if not lw else None,"test_tx":len(live)-len(lw)}}
    trade_events=[{"key":f"{t.get('ts')}|{t.get('event')}|{t.get('lead_id')}|{t.get('why')}","ts":t.get("ts"),"event":t.get("event"),"symbol":sym.get(t.get("lead_id")) or t.get("symbol"),"why":t.get("why"),"usd":t.get("usd") or t.get("cost")} for t in trades[-20:]]+[{"key":f"{v.get('ts')}|live|{v.get('sig')}","ts":v.get("ts"),"event":"LIVE "+str(v.get("event")),"symbol":v.get("tag"),"why":v.get("err"),"usd":None} for v in live[-10:]]
    return {"now":snap.get("now"),"healthy":healthy,"loops":loops,"agents":agents,"terminal":term,"kills":kills,"ticker":ticker,"equity":equity,"positions":pos,"trade_events":trade_events,"funnel":snap.get("funnel"),"feed":snap.get("feed")[:40]}
def coin(d,lead_id):
    L=lambda f:os.path.join(d,"logs",f)
    f=lambda name,n:[r for r in dd._jl(L(name),n) if r.get("lead_id")==lead_id]
    ld=f("leads.jsonl",5000);rk=f("risk.jsonl",3000);wh=f("whale.jsonl",2000);jd=f("judge.jsonl",1000);gt=f("gate.jsonl",3000);tr=f("trades.jsonl",3000)
    lead=ld[-1] if ld else {};j=jd[-1] if jd else {}
    m=lead.get("mint") or j.get("mint")
    if not tr and m:tr=[t for t in dd._jl(L("trades.jsonl"),3000) if t.get("mint")==m]
    dos={k:v for k,v in (j.get("dossier") or {}).items() if k not in("risk","whale","_birdeye")}
    trail=[{"ts":x.get("ts"),"step":s,"what":w} for s,x,w in
      [("SEARCH",lead,f"qualified={lead.get('qualified')} sources={(lead.get('onchain_reason') or {}).get('sources')}")]+
      [("RISK",r,f"{r.get('result')} {r.get('fails') or ''}") for r in rk]+[("WHALE",w,f"{w.get('result')} hits {len(w.get('hits') or [])}") for w in wh]+
      [("JUDGE",x,str({k:(v or {}).get('option') for k,v in (x.get('answers') or {}).items()})) for x in jd]+
      [("GATE",g,f"{g.get('decision')} killed_by={dd.kb(g.get('killed_by'))}") for g in gt]+
      [("TRADE",t,f"{t.get('event')} {t.get('why') or ''} ${round(t.get('usd') or t.get('cost') or 0,2)}") for t in tr] if x]
    trail.sort(key=lambda e:str(e["ts"])[:19])
    buys=[t for t in tr if "BUY" in t.get("event","")];sells=[t for t in tr if "SELL" in t.get("event","")]
    cost=sum(t.get("cost") or 0 for t in buys);got=sum(t.get("usd") or 0 for t in sells)
    return {"lead_id":lead_id,"symbol":lead.get("symbol") or j.get("symbol"),"mint":m,"lead":lead.get("onchain_reason"),"dossier":dos,
      "risk":rk[-1] if rk else None,"whale":wh[-1] if wh else None,"jev":{"model":j.get("model"),"answers":j.get("answers")} if j else None,
      "gate":gt[-1] if gt else None,"trades":tr,"traded":bool(tr),"entry":buys[0].get("entry") if buys else None,"exits":[{"price":t.get("price"),"why":t.get("why"),"usd":t.get("usd")} for t in sells],
      "pnl_realized":(got-cost) if sells else None,"trail":trail}
