"""Renders metrics/habits.svg: best day, most active weekday and hour, streaks."""
import json, os, sys, urllib.request
from collections import Counter
from datetime import date, datetime
from zoneinfo import ZoneInfo

USER, TZ = os.environ["GH_USER"], ZoneInfo(os.environ.get("TZ_NAME", "Asia/Kolkata"))
TOKEN = os.environ["GH_TOKEN"]
DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def api(url, body=None):
    req = urllib.request.Request(url, json.dumps(body).encode() if body else None, {
        "Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def calendar():
    q = """query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{
      weeks{contributionDays{date weekday contributionCount}}}}}}"""
    weeks = api("https://api.github.com/graphql", {"query": q, "variables": {"u": USER}})
    weeks = weeks["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [d for w in weeks for d in w["contributionDays"]]


def commit_hours():
    hours = Counter()
    for page in range(1, 11):  # search caps at 1000 results
        r = api(f"https://api.github.com/search/commits?q=author:{USER}&sort=author-date&per_page=100&page={page}")
        for item in r["items"]:
            hours[datetime.fromisoformat(item["commit"]["author"]["date"]).astimezone(TZ).hour] += 1
        if len(r["items"]) < 100:
            break
    return hours


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def streaks(days):
    run = best = 0
    for d in days:
        run = run + 1 if d["contributionCount"] else 0
        best = max(best, run)
    current = 0
    for d in reversed(days[:-1] if not days[-1]["contributionCount"] else days):  # today may be pending
        if not d["contributionCount"]:
            break
        current += 1
    return current, best


def bars(x, y, w, h, values, labels, every=1):
    top, gap = max(values) or 1, w / len(values)
    out = []
    for i, v in enumerate(values):
        bh = max(2, h * v / top) if v else 2
        out.append(f'<rect x="{x + i * gap + 1:.1f}" y="{y + h - bh:.1f}" width="{gap - 2:.1f}" height="{bh:.1f}" rx="2" class="{"bar hi" if v == top and v else "bar"}"/>')
        if i % every == 0:
            out.append(f'<text x="{x + i * gap + gap / 2:.1f}" y="{y + h + 14}" class="axis">{labels[i]}</text>')
    return "".join(out)


def main():
    days = calendar()
    by_day = Counter()
    for d in days:
        by_day[d["weekday"]] += d["contributionCount"]
    best = max(days, key=lambda d: d["contributionCount"])
    current, longest = streaks(days)
    total = sum(d["contributionCount"] for d in days)
    hours = commit_hours()
    hour_vals = [hours[h] for h in range(24)]
    top_day = DAYS[max(range(7), key=lambda i: by_day[i])]
    top_hour = max(range(24), key=lambda h: hours[h])
    best_on = date.fromisoformat(best["date"]).strftime("%d %b %Y")

    facts = [
        ("Last 12 months", f"{total:,}"),
        ("Best day", f'{best["contributionCount"]} on {best_on}'),
        ("Most active day", top_day),
        ("Most active hour", f"{top_hour:02d}:00" if sum(hour_vals) else "n/a"),
        ("Current streak", plural(current, "day")),
        ("Longest streak", plural(longest, "day")),
    ]
    rows = "".join(
        f'<text x="{20 + (i % 2) * 230}" y="{58 + (i // 2) * 22}" class="k">{k}</text>'
        f'<text x="{220 + (i % 2) * 230}" y="{58 + (i // 2) * 22}" class="v">{v}</text>'
        for i, (k, v) in enumerate(facts))
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="480" height="300" viewBox="0 0 480 300">
<style>
text{{font:13px -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;fill:#57606a}}
.t{{font-size:16px;fill:#0969da}} .k{{fill:#57606a}} .v{{font-weight:600;fill:#24292f;text-anchor:end}}
.s{{font-size:12px;fill:#57606a}} .axis{{font-size:10px;fill:#8c959f;text-anchor:middle}}
.bar{{fill:#9be9a8}} .hi{{fill:#216e39}}
@media (prefers-color-scheme:dark){{text,.k,.s{{fill:#8b949e}} .t{{fill:#58a6ff}} .v{{fill:#e6edf3}}
.axis{{fill:#6e7681}} .bar{{fill:#0e4429}} .hi{{fill:#39d353}}}}
</style>
<text x="20" y="28" class="t">Coding habits</text>
{rows}
<text x="20" y="148" class="s">Contributions by weekday</text>
{bars(20, 158, 170, 100, [by_day[i] for i in range(7)], [d[0] for d in DAYS])}
<text x="220" y="148" class="s">Public commits by hour (IST)</text>
{bars(220, 158, 240, 100, hour_vals, [str(h) for h in range(24)], every=3)}
</svg>"""
    os.makedirs("metrics", exist_ok=True)
    with open("metrics/habits.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print(dict(facts), file=sys.stderr)


main()
