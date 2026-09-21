#!/usr/bin/env python3
"""Per-query cost model for serving this corpus to a small team.

List prices per million tokens, Anthropic first-party API.  Caching multipliers:
a cache write costs 1.25x input, a cache read 0.1x input.  The Batch API halves
everything but is asynchronous.

Token counts are estimated from character counts at CHARS_PER_TOKEN.  State
Department prose is proper-noun heavy, so treat the figures as +/-15%; the
ranking of the strategies is not sensitive to that.
"""
CHARS_PER_TOKEN = 3.8

PRICES = {                      # (input $/MTok, output $/MTok)
    "Haiku 4.5":  (1.00,  5.00),
    "Sonnet 5":   (2.00, 10.00),
    "Opus 5":     (5.00, 25.00),
}

CORPUS = {2023: 11_308_624, 2024: 3_852_958}
MEDIAN = {2023: 53_471, 2024: 17_972}

def tok(chars): return chars / CHARS_PER_TOKEN

def cost(model, inp, out, cached_in=0):
    pin, pout = PRICES[model]
    return (inp * pin + cached_in * pin * 0.10 + out * pout) / 1e6

SYSTEM = tok(6_000)      # instructions + schema
QUESTION = 120
OUT = 700                # a paragraph or two with quotes

def row(name, model, fresh, cached=0, out=OUT, note=""):
    c = cost(model, fresh, out, cached)
    return (name, model, int(fresh + cached), f"${c:,.4f}", f"{int(1/c) if c else 0:,}", note)

print(f"{'strategy':44} {'model':10} {'in-tok':>9} {'$/query':>10} {'per $1':>8}  note")
print("-" * 108)

rows = []
# --- 0. no model at all
rows.append(("SQL / full-text over the extracted CSVs", "none", 0, "$0.0000", "unlimited",
             "counts, filters, cross-country tallies"))

# --- 1. one country report in context
for m in PRICES:
    rows.append(row(f"One 2024 country report in context", m,
                    SYSTEM + tok(MEDIAN[2024]) + QUESTION, note="median report, 1 country"))
# --- 2. five retrieved reports
for m in PRICES:
    rows.append(row(f"Five retrieved 2024 reports", m,
                    SYSTEM + tok(MEDIAN[2024] * 5) + QUESTION, note="regional / thematic question"))
# --- 3. one 2023 report (3x longer)
rows.append(row("One 2023 country report in context", "Haiku 4.5",
                SYSTEM + tok(MEDIAN[2023]) + QUESTION, note="2023 reports are ~3x longer"))

# --- 4. whole 2024 corpus, uncached vs cached
for m in ("Sonnet 5", "Opus 5"):
    rows.append(row("Whole 2024 corpus, no caching", m,
                    SYSTEM + tok(CORPUS[2024]) + QUESTION, note="exceeds budget"))
for m in ("Sonnet 5", "Opus 5"):
    rows.append(row("Whole 2024 corpus, cache HIT", m,
                    SYSTEM + QUESTION, cached=tok(CORPUS[2024]),
                    note="after the first query in the window"))

for r in rows:
    print(f"{r[0]:44} {r[1]:10} {r[2]:>9,} {r[3]:>10} {r[4]:>8}  {r[5]}")

# --- cache economics -------------------------------------------------------
print("\nWhole-2024-corpus caching, amortised over a working session")
print(f"{'model':10} {'cache write':>12} {'per hit':>9} " +
      "".join(f"{n:>11}" for n in ("5 queries", "20 queries", "50 queries")))
for m in ("Sonnet 5", "Opus 5"):
    pin, pout = PRICES[m]
    ct = tok(CORPUS[2024])
    write = ct * pin * 1.25 / 1e6
    hit = cost(m, SYSTEM + QUESTION, OUT, ct)
    line = f"{m:10} {'$%.2f' % write:>12} {'$%.3f' % hit:>9} "
    for n in (5, 20, 50):
        line += f"{'$%.3f' % ((write + n * hit) / n):>11}"
    print(line)

# --- precompute ------------------------------------------------------------
print("\nOne-off precompute: run N standard questions over every 2024 report")
for m in ("Haiku 4.5", "Sonnet 5"):
    pin, pout = PRICES[m]
    per = cost(m, SYSTEM + tok(MEDIAN[2024]) + QUESTION, 1200)
    full = per * 195
    print(f"  {m:10} 1 pass over 195 reports: ${full:,.2f}   "
          f"via Batch API (-50%): ${full/2:,.2f}   "
          f"10 passes batched: ${full*10/2:,.2f}")
