# Whale / smart-money tracking
- RPC: Helius when `HELIUS_API_KEY` is set (read from env at runtime, never printed/logged), else `WHALE_RPC` / public RPC.
- `build_wallets.py` MERGES (never overwrites): winners from DexScreener; early buyers via Helius enhanced API ascending order (first hour of any token reachable), fallback RPC paging (250 pages with Helius, 40 public). Excludes creation slot+1 (bundles) and deployer.
  Accumulates in `wallet_db.json`; already-scanned winners skipped unless `--rescan`. Active list in `wallets.json` = manual + wallets with >=2 distinct winners (`--min-hits`, floor 2). 1-hit wallets in `wallet_candidates.json`.
  Run: `python3 build_wallets.py [--max-tokens 60 --keep 50 --pages 8 --rescan]`.
- Manual wallets: add to `wallets.json` "wallets" as `{"address":"...","label":"phantom-x","source":"manual"}` - always active, kept by every rebuild.
- `whale.py`: derives each wallet's token account for the lead mint, batch `getMultipleAccounts` (100/call); holder whose account traded in last 2h => confirm (lists wallet + min ago). Any error => quiet.
- Caveat: early-buyer wallets hitting many unrelated winners are often sniper/MEV bots, not "smart money". Review the top list.
- Bot filter: wallets with >=1000 txs inside 24h excluded (6 of 12 removed; they 'confirmed' 8/11 random leads in a test scan).
