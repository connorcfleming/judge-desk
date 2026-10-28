"""Lightweight PAPER exit loop: checks open positions only, every 60s. One DexScreener call per position per tick."""
import os,sys,time
from common import *
import exit as ex
pidf=P("logs/exit_watch.pid")
if os.path.exists(pidf):
    try:os.kill(int(open(pidf).read()),0);print("already running");sys.exit(0)
    except (OSError,ValueError):pass
open(pidf,"w").write(str(os.getpid()))
cfg=load("config.json")
while True:
    try:
        with Lock():
            st=load("state.json");n=len(st["open_positions"])
            if n:ex.manage(st,cfg);save("state.json",st)
        print(time.strftime("%F %T"),"checked",n,"open; bank",round(st["bank"],2),SRC.get("dexscreener_pairs"),flush=True)
    except Exception as e:print(time.strftime("%F %T"),"error",e,flush=True)
    time.sleep(20)
