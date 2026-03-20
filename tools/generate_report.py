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

_DAYS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
_MONTHS_ES = ["enero","febrero","marzo","abril","mayo","junio",
               "julio","agosto","septiembre","octubre","noviembre","diciembre"]
_today = date.today()
TODAY = _today.strftime("%A, %B %d, %Y")
TODAY_ES = f"{_DAYS_ES[_today.weekday()]} {_today.day} de {_MONTHS_ES[_today.month - 1]}, {_today.year}"

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

OUTPUT FORMAT — CRITICAL RULES:
- Output ONLY the HTML body content below. No <html>, <head>, <body>, or <style> tags.
- Use ONLY the CSS classes listed in the component reference below. Do not invent new classes.
- Every source citation must use: <div class="src">Fuentes: <a href="URL" target="_blank">Name</a>, ...</div>
- NEVER output raw URLs in visible text. Every URL must be inside an <a> tag.
- Use specific numbers from the news (index levels, % changes, prices). Do not use placeholders.
- Write all content in Spanish.

=== CSS COMPONENT REFERENCE ===

TAGS (inline badges before item text):
  <span class="tag tag-red">GEOPOLÍTICA</span>     ← bad news / risk
  <span class="tag tag-green">TECH</span>           ← positive / gains
  <span class="tag tag-orange">INFLACIÓN</span>     ← macro warnings
  <span class="tag tag-blue">FED</span>             ← central bank / policy
  <span class="tag tag-accent">EMPRESA</span>       ← corporate news
  <span class="tag tag-purple">CRYPTO</span>        ← crypto
  <span class="tag tag-cyan">RWA</span>             ← trends / future

ITEM (bullet news item with optional source):
  <div class="item">
    <span class="tag tag-red">LABEL</span>
    <strong>Headline:</strong> body text.
    <div class="src">Fuentes: <a href="https://..." target="_blank">Source Name</a></div>
  </div>

TABLE (market data, crypto prices, comparisons):
  <table>
    <thead><tr><th>Col 1</th><th>Col 2</th><th>Col 3</th></tr></thead>
    <tbody>
      <tr><td>Name</td><td class="mono">$1,234</td><td class="val-up">+2.1%</td></tr>
      <tr><td>Name</td><td class="mono">$5,678</td><td class="val-down">-0.8%</td></tr>
      <tr><td>Name</td><td class="mono">$9,012</td><td class="val-neutral">flat</td></tr>
    </tbody>
  </table>

CARD (analysis block, company card, altcoin pick):
  <div class="card">
    <div class="card-header">
      <div>
        <div class="card-title">Card Title</div>
        <div class="card-subtitle">subtitle / exchange / description</div>
      </div>
      <span class="risk risk-high">🔴 Riesgo Alto</span>       ← risk-high / risk-med-high / risk-med / risk-low
    </div>
    <div class="card-grid">
      <div class="card-stat"><div class="label">Sector</div><div class="value" style="color:var(--cyan)">Tech</div></div>
      <div class="card-stat"><div class="label">Precio</div><div class="value val-up">$145 (+13%)</div></div>
    </div>
    <div class="card-body">
      <p><strong>Tesis:</strong> explanation paragraph.</p>
      <p><strong>Riesgos:</strong> (1) risk one, (2) risk two, (3) risk three.</p>
    </div>
    <div class="disclaimer">⚠️ Esto NO constituye consejo de inversión. Solo fines informativos.</div>
    <div class="src">Fuentes: <a href="https://..." target="_blank">Source</a></div>
  </div>

SECTION (wraps each report section):
  <div class="section">
    <div class="section-title"><span class="emoji">📊</span> Section Name</div>
    <!-- items / table / cards here -->
  </div>

REPORT HEADER (top of the report):
  <div class="report-header">
    <div class="report-header-top">
      <h1 class="report-title">Morning Brief</h1>
      <span class="header-badge">BADGE TEXT</span>   ← 1-3 words describing today's mood
    </div>
    <div class="report-meta">
      <span>{today_es}</span>
      <span>Generado {generated_at} CST</span>
      <span>Lectura ~6 min</span>
    </div>
    <div class="header-summary">
      <strong>Resumen del día:</strong> 2-3 sentences summarizing the most important stories.
    </div>
  </div>

REPORT FOOTER:
  <div class="report-footer">
    <p>Reporte generado el {today_es} a las {generated_at} CST con datos de fuentes públicas.<br>
    Este reporte es de carácter informativo y no constituye asesoría de inversión.</p>
  </div>

=== GENERATE THE MORNING BRIEF NOW ===

Produce the complete report HTML using the structure below. Fill every section with real data from the news provided.

<!-- REPORT HEADER -->
[report-header component — badge reflects today's market mood in 1-3 words]

<!-- SECTION 1: MACRO DEL DÍA -->
[section with 5-6 .item components covering global indices with specific levels and % changes, key headlines, geopolitical events]
[include a market data table with: index/asset, last price, change, signal]

<!-- SECTION 2: FINANZAS INSTITUCIONALES -->
[section with 2-3 .card components on endowments, capital markets, FIBRAs, PE/VC, Banxico, sovereign funds]

<!-- SECTION 3: EMPRESA DEL DÍA — Idea 10X/50X -->
[section with one detailed .card with card-grid (6-8 stats), full investment thesis, and risks. Include disclaimer.]

<!-- SECTION 4: CRYPTO PICK DEL DÍA -->
[section with a crypto price table: BTC, ETH, SOL, XRP + one more top-5 coin with val-up/val-down/val-neutral]
[followed by one altcoin pick .card with card-grid (4 stats: price, mktcap, ATH, narrative), thesis, risks, disclaimer]

<!-- SECTION 5: ENTORNO MACROECONÓMICO -->
[section with 3 .card components: México 🇲🇽, Estados Unidos 🇺🇸, and a commodities table]

<!-- SECTION 6: TENDENCIAS DEL FUTURO -->
[section with a trends table (Tendencia | Señal reciente | Relevancia para Endowments) covering 3-4 trends]

<!-- REPORT FOOTER -->
[report-footer component]
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
