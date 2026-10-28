"""phase2 with 25 synthetic requests + fake Jev responses, in a desk COPY (fake wallet/live_exec). Checks gate, watch, cooldown, cap."""
import sys,os,json,time;sys.path.insert(0,os.getcwd())
import live_exec as L;assert "TEST FAKE" in open(L.__file__).read()
assert os.getcwd()!="/workspace/judge-desk"
import run_scan as R,jev,sniper
from common import load,save,P
F=[]
def chk(c,m):print(("PASS " if c else "FAIL ")+m);c or F.append(m)
def raw(org,late,er,act):
    e={str(i):0.01 for i in range(5)};e[str(er-1)]=0.96
    a={"buy":0.05,"watch":0.05,"pass":0.05};a[act[0]]=act[1]
    return {"answers":{"organic":{"noul":org},"late":{"noul":late},"exit_risk":{"probabilities":e},"action":{"probabilities":a}},"usage":{"input_tokens":1000},"model":"fake"}
st=load("state.json");st.update(open_positions=[],watch={},death_watch={},cooldown={"COOLMINT":time.time()-3600});save("state.json",st)
sniper.pairs_for=lambda m:[{"priceUsd":"0.01","priceNative":"0.00005","quoteToken":{"symbol":"SOL"}}]
reqs=[];res={}
for i in range(25):
    m=f"MINT{i:02d}xxxxxxxx";reqs.append({"lead_id":f"{m[:8]}-1","mint":m,"symbol":f"S{i}","price_usd":0.01,"call":{"x":1},"dossier":{"liquidity_usd":50000}})
res["MINT00xx-1"]=raw(0.80,0.2,2,("buy",0.75))     # passes gate
res["MINT01xx-1"]=raw(0.60,0.2,2,("buy",0.75))     # organic p 0.60 <0.65 -> pass
res["MINT02xx-1"]=raw(0.80,0.6,2,("buy",0.75))     # late yes -> pass
res["MINT03xx-1"]=raw(0.80,0.2,4,("buy",0.75))     # exit 4 -> pass
res["MINT04xx-1"]=raw(0.80,0.2,2,("buy",0.69))     # buy p .69 -> pass
res["MINT05xx-1"]=raw(0.80,0.2,2,("watch",0.6))    # watch
res["MINT06xx-1"]=None                              # jev failed
for i in range(7,25):res[f"MINT{i:02d}xx-1"]=raw(0.5,0.5,3,("pass",0.8))
reqs.append({"lead_id":"COOLMINT-1","mint":"COOLMINT","symbol":"C","price_usd":0.01,"call":{"x":1},"dossier":{"liquidity_usd":1}})
res["COOLMINT-1"]=raw(0.9,0.1,1,("buy",0.9))
json.dump(reqs,open(R.REQ,"w"));json.dump(res,open(R.RES,"w"))
s0=jev.spend()["calls"];R.phase2();st=load("state.json")
g={}
for x in open(P("logs/gate.jsonl")):
    x=json.loads(x);g[x["lead_id"]]=x
chk(any(p["mint"]=="MINT00xxxxxxxx" for p in st["open_positions"]),"gate-passing buy executed (mock live)")
for i,why in [(1,"organic"),(2,"late"),(3,"exit_risk"),(4,"action")]:
    chk(g[f"MINT0{i}xx-1"]["decision"]=="pass" and g[f"MINT0{i}xx-1"]["killed_by"][0]==why,f"pass killed_by {why}")
chk("MINT05xx" in st["watch"] and st["watch"]["MINT05xx"]["asked"]==1,"watch recorded asked=1")
chk(g["MINT06xx-1"]["killed_by"][0]=="judge_failure","jev failure -> pass")
chk(g["COOLMINT-1"]["killed_by"][0]=="cooldown_after_stop" and not any(p["mint"]=="COOLMINT" for p in st["open_positions"]),"cooldown blocks rebuy")
chk(len(st["death_watch"])==24-0 and st["death_watch"]["MINT07xxxxxxxx"]["price"]==0.01,"passes tracked in death_watch with price (%d)"%len(st["death_watch"]))
chk(jev.spend()["calls"]-s0==25,"spend recorded for 25 answered calls")
chk(not os.path.exists(R.REQ) and os.path.exists(R.REQ+".done"),"batch closed")
# second ask of watch -> watch again => pass
st["watch"]["MINT05xx"]["t"]-=31*60;save("state.json",st)
json.dump([reqs[5]],open(R.REQ,"w"));json.dump({"MINT05xx-1":raw(0.8,0.2,2,("watch",0.6))},open(R.RES,"w"));R.phase2();st=load("state.json")
g=[json.loads(x) for x in open(P("logs/gate.jsonl"))][-1]
chk(g["killed_by"]==["action","second watch"] and "MINT05xx" not in st["watch"],"second watch -> pass")
# cap
s=jev.spend();s["usd"]=0.9999;save("jev_spend.json",s);chk(not jev.can_call(0),"cap: blocked when projected > $1")
s["usd"]=0.5;save("jev_spend.json",s);chk(jev.can_call(24),"cap: 25 calls allowed at $0.50")
print("FAILURES:",F);sys.exit(1 if F else 0)
