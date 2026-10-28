# Judge Desk — live Solana meme-coin desk

A small Python desk that scans fresh Solana meme coins, filters them, asks the **Jev** judge (TypeSafe AI, via the
Composio MCP) four fixed questions, applies a **fixed gate**, sizes small, and manages exits. It trades from a
**burner wallet** (live execution via Jupiter, `live_exec.py`); paper positions stay paper.

Pipeline: `search` (DexScreener boosts/profiles/PumpSwap, PumpPortal migrations from `grad_collector.py`) → `risk`
(RugCheck: authorities, LP, top10/dev, bundles/insiders) → `whale` (tracked smart wallets, Helius RPC) → **Jev** →
`gate.py` (buy_p / organic_p / max_exit_risk in `config.json`) → `sniper.py` → `exit.py` (take half at +50%, ladder,
tiered trailing stop, −30% hard stop). Details: `README_JEV.md`, `README_WHALE.md`, `AUDIT.md`. Operating rules: `CLAUDE.md`.

## Setup
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # fill in; never commit .env
set -a; . ./.env; set +a
mkdir -p logs pending
```
Keys are read from the environment only: `SOLANA_BURNER_PRIVATE_KEY`, `HELIUS_API_KEY`, `BIRDEYE_API_KEY`
(or `BIRDEYE_KEY_FILE`). `state.json` is created by the desk on first run (not in git).

## Run a scan (every ~15 min)
1. `python3 run_scan.py phase1` → writes `pending/jev_requests.json`.
2. **Jev step (Claude Code, Composio MCP):** for each request with non-null `call`, call `COMPOSIO_MULTI_EXECUTE_TOOL`
   with tool `JEV_EVALUATE_STATE` and `request.call` verbatim; write `pending/jev_responses.json`
   = `{lead_id: response.data}`. Errors → omit/null. Never invent answers. See `README_JEV.md`.
3. `python3 run_scan.py phase2` → spend accounting, gate, sniper (always run it, even with 0 requests).

## Background loops
```bash
nohup python3 exit_watch.py         >> logs/exit_watch.out 2>&1 &
nohup python3 grad_collector.py     >> logs/grad_collector.out 2>&1 &
nohup python3 snapshot_collector.py >> logs/snapshot_collector.out 2>&1 &
```
Each writes a pid file in `logs/` and refuses to double-start.

## Viewing (all read-only)
- Terminal live view: `python3 watch_scanner.py --dir .` (`--once`, `--interval 3`, `--no-price`, `--plain`).
- Web UI: `python3 ui/server.py --dir . --port 8787` → http://127.0.0.1:8787 (binds localhost only; `/api/snapshot` JSON).
- JSON summary: `python3 export_snapshot.py --dir . [--out snap.json]`.
Prices for open-position PnL come from the free public DexScreener API (disable with `--no-price`).

## Tests
`python3 tests/test_exit_sim.py`, `tests/test_phase2_sim.py`, `tests/test_sniper_sim.py` (simulations, no network trades).
