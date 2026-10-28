from common import *
def gate(lid,a,cfg,state):
    g=cfg["gate"];act=a.get("action",{})
    if act.get("option")=="buy":
        kill=None
        if act.get("p",0)<g["buy_p"]:kill=("action",act)
        elif not(a["organic"]["option"]=="yes" and a["organic"]["p"]>=g["organic_p"]):kill=("organic",a["organic"])
        elif a["late"]["option"]!="no":kill=("late",a["late"])
        elif a["exit_risk"]["option"]>g["max_exit_risk"]:kill=("exit_risk",a["exit_risk"])
        dec="buy" if not kill else "pass"
    elif act.get("option")=="watch":
        k=lid.split("-")[0]
        if k in state["watch"] and state["watch"][k].get("asked",0)>=1:dec,kill="pass",("action","second watch")
        else:dec,kill="watch",None
    else:dec,kill="pass",("action",act)
    out={"lead_id":lid,"decision":dec,"killed_by":kill};log("gate",out);return dec
