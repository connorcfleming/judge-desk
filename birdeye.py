"""Birdeye enrichment for Jev dossiers. Fail-safe: any error/budget hit -> {} (fields untouched).
Endpoint: GET /defi/v3/token/trade-data/single (12 CU fixed) -> holder, buy/sell 5m + previous 5m.
Key read at runtime from $BIRDEYE_API_KEY (or file $BIRDEYE_KEY_FILE, default ~/.birdeye_key); never printed/logged/written."""
import json,os,time,urllib.request,urllib.parse,datetime
D=os.path.dirname(os.path.abspath(__file__))
SPEND=os.path.join(D,"birdeye_spend.json");KEYF=os.environ.get("BIRDEYE_KEY_FILE",os.path.expanduser("~/.birdeye_key"))
BASE="https://public-api.birdeye.so";CU_TRADE=12;DAILY_CU=900;HOURLY_CU=36;SPACING=1.1
_last=[0.0]
def _today():return datetime.date.today().isoformat()
def spend():
    try:s=json.load(open(SPEND))
    except Exception:s={}
    if s.get("date")!=_today():s={"date":_today(),"cu":0,"calls":0,"errors":0}
    return s
def _save(s):
    tmp=SPEND+".tmp%d"%os.getpid();json.dump(s,open(tmp,"w"),indent=1);os.replace(tmp,SPEND)
def _get(path,params,cu):
    s=spend()
    if s["cu"]+cu>DAILY_CU:return None,"budget"
    import time as _t;h=_t.strftime("%Y-%m-%dT%H");HF=os.path.join(D,"birdeye_hourly.json")
    try:hb=json.load(open(HF))
    except Exception:hb={}
    if hb.get(h,0)+cu>HOURLY_CU:return None,"budget"
    hb={h:hb.get(h,0)+cu};json.dump(hb,open(HF,"w"))
    try:key=os.environ.get("BIRDEYE_API_KEY") or open(KEYF).read().strip()
    except Exception:return None,"nokey"
    url=BASE+path+"?"+urllib.parse.urlencode(params)
    for attempt in range(3):
        w=SPACING-(time.time()-_last[0])
        if w>0:time.sleep(w)
        _last[0]=time.time()
        s=spend();s["cu"]+=cu;s["calls"]+=1;_save(s)   # count CU before response: conservative
        try:
            r=urllib.request.Request(url,headers={"X-API-KEY":key,"x-chain":"solana","accept":"application/json"})
            d=json.load(urllib.request.urlopen(r,timeout=8))
            if d.get("success") and isinstance(d.get("data"),dict):return d["data"],None
            err="bad_response"
        except urllib.error.HTTPError as e:
            err="http%d"%e.code
            if e.code==429 and attempt<2 and spend()["cu"]+cu<=DAILY_CU:time.sleep(2*(attempt+1));continue
        except Exception as e:err=type(e).__name__
        break
    s=spend();s["errors"]=s.get("errors",0)+1;_save(s);return None,err
def _n(x):return x if isinstance(x,(int,float)) and not isinstance(x,bool) else None
def fetch(mint):
    """-> dict of present values only, plus '_status'"""
    try:
        d,err=_get("/defi/v3/token/trade-data/single",{"address":mint},CU_TRADE)
        if not d:return {"_status":err}
        out={"_status":"ok"}
        if _n(d.get("holder")) is not None:out["holders_now"]=int(d["holder"])
        b,s_=_n(d.get("buy_5m")),_n(d.get("sell_5m"))
        if b is not None and s_ is not None:out["buys_sells_m5"]=[int(b),int(s_)]
        b,s_=_n(d.get("buy_history_5m")),_n(d.get("sell_history_5m"))
        if b is not None and s_ is not None:out["buys_sells_prev_m5"]=[int(b),int(s_)]
        return out
    except Exception as e:return {"_status":"exc_"+type(e).__name__}
def apply(d,mint):
    """overlay Birdeye values onto dossier d (only where present); record holders snapshot so holders_1h_ago fills later"""
    try:
        if d.get("holders_1h_ago")!="missing" and d.get("buys_sells_prev_m5")!="missing":
            d["_birdeye"]="skipped_not_needed";return d   # free snapshots already filled it: save hourly CU for later leads
        f=fetch(mint);d["_birdeye"]=f.get("_status")
        for k in ("holders_now","buys_sells_m5","buys_sells_prev_m5"):
            if k in f:d[k]=f[k]
        if "holders_now" in f:
            import snapshots as S
            try:S.record(mint,holders=f["holders_now"])
            except Exception:pass
            if d.get("holders_1h_ago")=="missing":
                h1=S.nearest(mint,3600,15*60,"holders")
                if h1 is not None:d["holders_1h_ago"]=h1
    except Exception:pass
    return d
