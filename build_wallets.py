#!/usr/bin/env python3
"""Build/MERGE wallets.json from free data: DexScreener (winners) + early buyers.
Early buyers: Helius enhanced tx API in ascending order (HELIUS_API_KEY env, read at runtime, never logged) -> first hour reachable
for any token; fallback = RPC getSignaturesForAddress paging (Helius RPC if key, else WHALE_RPC/public).
Accumulates across runs in wallet_db.json (address -> {mint: first_buy_ts}); already-scanned winners are skipped (--rescan to redo).
wallets.json: manual entries (source='manual', always active, never removed) + wallets with >= --min-hits distinct winners.
1-hit wallets are kept in wallet_candidates.json for accumulation.
Usage: python3 build_wallets.py [--max-tokens 40] [--min-hits 2] [--keep 50] [--pages 5] [--rescan]"""
import json,time,sys,argparse,urllib.request,collections,os
from common import get,P,save
HK=os.environ.get("HELIUS_API_KEY")
RPC=f"https://mainnet.helius-rpc.com/?api-key={HK}" if HK else os.environ.get("WHALE_RPC","https://api.mainnet-beta.solana.com")
EXCL={"So11111111111111111111111111111111111111112","6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P","pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
 "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1","39azUYFWPz3VHgKCf3VChUwbpURdCHRxjWVowf5jUJjg","TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM"}
def rpc(m,p,tries=6):
    d=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode()
    for i in range(tries):
        try:
            r=urllib.request.Request(RPC,d,{"content-type":"application/json","User-Agent":"judge-desk"})
            j=json.loads(urllib.request.urlopen(r,timeout=30).read())
            if "error" in j:
                if j["error"].get("code") in(429,-32429,-32005):raise Exception("rl")
                return None
            return j["result"]
        except Exception: time.sleep(min(30,1.5*2**i))
    return None
QUERIES=["pump","pumpswap","raydium solana","meteora","bonk","sol meme","cat","dog","pepe","ai","trump","elon","frog","coin","inu","moon","wif","based","chill","baby","grok","penguin","monkey","cto","nigga","retard","goat","jeet","bull","god"]
def winners(maxn):
    seen={}
    for u in["https://api.dexscreener.com/token-boosts/top/v1","https://api.dexscreener.com/token-boosts/latest/v1","https://api.dexscreener.com/token-profiles/latest/v1"]:
        try:
            for t in get(u):
                if t.get("chainId")=="solana":seen[t["tokenAddress"]]=1
        except Exception as e:print("dex list fail",u,e)
    for q in QUERIES:
        try:
            for p in get(f"https://api.dexscreener.com/latest/dex/search?q={q}")["pairs"]:
                if p.get("chainId")=="solana":seen[p["baseToken"]["address"]]=1
        except Exception:pass
    out=[];mints=list(seen);now=time.time()*1000
    for i in range(0,len(mints),30):
        try:ps=get("https://api.dexscreener.com/tokens/v1/solana/"+",".join(mints[i:i+30]))
        except Exception:continue
        best={}
        for p in ps:
            m=p["baseToken"]["address"]
            if m not in best or (p.get("liquidity")or{}).get("usd",0)>(best[m].get("liquidity")or{}).get("usd",0):best[m]=p
        for m,p in best.items():
            age=(now-(p.get("pairCreatedAt")or now))/3.6e6;fdv=p.get("fdv")or 0;pc=p.get("priceChange")or{}
            if 6<=age<=24*8 and 300_000<=fdv<=500_000_000 and p["baseToken"]["symbol"].upper()!="SOL" and (pc.get("h24",0)>=50 or pc.get("h6",0)>=30 or fdv>=1_000_000):
                out.append({"mint":m,"sym":p["baseToken"]["symbol"],"fdv":fdv,"age_h":round(age,1)})
    out.sort(key=lambda x:-x["fdv"]);return out[:maxn]
