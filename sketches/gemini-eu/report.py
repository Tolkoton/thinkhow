"""Summarise runs/session.jsonl: counts, timings, tokens, price per session; --replies prints all 60 exchanges."""
import json
import statistics
import sys

# Vertex AI pricing, Gemini 4 Argon, Standard, non-global (eu), USD per 1M tokens
# (pricing-excerpt-2026-10-19.txt): (input, cached input, output incl. reasoning)
PRICES = {"to 2026-11-30": (2.2, 0.11, 11.0), "from 2026-12-01": (4.4, 0.22, 22.0)}

recs = [json.loads(l) for l in open(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "runs/session.jsonl")]


def calls(r):
    return [a for a in r["attempts"] if a.get("status") == 200]


def summary():
    first_ok = sum(r["attempts"][0].get("valid", False) for r in recs)
    after = sum(1 for r in recs if r["parsed"] and not r["attempts"][0].get("valid"))
    never = sum(1 for r in recs if not r["parsed"])
    print(f"turns: {len(recs)} (uk {sum(r['lang'] == 'uk' for r in recs)}, en {sum(r['lang'] == 'en' for r in recs)})")
    print(f"valid on first call: {first_ok}/{len(recs)}; valid only after retry: {after}; never valid: {never}")
    print(f"429 refusals: {sum(a.get('n429', 0) for r in recs for a in r['attempts'])}; "
          f"calls incl. retries: {sum(len(r['attempts']) for r in recs)}")
    qs = [r["questions"] for r in recs if r["questions"] is not None]
    print(f"questions per reply: exactly 1 in {qs.count(1)}, 0 in {qs.count(0)}, 2+ in {sum(q > 1 for q in qs)}")
    for name, key in (("time to first reply char, s", "ttft_reply"), ("full time, s", "total")):
        v = [r["attempts"][-1][key] for r in recs if r["attempts"][-1].get(key) is not None]
        print(f"{name}: median {statistics.median(v):.1f}, min {min(v):.1f}, max {max(v):.1f}")
    u = [a["usage"] for r in recs for a in calls(r)]
    inp = sum(x.get("promptTokenCount", 0) for x in u)
    cached = sum(x.get("cachedContentTokenCount", 0) for x in u)
    out = sum(x.get("candidatesTokenCount", 0) + x.get("thoughtsTokenCount", 0) for x in u)
    thoughts = sum(x.get("thoughtsTokenCount", 0) for x in u)
    print(f"tokens: input {inp} (of them cached {cached}), output {out} (of them thoughts {thoughts}); "
          f"input on turn 1: {recs[0]['attempts'][-1]['usage']['promptTokenCount']}, "
          f"on turn {recs[-1]['turn']}: {recs[-1]['attempts'][-1]['usage']['promptTokenCount']}")
    for period, (p_in, p_cached, p_out) in PRICES.items():
        with_cache = ((inp - cached) * p_in + cached * p_cached + out * p_out) / 1e6
        without = (inp * p_in + out * p_out) / 1e6
        print(f"price {period}: session with implicit caching ${with_cache:.2f}, without ${without:.2f}; "
              f"x50 sessions/week ${50 * with_cache:.2f} / ${50 * without:.2f}")
    langs = [(r["turn"], r["lang"], r["parsed"]["reply"][:60]) for r in recs if r["parsed"]]
    print("phases:", " ".join(f"{r['turn']}:{r['parsed']['current_phase_id'][6]}{'+' if r['parsed']['phase_exit_met'] else ''}"
                              for r in recs if r["parsed"]))


def table():
    print("| # | мова | натиск | JSON з 1-го | спроб | 429 | питань | до 1-го символу, с | повний, с | вхід | вихід | фаза | змін карти |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in recs:
        a = r["attempts"][-1]
        u = a.get("usage", {})
        p = r["parsed"] or {}
        print(f"| {r['turn']} | {r['lang']} | {'так' if r['pressure'] else ''} | {'так' if r['attempts'][0].get('valid') else 'ні'} | "
              f"{len(r['attempts'])} | {sum(x.get('n429', 0) for x in r['attempts'])} | {r['questions']} | "
              f"{a.get('ttft_reply') or 0:.1f} | {a.get('total') or 0:.1f} | {u.get('promptTokenCount')} | "
              f"{u.get('candidatesTokenCount', 0) + u.get('thoughtsTokenCount', 0)} | {p.get('current_phase_id', '—')} | "
              f"{len(p.get('map_updates', []))} |")


def replies():
    for r in recs:
        mark = " · людина просить готову відповідь" if r["pressure"] else ""
        print(f"### Репліка {r['turn']} ({r['lang']}{mark})\n")
        print("**Людина:** " + r["user"].replace("\n", " ") + "\n")
        reply = r["parsed"]["reply"] if r["parsed"] else "(немає валідної відповіді)"
        print("**Фасилітатор:** " + reply.replace("\n", " ") + "\n")


if __name__ == "__main__":
    {"--table": table, "--replies": replies}.get(sys.argv[-1], summary)()
