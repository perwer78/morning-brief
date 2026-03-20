"""
Morning Brief — Daily Financial Report Generator
Calls Claude API with web_search tool to generate the report and saves it as JSON.
Run: python tools/generate_report.py
"""

import os
import sys
import json
import time
from datetime import datetime, date
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

# ── Constants ──────────────────────────────────────────────────────────────────

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16000
REPORTS_DIR = Path(__file__).parent.parent / "docs" / "reports"

# Whitepaper.mx source expires April 7 2026
WHITEPAPER_ACTIVE = date.today() <= date(2026, 4, 7)

WHITEPAPER_INSTRUCTION = (
    "- Include https://www.whitepaper.mx/t/hoy as a source (paid subscription, access it)."
    if WHITEPAPER_ACTIVE
    else ""
)

PROMPT = f"""Today is {date.today().strftime('%A, %B %d, %Y')}.

Generate the complete "Morning Brief" daily financial report for an endowment fund manager.
Search the web for today's latest news before writing each section. Use reliable sources:
CNBC, Bloomberg, Yahoo Finance, Financial Times, WSJ, The Economist, CoinDesk, Reuters,
El Financiero, Banxico, IMF, TradingView, The Medical Futurist, VML Research.
{WHITEPAPER_INSTRUCTION}

OUTPUT FORMAT: Return the full report in Markdown. Use the exact structure below.

---

# 🌅 Morning Brief — {date.today().strftime('%A %d de %B, %Y')}
*Generado para: Fund Manager | Tiempo de lectura: 5-7 min*

---

## 📊 1. Macro del Día

[5-6 bullet points: global markets, major indices with % changes, financial headlines, geopolitical events affecting markets. Include specific numbers.]

---

## 🏛️ 2. Finanzas Institucionales

[2-3 items on institutional finance, endowments, capital markets, FIBRAs, PE/VC. Use tables when comparing data.]

---

## 🎯 3. Empresa del Día — Idea 10X/50X

[Research one public or private company with high-growth potential. Format as a structured card:]

**Empresa:** [Name] | **Sector:** [Sector] | **Mercado:** [Exchange/Private]
**Cap. Mercado:** [Market cap] | **Riesgo:** 🔴/🟠/🟡 [level]

**Tesis de Inversión:**
[2-3 paragraphs on why this company, catalysts, growth potential]

**Riesgos Principales:**
- [Risk 1]
- [Risk 2]
- [Risk 3]

> ⚠️ Esto NO es una recomendación de inversión. Solo para fines informativos y educativos.

---

## 🪙 4. Crypto Pick del Día

[Table with today's prices for BTC, ETH, SOL, XRP + one more top-5 coin]

**Altcoin Pick:**
[One altcoin outside top 5 with tesis and risk assessment. Reference RWA narrative when relevant.]

---

## 🌎 5. Entorno Macroeconómico

**México 🇲🇽**
[Peso/USD rate, Banxico rate decisions, inflation data, key economic news]

**EE.UU. 🇺🇸**
[Fed policy, employment, inflation (PCE/CPI), equity market conditions]

**Global 🌐**
[IMF projections, geopolitical impacts, commodity prices: oil (WTI/Brent) and gold]

---

## 🔮 6. Tendencias del Futuro

[3-4 trends covering: emerging tech, AI applications, healthcare/longevity, civilization shifts.
Use a table when showing multiple trends side by side. Connect each trend to investment implications.]

---

*Fuentes utilizadas: [list all sources with URLs]*
*Reporte generado: {datetime.now().strftime('%Y-%m-%d %H:%M')} CST*
"""

# ── Main ───────────────────────────────────────────────────────────────────────

def generate_report() -> str:
    """Run the Morning Brief prompt through Claude with web_search. Returns Markdown string."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in environment or .env file.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    messages = [{"role": "user", "content": PROMPT}]
    tools = [{"type": "web_search_20250305", "name": "web_search"}]

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Calling Claude API (model: {MODEL})...")

    # Agentic loop — Claude may do multiple web searches before finishing
    iterations = 0
    while True:
        iterations += 1
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Iteration {iterations}...")

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            tools=tools,
            messages=messages,
        )

        # Collect text blocks for final output
        text_blocks = [b.text for b in response.content if hasattr(b, "text")]

        if response.stop_reason == "end_turn":
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Done after {iterations} iteration(s).")
            return "\n".join(text_blocks)

        if response.stop_reason == "tool_use":
            # Add assistant turn to conversation
            messages.append({"role": "assistant", "content": response.content})

            # Build tool_result blocks for each tool_use block
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  → web_search: {getattr(block, 'input', {}).get('query', '(query)')}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "",  # Server-side tool: Anthropic handles the result
                    })

            messages.append({"role": "user", "content": tool_results})
            time.sleep(0.5)  # brief pause between iterations
            continue

        # Unexpected stop reason — return whatever text we have
        print(f"WARNING: Unexpected stop_reason '{response.stop_reason}'", file=sys.stderr)
        return "\n".join(text_blocks) if text_blocks else ""


def save_report(content: str) -> Path:
    """Save report as JSON to docs/reports/YYYY-MM-DD.json and update manifest."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    output_path = REPORTS_DIR / f"{today}.json"

    payload = {
        "date": today,
        "generated_at": datetime.now().isoformat(),
        "content": content,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Report saved → {output_path}")

    # Update manifest.json — sorted newest-first list of all report dates
    manifest_path = REPORTS_DIR / "manifest.json"
    existing = []
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []

    if today not in existing:
        existing.insert(0, today)
        existing.sort(reverse=True)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Manifest updated ({len(existing)} entries).")
    return output_path


if __name__ == "__main__":
    report_md = generate_report()
    if not report_md.strip():
        print("ERROR: Empty report returned by Claude.", file=sys.stderr)
        sys.exit(1)
    save_report(report_md)
    print("✅ Morning Brief generated successfully.")
