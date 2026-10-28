"""LIVE swap executor via Jupiter lite-api. Refuses to send unless send=True AND caller passes it explicitly.
Slippage cap 3% (300 bps); aborts if priceImpactPct > 3%. Keeps 0.02 SOL reserve. Key loaded in-process only."""
import urllib.error,json,base64,urllib.request,time
from solders.transaction import VersionedTransaction
from wallet import keypair,rpc,sol_balance
from common import log
USDC="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL="So11111111111111111111111111111111111111112"
RESERVE_SOL=0.02;SLIP_BPS=300;MAX_IMPACT=3.0;PRIO_LAMPORTS=50000
def J(url,body=None):
    r=urllib.request.Request(url,json.dumps(body).encode() if body else None,{"Content-Type":"application/json"})
    for i in range(5):
        try:return json.loads(urllib.request.urlopen(r,timeout=30).read())
        except urllib.error.HTTPError as e:
            if e.code!=429 or i==4:raise
            time.sleep(2*(i+1))
def quote(inp,out,amount):
    q=J(f"https://lite-api.jup.ag/swap/v1/quote?inputMint={inp}&outputMint={out}&amount={int(amount)}&slippageBps={SLIP_BPS}")
    imp=float(q.get("priceImpactPct",0))*100
    return q,imp
def swap(inp,out,amount,send=False,tag=""):
    kp=keypair();pub=str(kp.pubkey())
    if inp==SOL and sol_balance(pub)-amount/1e9<RESERVE_SOL:
        log("live",{"tag":tag,"event":"abort_reserve"});return {"ok":False,"why":"would breach 0.02 SOL reserve"}
    q,imp=quote(inp,out,amount)
    if imp>MAX_IMPACT:log("live",{"tag":tag,"event":"abort_impact","impact_pct":imp});return {"ok":False,"why":f"impact {imp:.2f}%>3%"}
    if not send:return {"ok":True,"dry_run":True,"in":amount,"out":q["outAmount"],"impact_pct":imp}
    s=J("https://lite-api.jup.ag/swap/v1/swap",{"quoteResponse":q,"userPublicKey":pub,"wrapAndUnwrapSol":True,"dynamicComputeUnitLimit":True,
        "prioritizationFeeLamports":{"priorityLevelWithMaxLamports":{"maxLamports":PRIO_LAMPORTS,"priorityLevel":"medium"}}})
    tx=VersionedTransaction.from_bytes(base64.b64decode(s["swapTransaction"]))
    signed=VersionedTransaction(tx.message,[kp])
    r=rpc("sendTransaction",[base64.b64encode(bytes(signed)).decode(),{"encoding":"base64","skipPreflight":False,"maxRetries":3}])
    sig=r.get("result");rec={"tag":tag,"event":"sent" if sig else "send_error","sig":sig,"err":r.get("error"),"in_mint":inp,"out_mint":out,"in":amount,"quote_out":q["outAmount"],"impact_pct":imp}
    log("live",rec);return {"ok":bool(sig),**rec,"solscan":f"https://solscan.io/tx/{sig}" if sig else None}
