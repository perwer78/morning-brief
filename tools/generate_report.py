"""
Morning Brief — Daily Financial Report Generator
Uses Tavily (web search) + Groq (LLM) to generate the report and saves it as JSON.
Both are free tier — no credit card needed.
Run: python tools/generate_report.py
"""

import os
import sys
import json
from datetime import datetime, date
from pathlib import Path

import time
import requests
from tavily import TavilyClient
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ── Constants ──────────────────────────────────────────────────────────────────

# Fallback list if the API query fails
FALLBACK_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "google/gemma-3-27b-it:free",
    "google/gemma-3-4b-it:free",
    "microsoft/phi-4-mini-instruct:free",
]
REPORTS_DIR = Path(__file__).parent.parent / "docs" / "reports"

# Whitepaper.mx source expires April 7 2026
WHITEPAPER_ACTIVE = date.today() <= date(2026, 4, 7)

TODAY = date.today().strftime("%A, %B %d, %Y")
TODAY_ES = date.today().strftime("%A %d de %B, %Y")

# Targeted search queries — one per report section
SEARCH_QUERIES = [
    f"global stock markets indices performance {date.today().isoformat()}",
    f"Mexico economy peso banxico interest rates {date.today().isoformat()}",
    f"US Federal Reserve inflation employment data {date.today().isoformat()}",
    f"cryptocurrency bitcoin ethereum solana XRP prices {date.today().isoformat()}",
    f"institutional finance endowment PE VC capital markets news {date.today().isoformat()}",
    f"emerging technology AI healthcare longevity investment trends {date.today().isoformat()}",
    f"high growth company 10x potential stock market {date.today().isoformat()}",
]

if WHITEPAPER_ACTIVE:
    WHITEPAPER_NOTE = "- Whitepaper.mx (https://www.whitepaper.mx/t/hoy) is a source (paid subscription)."
else:
    WHITEPAPER_NOTE = ""

PROMPT_TEMPLATE = """Today is {today}.

You are preparing the "Morning Brief" daily financial report for an endowment fund manager.
Below are today's fresh news gathered from the web. Use these as your PRIMARY sources and cite URLs.
Additional sources to reference when relevant: CNBC, Bloomberg, Yahoo Finance, Financial Times,
WSJ, The Economist, CoinDesk, Reuters, El Financiero, Banxico, IMF, TradingView.
{whitepaper_note}

=== TODAY'S NEWS (web search results) ===
{news_context}
===========================================

Generate the complete Morning Brief in Markdown with this EXACT structure:

# 🌅 Morning Brief — {today_es}
*Generado para: Fund Manager | Tiempo de lectura: 5-7 min*

---

## 📊 1. Macro del Día

5-6 bullet points covering global markets with specific index levels and % changes,
major financial headlines, and geopolitical events affecting markets today.

---

## 🏛️ 2. Finanzas Institucionales

2-3 items on institutional finance: endowments, capital markets, FIBRAs, PE/VC news.
Use a table when comparing data.

---

## 🎯 3. Empresa del Día — Idea 10X/50X

Pick one public or private company with high-growth potential. Format:

**Empresa:** [Name] | **Sector:** [Sector] | **Mercado:** [Exchange/Private]
**Cap. Mercado:** [Market cap] | **Riesgo:** 🔴/🟠/🟡 [level]

**Tesis de Inversión:**
[2-3 paragraphs on catalysts and growth potential]

**Riesgos Principales:**
- [Risk 1]
- [Risk 2]
- [Risk 3]

> ⚠️ Esto NO es una recomendación de inversión. Solo para fines informativos y educativos.

---

## 🪙 4. Crypto Pick del Día

Table with today's prices for BTC, ETH, SOL, XRP + one more top-5 coin.

**Altcoin Pick:**
One altcoin outside top 5 with investment thesis and risk level. Reference RWA narrative when relevant.

---

## 🌎 5. Entorno Macroeconómico

**México 🇲🇽**
Peso/USD rate, Banxico decisions, inflation, key economic news.

**EE.UU. 🇺🇸**
Fed policy, employment, inflation (PCE/CPI), equity market conditions.

**Global 🌐**
IMF projections, geopolitical impacts, commodity prices: WTI oil, Brent oil, gold.

---

## 🔮 6. Tendencias del Futuro

3-4 trends on: emerging tech, AI applications, healthcare/longevity, civilization shifts.
Use a table when showing multiple trends. Connect each to investment implications.

---

*Fuentes utilizadas: [list all sources with clickable URLs]*
*Reporte generado: {generated_at} CST*
"""

