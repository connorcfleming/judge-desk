"""Live sizing math with mocked balance/prices/swap (fake wallet+live_exec in a desk COPY)."""
import sys,os;sys.path.insert(0,os.getcwd())
import live_exec as L,wallet as W
assert "TEST FAKE" in open(L.__file__).read() and "TEST FAKE" in open(W.__file__).read()
import sniper,common
from common import load
cfg=load("config.json");cfg["live_enabled"]=True;F=[]
def chk(c,m):print(("PASS " if c else "FAIL ")+m);c or F.append(m)
PR={"NEW":[{"priceUsd":"0.002","priceNative":"0.00001","quoteToken":{"symbol":"SOL"}}],   # SOL=$200
    "HELD":[{"priceUsd":"0.5","priceNative":"0.0025","quoteToken":{"symbol":"SOL"}}]}
sniper.pairs_for=lambda m:PR.get(m,[])
W.FAKE_BAL=2.0  # 2 SOL = $400
st={"bank":50,"open_positions":[{"mint":"HELD","live":True,"qty":200,"entry":0.4},{"mint":"PAPER","qty":999,"entry":1}],"watch":{},"death_watch":{}}
L.OK=True;L.CALLS.clear()
ok=sniper.buy({"lead_id":"X","mint":"NEW","symbol":"N"},st,cfg)
# total = 400 + 200*0.5=100 -> 500 ; size 50 ; lamports 50/200 SOL = 0.25 SOL
chk(ok is True,"buy returns True")
chk(L.CALLS and L.CALLS[-1][2]==250_000_000,"swap amount 0.25 SOL (10%% of $500 total, paper pos excluded): %s"%(L.CALLS[-1][2] if L.CALLS else None))
pos=st["open_positions"][-1];chk(pos["live"] and abs(pos["cost"]-50)<1e-9 and st["bank"]==50,"live pos cost $50, paper bank untouched")
chk(abs(st["live_last_total_usd"]-500)<1e-9,"live_last_total_usd recorded")
L.OK=False;n=len(st["open_positions"]);ok=sniper.buy({"lead_id":"Y","mint":"NEW","symbol":"N"},st,cfg)
chk(ok is False and len(st["open_positions"])==n,"failed live swap -> no position")
def boom(p):raise Exception("rpc down")
W.sol_balance=boom;ok=sniper.buy({"lead_id":"Z","mint":"NEW","symbol":"N"},st,cfg);chk(ok is False,"balance RPC error -> abort, no crash")
PR["USDQ"]=[{"priceUsd":"1","priceNative":"1","quoteToken":{"symbol":"USDC"}}];ok=sniper.buy({"lead_id":"Q","mint":"USDQ","symbol":"U"},st,cfg);chk(ok is False,"non-SOL quote -> abort")
cfg["live_enabled"]=False;st2={"bank":100,"open_positions":[]};ok=sniper.buy({"lead_id":"P","mint":"NEW","symbol":"N"},st2,cfg)
chk(ok and abs(st2["bank"]-90)<1e-9 and not st2["open_positions"][0].get("live"),"paper size min($10,10%) when live disabled")
print("FAILURES:",F);sys.exit(1 if F else 0)