def early_buyers_rpc(mint,max_pages=None):
    max_pages=max_pages or (250 if HK else 40)
    before=None;oldest=[]
    for _ in range(max_pages):
        cfg={"limit":1000};
        if before:cfg["before"]=before
        s=rpc("getSignaturesForAddress",[mint,cfg]);time.sleep(0.12 if HK else 0.4)
        if s is None:return None,"rpc fail"
        if not s:break
        oldest=s;before=s[-1]["signature"]
        if len(s)<1000:break
    else:return None,"history too deep (>%d sigs)"%(max_pages*1000)
    sigs=[x for x in reversed(oldest) if not x.get("err")]
    if not sigs:return None,"no sigs"
    s0=sigs[0]["slot"];t0=sigs[0].get("blockTime")or 0
    dev=None;buyers={}
    for k,x in enumerate(sigs[:70]):
        if (x.get("blockTime")or 0)-t0>3600:break
        tx=rpc("getTransaction",[x["signature"],{"encoding":"jsonParsed","maxSupportedTransactionVersion":0}]);time.sleep(0.12 if HK else 0.25)
        if not tx:continue
        keys=tx["transaction"]["message"]["accountKeys"];payer=keys[0]["pubkey"] if isinstance(keys[0],dict) else keys[0]
        if k==0:dev=payer
        if x["slot"]<=s0+1:continue   # block-0 / bundle snipers
        meta=tx["meta"];pre={(b["accountIndex"]):float(b["uiTokenAmount"]["uiAmount"]or 0) for b in meta.get("preTokenBalances",[]) if b["mint"]==mint}
        for b in meta.get("postTokenBalances",[]):
            if b["mint"]!=mint:continue
            o=b.get("owner");d=float(b["uiTokenAmount"]["uiAmount"]or 0)-pre.get(b["accountIndex"],0)
            if d>0 and o==payer:buyers.setdefault(o,x.get("blockTime"))
    buyers.pop(dev,None)
    return buyers,"ok dev=%s"%dev
def _enh(addr,before=None):
    u=f"https://api.helius.xyz/v0/addresses/{addr}/transactions?api-key={HK}&limit=100&sort-order=asc"+(f"&before-signature={before}" if before else "")
    for i in range(5):
        try:return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"judge-desk"}),timeout=30).read())
        except Exception as e:
            if getattr(e,"code",None)==429:time.sleep(2*(i+1));continue
            return None   # never print e (URL carries the key)
    return None
def early_buyers_helius(mint,pages=5):
    """ascending history: buyers = fee payers who received the mint within 1h of the first tx, excl. creation slot+1 and deployer"""
    txs=[];last=None
    for _ in range(pages):
        d=_enh(mint,last);time.sleep(0.6)
        if d is None:return None,"helius fail"
        if not d:break
        txs+=d;last=d[-1]["signature"]
        if (d[-1].get("timestamp") or 0)-(txs[0].get("timestamp") or 0)>3600:break
    if not txs:return None,"no txs"
    t0=txs[0].get("timestamp") or 0;s0=txs[0].get("slot") or 0
    dev=next((t["feePayer"] for t in txs if t.get("type")=="CREATE"),txs[0].get("feePayer"))
    buyers={}
    for t in txs:
        if (t.get("timestamp") or 0)-t0>3600:break
        if (t.get("slot") or 0)<=s0+1 or t.get("transactionError"):continue
        fp=t.get("feePayer")
        if any(x.get("mint")==mint and x.get("toUserAccount")==fp and (x.get("tokenAmount") or 0)>0 for x in t.get("tokenTransfers") or []):
            buyers.setdefault(fp,t.get("timestamp"))
    buyers.pop(dev,None)
    return buyers,"ok helius %d txs dev=%s"%(len(txs),dev)
def early_buyers(mint,pages=5):
    if HK:
        b,why=early_buyers_helius(mint,pages)
        if b is not None:return b,why
    return early_buyers_rpc(mint)
