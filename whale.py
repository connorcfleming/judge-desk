"""WHALE: smart-money confirm from wallets.json. Result confirm or quiet; any error => quiet (fail-safe), never raises.
RPC: Helius if HELIUS_API_KEY is set (key read from env at runtime, never logged), else WHALE_RPC / public RPC.
Method: derive each tracked wallet's associated token account for the lead mint (SPL + Token-2022), batch getMultipleAccounts
(100/call => ~1-2 credits per lead), then getSignaturesForAddress on accounts that hold the token to get when they last traded it."""
from common import *
import os
def _rpc_url():
    k=os.environ.get("HELIUS_API_KEY")
    return f"https://mainnet.helius-rpc.com/?api-key={k}" if k else os.environ.get("WHALE_RPC","https://api.mainnet-beta.solana.com")
WINDOW_S=2*3600;MAX_WALLETS=300;BUDGET_S=20
TOKEN="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA";T22="TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb";ATA="ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
def _rpc(m,p):
    d=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode()
    r=urllib.request.Request(_rpc_url(),d,{"content-type":"application/json","User-Agent":"judge-desk"})
    try:j=json.loads(urllib.request.urlopen(r,timeout=10).read())
    except Exception as e:raise Exception(type(e).__name__+" "+str(getattr(e,"code","")))   # never echo the URL (contains key)
    if "error" in j:raise Exception(str(j["error"])[:120])
    return j["result"]
def _ata(owner,mint,prog):
    from solders.pubkey import Pubkey as K
    return str(K.find_program_address([bytes(K.from_string(owner)),bytes(K.from_string(prog)),bytes(K.from_string(mint))],K.from_string(ATA))[0])
def active_wallets():
    w=load("wallets.json").get("wallets",[])
    man=[x for x in w if x.get("source")=="manual"];rest=[x for x in w if x.get("source")!="manual"]
    return (man+sorted(rest,key=lambda x:-(x.get("hits") or 0)))[:MAX_WALLETS]
def whale(lead,rk=None):
    try:
        w=active_wallets()
        if not w:out={"lead_id":lead["lead_id"],"result":"quiet","reason":"no tracked wallets (wallets.json empty) - no data, not a signal"}
        else:
            owners=set((rk or {}).get("_owners",[]));t_end=time.time()+BUDGET_S;now=time.time();hits=[];errs=0
            accs=[]
            for x in w:
                for prog in (TOKEN,T22):
                    try:accs.append((x,_ata(x["address"],lead["mint"],prog)))
                    except Exception:errs+=1
            holding=[]
            for i in range(0,len(accs),100):
                if time.time()>t_end:errs+=1;break
                ch=accs[i:i+100]
                try:v=_rpc("getMultipleAccounts",[[a for _,a in ch],{"encoding":"jsonParsed"}])["value"]
                except Exception:errs+=1;continue
                for (x,a),acc in zip(ch,v):
                    try:amt=float(acc["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0) if acc else 0
                    except Exception:amt=0
                    if amt>0:holding.append((x,a,amt))
            for x,a,amt in holding:
                ts=0
                if time.time()<t_end:
                    try:s=_rpc("getSignaturesForAddress",[a,{"limit":5}]);ts=max([y.get("blockTime") or 0 for y in s] or [0])
                    except Exception:errs+=1
                if ts and now-ts<=WINDOW_S:
                    hits.append({"address":x["address"],"label":x.get("label"),"source":x.get("source"),"hits":x.get("hits"),"via":"rpc_holds","amount":amt,"min_ago":round((now-ts)/60,1)})
            for x in w:
                if x["address"] in owners and not any(h["address"]==x["address"] for h in hits):
                    hits.append({"address":x["address"],"label":x.get("label"),"source":x.get("source"),"via":"rugcheck_top_holder"})
            out={"lead_id":lead["lead_id"],"result":"confirm" if hits else "quiet","hits":hits,"checked":len(w),"holding_any_time":len(holding),"rpc_errors":errs,"tracked":len(w),"rpc":"helius" if os.environ.get("HELIUS_API_KEY") else "public"}
    except Exception as e:out={"lead_id":lead.get("lead_id"),"result":"quiet","reason":"whale error (fail-safe): %s"%str(e)[:150]}
    try:log("whale",out)
    except Exception:pass
    return out