# ── Search ─────────────────────────────────────────────────────────────────────

def gather_news(tavily_key: str) -> str:
    """Run targeted searches and return a combined news context string."""
    client = TavilyClient(api_key=tavily_key)
    sections = []

    for query in SEARCH_QUERIES:
        print(f"  >> {query[:70]}...")
        try:
            result = client.search(
                query=query,
                max_results=4,
                include_answer=True,
                search_depth="basic",
            )
            block = f"### Query: {query}\n"
            if result.get("answer"):
                block += f"Summary: {result['answer']}\n\n"
            for r in result.get("results", []):
                block += f"**{r.get('title', '')}**\n"
                block += f"{r.get('content', '')[:400]}\n"
                block += f"URL: {r.get('url', '')}\n\n"
            sections.append(block)
        except Exception as e:
            print(f"    ⚠️  Search failed: {e}", file=sys.stderr)

    return "\n---\n".join(sections)

# ── Generate ───────────────────────────────────────────────────────────────────

def generate_report() -> str:
    """Search news with Tavily, then synthesize report with Groq."""
    tavily_key = os.getenv("TAVILY_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")

    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    if not tavily_key:
        print("ERROR: TAVILY_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)
    if not openrouter_key:
        print("ERROR: OPENROUTER_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    # Step 1: Search
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Gathering today's news (Tavily)...")
    news_context = gather_news(tavily_key)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] News gathered ({len(news_context):,} chars).")

    # Step 2: Synthesize
    prompt = PROMPT_TEMPLATE.format(
        today=TODAY,
        today_es=TODAY_ES,
        news_context=news_context,
        whitepaper_note=WHITEPAPER_NOTE,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=openrouter_key,
    )

    # Fetch currently available free models from OpenRouter
    models_to_try = FALLBACK_MODELS
    try:
        r = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {openrouter_key}"},
            timeout=10,
        )
        if r.ok:
            all_models = r.json().get("data", [])
            free_live = [
                m["id"] for m in all_models
                if str(m.get("pricing", {}).get("prompt", "1")) == "0"
                and ":free" in m["id"]
            ]
            # Prefer larger context models
            free_live.sort(
                key=lambda mid: next(
                    (m.get("context_length", 0) for m in all_models if m["id"] == mid), 0
                ),
                reverse=True,
            )
            if free_live:
                print(f"  Found {len(free_live)} free models. Top picks: {free_live[:3]}")
                models_to_try = free_live
    except Exception as e:
        print(f"  Could not fetch model list ({e}), using fallback list.", file=sys.stderr)

    for model in models_to_try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Trying: {model}...")
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8000,
                temperature=0.6,
                timeout=120,
            )
            content = response.choices[0].message.content
            if content and content.strip():
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Done with {model}.")
                return content
        except Exception as e:
            err = str(e)[:120]
            print(f"  skip ({err})", file=sys.stderr)
            time.sleep(1)
            continue

    print("ERROR: All models failed.", file=sys.stderr)
    sys.exit(1)

# ── Save ───────────────────────────────────────────────────────────────────────

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

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Report saved: {output_path}")

    # Update manifest.json
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

# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    report_md = generate_report()
    if not report_md.strip():
        print("ERROR: Empty report returned.", file=sys.stderr)
        sys.exit(1)
    save_report(report_md)
    print("Morning Brief generated successfully.")
