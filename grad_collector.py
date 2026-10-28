#!/usr/bin/env python3
"""Free fresh-graduation collector: PumpPortal public data websocket (subscribeMigration, no key, no spend).
Writes logs/grad_ws.json = {mint: migrated_unix_ts} (last 6h). search.py reads it. Reconnects with backoff. Read-only, never trades."""
import asyncio,json,time,os,websockets
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),"logs","grad_ws.json");KEEP=6*3600
def save(d):
    t=time.time();d={m:ts for m,ts in d.items() if t-ts<KEEP};tmp=OUT+".tmp";json.dump(d,open(tmp,"w"));os.replace(tmp,OUT);return d
async def run():
    try:d=json.load(open(OUT))
    except Exception:d={}
    back=5
    while True:
        try:
            async with websockets.connect("wss://pumpportal.fun/api/data",ping_interval=20) as ws:
                await ws.send(json.dumps({"method":"subscribeMigration"}));back=5
                async for msg in ws:
                    try:j=json.loads(msg)
                    except Exception:continue
                    m=j.get("mint")
                    if m and (j.get("txType")=="migrate" or j.get("pool") or "migrat" in str(j.get("txType","")).lower()):
                        d[m]=time.time();d=save(d);print(time.strftime("%H:%M:%S"),"grad",m,flush=True)
        except Exception as e:print("ws err",type(e).__name__,flush=True);await asyncio.sleep(back);back=min(back*2,300)
asyncio.run(run())