def main():
    a=argparse.ArgumentParser();a.add_argument("--max-tokens",type=int,default=40);a.add_argument("--min-hits",type=int,default=2);a.add_argument("--keep",type=int,default=50)
    a.add_argument("--pages",type=int,default=5);a.add_argument("--rescan",action="store_true");g=a.parse_args()
    g.min_hits=max(2,g.min_hits)
    try:db=json.load(open(P("wallet_db.json")))
    except Exception:db={"wallets":{},"scanned":{}}
    try:old=json.load(open(P("wallets.json")))
    except Exception:old={}
    manual=[x for x in old.get("wallets",[]) if x.get("source")=="manual"]
    for x in old.get("wallets",[]):   # seed db with previously active on-chain wallets so nothing is lost
        if x.get("source")!="manual" and x.get("address"):
            for m in x.get("tokens",[]):db["wallets"].setdefault(x["address"],{}).setdefault(m,None)
    W=winners(g.max_tokens);print("winners",len(W),"rpc","helius" if HK else "public",flush=True)
    done=0;report=[];skipped=0
    for w in W:
        if w["mint"] in db["scanned"] and not g.rescan:skipped+=1;continue
        b,why=early_buyers(w["mint"],g.pages);print(w["sym"],w["mint"],w["age_h"],"h",int(w["fdv"]),why,len(b) if b else 0,flush=True)
        report.append({**w,"status":why,"buyers":len(b) if b else 0})
        if b is None:continue
        done+=1;db["scanned"][w["mint"]]={"date":time.strftime("%F"),"sym":w["sym"],"buyers":len(b)}
        for o,ts in b.items():
            if o not in EXCL:db["wallets"].setdefault(o,{})[w["mint"]]=ts
        save("wallet_db.json",db)
    day=time.strftime("%Y-%m-%d");man_addr={x["address"] for x in manual}|set(db.get("leaderboard",{}))
    syms={m:v.get("sym") for m,v in db["scanned"].items()}
    bots=db.setdefault("bots",{})
    def is_bot(o):
        """>=1000 txs within 24h => trading bot/sniper (would 'confirm' on almost every fresh lead). Cached 3 days."""
        b=bots.get(o)
        if b and time.time()-b["t"]<3*86400:return b["bot"]
        s=rpc("getSignaturesForAddress",[o,{"limit":1000}],tries=3);time.sleep(0.12 if HK else 0.4)
        if not s:return False
        bot=len(s)>=1000 and (s[0].get("blockTime") or 0)-(s[-1].get("blockTime") or 0)<86400
        bots[o]={"t":time.time(),"bot":bot};return bot
    elig=sorted(((o,t) for o,t in db["wallets"].items() if len(t)>=g.min_hits and o not in man_addr),key=lambda x:-len(x[1]))
    ranked=[x for x in elig if not is_bot(x[0])][:g.keep];nbots=len(elig)-len(ranked) if len(ranked)<g.keep else sum(1 for o,_ in elig if bots.get(o,{}).get("bot"))
    save("wallet_db.json",db)
    lbw=[x for x in db.get("leaderboard",{}).values() if x.get("active")]   # verified leaderboard wallets (kolscan), kept by rebuilds
    wallets=manual+lbw+[{"address":o,"label":f"early-{len(t)}x-{o[:4]}","source":"onchain-early-buyer","hits":len(t),"tokens":sorted(t),"symbols":[syms.get(m) for m in sorted(t)],"added":day,
      "notes":"bought within first hour (after creation slot+1, excl. deployer) of %d winners"%len(t)} for o,t in ranked]
    cands=[{"address":o,"hits":1,"tokens":list(t)} for o,t in db["wallets"].items() if len(t)==1]
    save("wallet_candidates.json",{"built":day,"count":len(cands),"candidates":cands})
    save("wallets.json",{"note":f"merged {day} by build_wallets.py: {len(db['scanned'])} winners scanned total ({done} new this run, {skipped} skipped as already scanned); manual entries always active","built":day,
        "scan":report,"candidates_count":len(cands),"wallets":wallets})
    print(json.dumps({"winners":len(W),"scanned_ok_this_run":done,"skipped_already":skipped,"db_wallets":len(db["wallets"]),"candidates_1hit":len(cands),"manual":len(manual),"active_onchain":len(ranked),"excluded_bots":nbots,"top":[(x['address'],x['hits'],x.get('symbols')) for x in wallets if x.get('source')!='manual'][:5]}))
if __name__=="__main__":main()
