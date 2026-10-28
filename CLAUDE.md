# CLAUDE.md — operating rules for this desk

This desk trades real money from a burner wallet. Follow these rules exactly.

1. **Never change the gate, sizing, or exits** (`gate.py`, `sniper.py`, `exit.py`, `config.json` gate/trade/exits/live keys)
   without Connor's approval **in writing**. Bug fixes that change behavior count as changes.
2. **Never print, log, echo, or commit keys** (`SOLANA_BURNER_PRIVATE_KEY`, `HELIUS_API_KEY`, `BIRDEYE_API_KEY`, `.env`,
   key files). Don't `cat .env`, don't `env | grep`. Keys come from the environment only.
3. **Jev cap: $1.00/day** (enforced by `jev.py` / `jev_spend.json`). Don't raise it or bypass it.
4. **Any spend > $1** (API plans, deposits, top-ups, larger trades, anything) needs Connor's OK first.
5. **The Jev step happens via the Composio MCP between phase1 and phase2**: run `run_scan.py phase1`, call
   `JEV_EVALUATE_STATE` through `COMPOSIO_MULTI_EXECUTE_TOOL` for each request with `call` verbatim, write
   `pending/jev_responses.json`, then `run_scan.py phase2`. Never fabricate answers or use the rule judge to decide;
   missing/failed answers mean pass. Don't edit `jev_questions.json`.
6. Don't run two copies of a background loop; check `logs/*.pid` first. Don't delete `state.json` or logs.
7. Viewers (`watch_scanner.py`, `ui/`, `export_snapshot.py`) are read-only — keep them that way.
8. Never commit `state.json`, `logs/`, `pending/`, `.env`, wallet DBs, or `*.bak*` (see `.gitignore`).
