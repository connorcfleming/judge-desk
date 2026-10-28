"""Jev judge helpers. Decisions come ONLY from Jev; any failure => pass."""
import json,time
from common import *
MODEL="jev-latest"
RATE_PER_TOK=0.42e-6   # conservative: highest published rate ($0.42/M); docs.typesafe.ai lists $0.042/M
DAILY_CAP=1.00
EST_TOKENS=1000        # per call estimate for pre-call budget check (test call used 901)
Q=json.load(open(P("jev_questions.json")))
def spend():
    try:s=load("jev_spend.json")
    except Exception:s={}
    d=time.strftime("%F")
    if s.get("date")!=d:s={"date":d,"calls":0,"input_tokens":0,"usd":0.0}
    return s
def can_call(n_reserved=0):return spend()["usd"]+(n_reserved+1)*EST_TOKENS*RATE_PER_TOK<=DAILY_CAP
def record(tokens):
    s=spend();s["calls"]+=1;s["input_tokens"]+=tokens;s["usd"]=round(s["input_tokens"]*RATE_PER_TOK,6);save("jev_spend.json",s);return s
def call_args(d):return {"model":MODEL,"state":d,"questions":Q}
def map_answers(raw):
    """raw = JEV_EVALUATE_STATE data {answers,usage,model}. Returns option+probability or None."""
    try:
        a=raw["answers"]
        o=a["organic"]["noul"];l=a["late"]["noul"]
        er=a["exit_risk"]["probabilities"];k=max(er,key=lambda x:er[x])
        ac=a["action"]["probabilities"];c=max(ac,key=lambda x:ac[x])
        return {"organic":{"option":"yes" if o>=0.5 else "no","p":round(max(o,1-o),3)},
                "late":{"option":"yes" if l>=0.5 else "no","p":round(max(l,1-l),3)},
                "exit_risk":{"option":int(k)+1,"p":round(er[k],3)},
                "action":{"option":c,"p":round(ac[c],3)}}
    except Exception:return None
