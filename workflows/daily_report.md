# Workflow: Morning Brief — Daily Financial Report

## Objective
Generate a comprehensive daily financial report every Mon-Fri and publish it to the GitHub Pages web page, ready to read at 8:00 AM CST.

## Inputs Required
- `ANTHROPIC_API_KEY` — set as GitHub Actions secret (and in `.env` for local testing)
- Today's date — injected automatically by the script

## Execution
```bash
python tools/generate_report.py
```
Runs automatically via GitHub Actions cron (`0 14 * * 1-5` = 8 AM CST Mon-Fri).

## What the Tool Does
1. Builds the Morning Brief prompt with today's date
2. Calls `claude-sonnet-4-6` with the `web_search_20250305` tool
3. Claude autonomously searches CNBC, Bloomberg, FT, Reuters, CoinDesk, El Financiero, etc.
4. Runs an agentic loop until Claude signals `end_turn`
5. Saves the Markdown report to `docs/reports/YYYY-MM-DD.json`
6. Updates `docs/reports/manifest.json` (list of all available dates for the archive)
7. GitHub Actions commits and pushes both files
8. GitHub Pages auto-serves the updated site

## Output
- `docs/reports/YYYY-MM-DD.json` — the day's report (Markdown in JSON)
- `docs/reports/manifest.json` — updated archive index

## Report Structure (6 sections)
1. 📊 Macro del Día — global markets, indices, headlines
2. 🏛️ Finanzas Institucionales — endowments, FIBRAs, PE/VC
3. 🎯 Empresa del Día — 10X/50X idea with investment thesis
4. 🪙 Crypto Pick del Día — BTC/ETH/SOL/XRP prices + altcoin pick
5. 🌎 Entorno Macroeconómico — Mexico 🇲🇽, USA 🇺🇸, Global 🌐
6. 🔮 Tendencias del Futuro — tech, AI, healthcare, civilization

## Sources
CNBC, Bloomberg, Yahoo Finance, Financial Times, WSJ, The Economist,
CoinDesk, Reuters, El Financiero, Banxico, IMF, TradingView,
The Medical Futurist, VML Research.

⚠️ Whitepaper.mx (https://www.whitepaper.mx/t/hoy) — included ONLY until April 7, 2026.
After that date, it is automatically excluded by the script's date check.

## Error Handling
- **Empty response**: Script exits with code 1, GitHub Actions marks the run as failed
- **API rate limit**: Anthropic handles retries internally; if persistent, check the Actions log and re-run manually
- **web_search failures**: Claude falls back to knowledge-based content with a disclaimer
- **Commit conflicts**: Should not occur since only the bot writes to `docs/reports/`

## Manual Trigger
Go to GitHub → Actions → "Morning Brief — Daily Report" → "Run workflow"

## Updating the Prompt
The prompt lives in `tools/generate_report.py` in the `PROMPT` constant.
Edit it there and commit to take effect on the next run.

## Adding New Sources
Add the source name/URL to the `PROMPT` constant in `tools/generate_report.py`.

## Timing Note
- Schedule: `0 14 * * 1-5` (UTC)
- Nov–Mar (CST, UTC-6): runs at 8:00 AM local
- Apr–Oct (CDT, UTC-5): runs at 9:00 AM local
- To always hit exactly 8 AM local, adjust the cron when DST changes.
