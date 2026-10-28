# AUDIT 2026-10-28 (afternoon, ET)
Backups: every edited file has `<file>.bak_audit` (common, exit, exit_watch(unchanged), gate(unchanged), judge_rules_dryrun, judge_core, run_scan, search, sniper, whale, build_wallets, wallets.json). State snapshot before edits: /tmp/state.snapshot_audit.json.
Tests: tests/*.py run ONLY in a desk copy (/tmp/deskT) whose wallet.py/live_exec.py are fakes (tests assert "TEST FAKE"). No key read, nothing sent.

## Findings / fixes
- common.save: non-atomic -> now tmp+os.replace (state.json can't be half-written if killed).
- exit.py: stage advanced even when a LIVE sell failed (half/rung silently skipped). Now sell() returns bool; stage only advances on fill; failed rung stops ladder for that tick; qty/cooldown untouched on failure. Trail armed by stage>=1 OR peak>=+50. Live pos with live disabled no longer "paper-sold". Log label LIVE_SELL vs PAPER_SELL, qty_left, closed_ts. price_fn injectable for tests. Rules unchanged.
- exit_watch restarted cleanly 15:24 (old pid 51298 -> new pid in logs/exit_watch.pid).
- sniper.py: returns True/False; RPC balance error no longer crashes phase2 inside the lock; logs SOL bal/price; stores live_last_total_usd (for dossier size). Sizing rule unchanged.
- run_scan.py: watch grace 2 min (30-min re-ask was slipping to 45 with 15-min scans); due watches re-asked even if search doesn't surface them; watches un-askable 3h -> pass logged; passed mints not re-asked for 24h (never re-ask for a different answer; previously same mint re-judged every scan); buy-when-held no longer falls into pass/death_watch; death_check no longer marks dead on API error, records price_then/now, chg_24h, green_24h; judge log carries mint/symbol/price; dossier size = live estimate when live; requests written atomically.
- dossier: holders_1h_ago + buys_sells_prev_m5 from logs/snapshots.json (snapshots.py); WHALE now includes which wallets + minutes ago; social = "missing" (no free source).
- search.py: age 0 -> None bug; backoff counter never reset; added lead_for_mint().
- judge_core (dry-run only): tolerate "missing" size.
- whale.py: Helius RPC if HELIUS_API_KEY (never logged), ATA derivation + batched getMultipleAccounts (~1-2 credits/lead), manual wallets always first/active, fail-safe quiet.
- build_wallets.py: Helius enhanced API ascending order (first hour reachable), RPC fallback paging cap 40->250 pages with Helius; MERGE via wallet_db.json; min_hits>=2 enforced; 1-hit -> wallet_candidates.json; manual entries preserved.
- report.py / calibrate.py added.
- build_wallets: bot filter (>=1000 tx/24h). Rebuild 15:40: 8 winners scanned (DexScreener winner filter only yields 8), 212 wallets in db, 200 one-hit candidates, 12 with >=2 hits, 6 bots excluded -> 6 active (all 2 hits).

## Tests (in /tmp/deskT copy, fakes): test_exit_sim 25/25 PASS, test_sniper_sim 8/8 PASS, test_phase2_sim 15/15 PASS (25 leads, gate kills, watch x2, cooldown, Jev failure, $1 cap). phase1 on copy: 25 leads, ~16-19s.

## Open / for Connor
- live_enabled=true: the next Jev buy that clears the gate spends real SOL (10% of portfolio, no $ cap). Intended per spec; confirm.
- buys_sells_prev_m5 only when a ~5-min-old snapshot exists (rare with 15-min scans). Exact fix = 5-min wait in phase1 or a 5-min snapshotter; not done.
- Social mentions: no free source -> "missing".
- Passed mints now not re-asked for 24h (my reading of "never re-ask"); revert = PASS_NO_REASK_S=0 in run_scan.py.
- Whale list is thin/early; HELIUS_API_KEY must be in the routine's env or whale/build fall back to public RPC.
- LIVE position raw_units = Jupiter quote outAmount, not actual received; partial sells are proportional to that.
