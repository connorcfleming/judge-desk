"""SIMULATED exit test. Run from a COPY of the desk whose wallet.py/live_exec.py are fakes (see AUDIT.md). Never sends."""
import sys,os,json,time
sys.path.insert(0,os.getcwd())
import live_exec as L
assert "TEST FAKE" in open(L.__file__).read(), "refusing: live_exec is not the fake"
import exit as ex
from common import load
cfg=load("config.json");cfg["live_enabled"]=True
F=[]
def chk(c,msg):
    print(("PASS " if c else "FAIL ")+msg);c or F.append(msg)
def mk(live=False,mint="M1"):
    p={"lead_id":"T-"+mint,"mint":mint,"symbol":"T","entry":1.0,"cost":1000,"qty":1000.0,"qty0":1000.0,"peak":1.0,"stage":0,"realized":0,"opened":time.time()}
    if live:p.update(live=True,raw_units=1_000_000)
    return {"bank":0.0,"open_positions":[p],"closed":[],"cooldown":{}},p
def tick(st,px):ex.manage(st,cfg,price_fn=lambda m:px)
# full ladder, paper
st,p=mk()
tick(st,1.2);chk(p["qty"]==1000 and p["stage"]==0,"no sell below +50")
tick(st,1.6);chk(abs(p["qty"]-500)<1e-9 and p["stage"]==1 and abs(st["bank"]-800)<1e-6,"half at +50 (qty 500, bank +800)")
tick(st,1.5);chk(p["qty"]==500,"no trail at 1.5 (peak1.6*0.8=1.28)")
tick(st,3.0);chk(abs(p["qty"]-400)<1e-9 and p["stage"]==2,"rung +200 sells 10% of ORIGINAL (100)")
tick(st,6.0);chk(abs(p["qty"]-300)<1e-9 and p["stage"]==3,"rung +500")
tick(st,11.0);chk(abs(p["qty"]-200)<1e-9 and p["stage"]==4,"rung +1000")
tick(st,21.0);chk(abs(p["qty"]-100)<1e-9 and p["stage"]==5,"rung +2000 -> moonbag 100 (10%)")
tick(st,30.0);chk(abs(p["qty"]-100)<1e-9,"moonbag: no more ladder sells")
tick(st,18.5);chk(abs(p["qty"]-100)<1e-9,"40% tier: 18.5 > 30*0.6=18 holds")
tick(st,17.9);chk(p["qty"]<=1e-9 and st["closed"] and "M1" in st["cooldown"] and not st["open_positions"],"moonbag trailing stop at 40% tier, closed, cooldown set")
# hard stop
st,p=mk(mint="M2");tick(st,0.71);chk(p["qty"]==1000,"no stop at -29%")
tick(st,0.70);chk(p["qty"]<=1e-9 and "M2" in st["cooldown"] and abs(st["bank"]-700)<1e-6,"hard stop -30% sells all + cooldown")
# 20% trail tier
st,p=mk(mint="M3");tick(st,1.55);tick(st,1.25);chk(p["qty"]==500,"20% trail holds at 1.25 (stop 1.24)")
tick(st,1.24);chk(p["qty"]<=1e-9 and "M3" in st["cooldown"],"20% trail fires at 1.24")
# 30% tier
st,p=mk(mint="M4");tick(st,1.6);tick(st,3.1);tick(st,2.2);chk(abs(p["qty"]-400)<1e-9,"30% tier holds at 2.2 (stop 2.17)")
tick(st,2.17);chk(p["qty"]<=1e-9,"30% tier fires at 2.17")
# gap straight to +2400 in one tick
st,p=mk(mint="M5");tick(st,25.0);chk(abs(p["qty"]-100)<1e-9 and p["stage"]==5,"one-tick gap: half + all 4 rungs, 100 left")
# LIVE mocked ok
st,p=mk(live=True,mint="L1");L.OK=True;L.CALLS.clear()
tick(st,1.6);chk(abs(p["qty"]-500)<1e-9 and st["bank"]==0 and L.CALLS and L.CALLS[-1][2]==500000,"live half: qty decremented, bank untouched (live), raw 500000")
tick(st,3.0);chk(abs(p["qty"]-400)<1e-9 and L.CALLS[-1][2]==100000,"live rung: raw 100000 = 10% of original")
# LIVE failed sell
L.OK=False;n=len(L.CALLS);tick(st,6.0);chk(abs(p["qty"]-400)<1e-9 and p["stage"]==2 and len(L.CALLS)==n+1,"live FAILED sell: qty and stage unchanged")
L.OK=True;tick(st,6.0);chk(abs(p["qty"]-300)<1e-9 and p["stage"]==3,"live retry next tick succeeds")
L.OK=False;tick(st,0.5);chk(abs(p["qty"]-300)<1e-9 and "L1" not in st["cooldown"] and st["open_positions"],"live FAILED hard stop: qty unchanged, no cooldown, still open")
L.OK=True;tick(st,0.5);chk(p["qty"]<=1e-9 and "L1" in st["cooldown"] and L.CALLS[-1][2]==300000,"live hard stop retry sells remaining raw 300000")
chk(all(c[3] is True for c in L.CALLS),"(mock recorded send=True calls; nothing real sent - fake module)")
# failed half sell must not arm ladder skip
st,p=mk(live=True,mint="L2");L.OK=False;tick(st,1.6);chk(p["stage"]==0 and p["qty"]==1000,"live failed half: stage stays 0")
print("FAILURES:",F);sys.exit(1 if F else 0)
