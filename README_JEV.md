# Jev judge — two-phase scan (PAPER ONLY)

The judge is Jev (TypeSafe AI) via the Composio MCP connector. The old rule judge
(`judge_rules_dryrun.py`) is kept only for comparison logs (`logs/judge_dryrun.jsonl`); it never decides.

## Every scan (routine run)
1. `cd /workspace/judge-desk && python3 run_scan.py phase1`
   - runs exits + 24h death check, search, RISK, WHALE
   - judges ONLY RISK-clean leads; skips held tokens (never re-judged) and watch leads inside 30 min
   - checks the $1/day Jev cap (`jev_spend.json`); blocked leads get `call: null`
   - writes `pending/jev_requests.json` (list of {lead_id, call, dossier})
2. For each request whose `call` is not null, ONE call per lead (all 4 questions batched):
   - namespace `user-Composio`, tool `COMPOSIO_MULTI_EXECUTE_TOOL`, session_id `hold`
   - tools: `[{"tool_slug":"JEV_EVALUATE_STATE","arguments": <request.call verbatim>}]`
     (model `jev-latest`, state = dossier, questions = `jev_questions.json`; do not edit wording)
   - Up to 50 leads may be batched in one MULTI_EXECUTE call (still one Jev call per lead).
3. Write `pending/jev_responses.json` = `{ "<lead_id>": <response.data verbatim> }`
   (the object with `answers`, `usage`, `model`). On error/timeout, omit the lead or write null.
   Do NOT invent answers; do NOT use the rule judge.
4. `python3 run_scan.py phase2` — records spend from `usage.input_tokens`, maps to option+probability,
   logs raw response, gates, paper-fills. Missing/failed Jev answer = pass.
If `jev_requests` is 0 in phase1 output, skip step 2-3 and run phase2 anyway (it closes the batch).

## Mapping
organic/late: noul>=0.5 -> yes, p=max(noul,1-noul). exit_risk: argmax of score probabilities (index 0..4 -> 1..5).
action: argmax of choice probabilities. Gate thresholds are unchanged (gate.py).

## Spend
Counter `jev_spend.json` resets daily; priced conservatively at $0.42/M input tokens
(docs.typesafe.ai lists $0.042/M). Halts Jev calls once projected spend would exceed $1.00/day.
Exit loop: `exit_watch.py` (pid in logs/exit_watch.pid) is independent of this flow.

## Audit changes (2026-10-28)
- Watch re-ask: due at >=28 min (2-min grace for 15-min scans); due watches are re-asked even if search doesn't surface them; second watch = pass; a watch not re-askable for 3h = pass (logged).
- A passed mint is not re-asked for 24h (it sits in death_watch; 24h check logs dead + green_24h to logs/death_check.jsonl).
- Dossier: holders_1h_ago / buys_sells_prev_m5 come from logs/snapshots.json when a snapshot ~1h / ~5min old exists, else "missing". Social mentions always "missing" (no free source).
- Reports: `python3 report.py [YYYY-MM-DD]` (9 PM), `python3 calibrate.py [days]` (Sunday).
