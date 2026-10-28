"""Patch X mention counts into pending Jev requests.
Input pending/social_counts.json: {lead_id: {"now": int|null, "prev": int|null}} (null = lookup failed -> stays "missing").
now = posts in the last 60 min, prev = posts in the 60 min before that."""
import json,os
REQ="pending/jev_requests.json";SC="pending/social_counts.json"
if not (os.path.exists(REQ) and os.path.exists(SC)):print("nothing to inject");raise SystemExit
reqs=json.load(open(REQ));sc=json.load(open(SC));n=0
for r in reqs:
    c=sc.get(r["lead_id"]) or {}
    for k,f in (("now","social_mentions_hr_now"),("prev","social_mentions_hr_1h_ago")):
        v=c.get(k)
        if isinstance(v,int):
            r["dossier"][f]=v
            if r.get("call"):r["call"]["state"][f]=v
            n+=1
json.dump(reqs,open(REQ+".tmp","w"),indent=1);os.replace(REQ+".tmp",REQ);os.remove(SC)
print(f"injected {n} social fields")
