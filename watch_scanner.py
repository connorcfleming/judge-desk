#!/usr/bin/env python3
"""Live, read-only terminal dashboard for the desk. Tails logs/*.jsonl, exit_watch.out, grad_ws.json, state.json.
  python3 watch_scanner.py --dir /path/to/desk [--interval 3] [--once] [--no-price]
Uses `rich` if installed, else plain ANSI. Never writes, never reads keys."""
import argparse,os,sys,time
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import deskdata
ap=argparse.ArgumentParser();ap.add_argument("--dir",default=".");ap.add_argument("--interval",type=float,default=3)
ap.add_argument("--once",action="store_true");ap.add_argument("--no-price",action="store_true");ap.add_argument("--plain",action="store_true")
a=ap.parse_args()
try:
    if a.plain:raise ImportError
    from rich.console import Console,Group;from rich.table import Table;from rich.live import Live;from rich.panel import Panel;RICH=True
except ImportError:RICH=False
def n(v,f="{:,.0f}"):
    try:return f.format(v)
    except Exception:return "-"
def hhmm(ts):return str(ts or "")[11:19]
G,R,Y,C,D,B,X="\033[32m","\033[31m","\033[33m","\033[36m","\033[2m","\033[1m","\033[0m"
def col(v):
    v=str(v or "-");return (G if v in("clean","confirm","buy") else R if v in("dead","pass","kill") else Y if v in("watch","quiet") else "")+v+X
def rows(s):
    f=s["funnel"];j=s["jev_spend"]
    head=f"Judge desk  {s['now']}  bank ${n(s['bank'],'{:.2f}')}  watch {s['watch_n']}  Jev today ${n(j.get('usd'),'{:.4f}')}/{j['cap_usd']:.2f} ({j.get('calls') or 0} calls)"
    fun="FUNNEL today: "+"  ".join(f"{k}={v}" for k,v in f.items())
    loops="LOOPS: "+"  ".join(f"{k}:{'up '+str(v['pid']) if v['pid'] else ('-' if k.endswith('.json') else 'DOWN')} ({v['log_age_s']}s)" for k,v in s["loops"].items())
    feed=[[hhmm(x["ts"]),x["symbol"] or "?",x["mint"],n(x["age_h"],"{:.1f}h"),n(x["mcap"]),n(x["liq"]),"Q" if x["qualified"] else ".",",".join(x["sources"])[:38],
           x["risk"] or "-",",".join(x["risk_fails"] or [])[:28],x["whale"] or "-",x["gate"] or "-",x["killed_by"] or ""] for x in s["feed"][:18]]
    jt=[[hhmm(x["ts"]),x["symbol"] or "?",f"{x['action']} {n(x['action_p'],'{:.2f}')}",f"{x['organic']} {n(x['organic_p'],'{:.2f}')}",str(x["late"]),str(x["exit_risk"]),x["gate"] or "-",x["killed_by"] or ""] for x in s["judge"][:8]]
    wh=[[hhmm(x["ts"]),str(x["symbol"]),x["result"] or "-",str(x["hits"]),str(x["checked"]),x["rpc"] or ""] for x in s["whales"][:6]]
    ps=[[x["symbol"] or "?",x["mint"],n(x["entry"],"{:.6g}"),n(x["price"],"{:.6g}"),n(x["pnl_pct"],"{:+.1f}%"),n(x["pnl_usd"],"{:+.2f}"),n(x["peak_pct"],"{:+.1f}%"),str(x["stage"]),f"{x['held_min']}m"] for x in s["positions"]]
    tr=[[hhmm(x["ts"]),x["event"] or "",x["symbol"] or str(x["lead_id"])[:12],x["why"] or "",n(x["price"],"{:.6g}"),n(x["usd"],"{:.2f}")] for x in s["trades"][:6]]
    return head,fun,loops,feed,jt,wh,ps,tr
H=dict(feed=["time","sym","mint","age","mcap","liq","Q","source","RISK","kill reason","WHALE","GATE","killed_by"],
  jt=["time","sym","action","organic","late","exit_risk","GATE","killed_by"],wh=["time","sym","result","hits","checked","rpc"],
  ps=["sym","mint","entry","now","PnL%","PnL$","peak","stage","held"],tr=["time","event","sym","why","price","usd"])
def render_rich(s):
    head,fun,loops,feed,jt,wh,ps,tr=rows(s)
    def T(t,h,r,c={}):
        tb=Table(title=t,expand=True,header_style="bold cyan",title_justify="left")
        for x in h:tb.add_column(x,no_wrap=True,overflow="ellipsis")
        for row in r:tb.add_row(*[f"[{'green' if v in('clean','confirm','buy') else 'red' if v in('dead','pass') else 'yellow' if v in('watch','quiet') else 'white'}]{v}" for v in row])
        return tb
    tail="\n".join(s["exit_watch_tail"][-2:])
    return Group(Panel(f"[bold]{head}[/]\n{fun}\n{loops}\n[dim]{tail}[/]"),T("LEADS (newest first)",H["feed"],feed),T("JEV / GATE",H["jt"],jt),
                 T("WHALE",H["wh"],wh),T("OPEN POSITIONS",H["ps"],ps),T("RECENT TRADES",H["tr"],tr))
def table_plain(title,h,r):
    w=[max(len(str(x)) for x in [h[i]]+[row[i] for row in r]) for i in range(len(h))]
    out=[f"{B}{C}{title}{X}","  ".join(f"{B}{h[i]:<{w[i]}}{X}" for i in range(len(h)))]
    for row in r:out.append("  ".join(col(v)+" "*(w[i]-len(str(v))) if v in("clean","dead","confirm","quiet","buy","watch","pass") else f"{str(v):<{w[i]}}" for i,v in enumerate(row)))
    return "\n".join(out)
def render_plain(s):
    head,fun,loops,feed,jt,wh,ps,tr=rows(s)
    return "\n\n".join([f"{B}{head}{X}\n{fun}\n{loops}\n{D}"+"\n".join(s["exit_watch_tail"][-2:])+X,table_plain("LEADS (newest first)",H["feed"],feed),
        table_plain("JEV / GATE",H["jt"],jt),table_plain("WHALE",H["wh"],wh),table_plain("OPEN POSITIONS",H["ps"],ps),table_plain("RECENT TRADES",H["tr"],tr)])
seen=set()
def snap():
    s=deskdata.snapshot(a.dir,live_price=not a.no_price)
    for x in s["feed"]:x["_new"]=x["lead_id"] not in seen;seen.add(x["lead_id"])
    return s
if RICH and not a.once:
    with Live(render_rich(snap()),refresh_per_second=2,screen=True) as lv:
        while True:time.sleep(a.interval);lv.update(render_rich(snap()))
elif RICH:Console().print(render_rich(snap()))
else:
    while True:
        out=render_plain(snap())
        if a.once:print(out);break
        sys.stdout.write("\033[H\033[2J"+out+"\n");sys.stdout.flush();time.sleep(a.interval)
