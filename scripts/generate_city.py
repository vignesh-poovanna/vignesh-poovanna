#!/usr/bin/env python3
"""Render the last year of GitHub contributions as an isometric night-skyline SVG.

Data source, in order:
  1. GitHub GraphQL API (needs GITHUB_TOKEN / PROFILE_TOKEN)
  2. Public contributions page (no token needed)
If both fail, the existing SVG is left untouched.

Usage:
  USERNAME=your-login GITHUB_TOKEN=... python scripts/generate_city.py
  python scripts/generate_city.py --demo        # synthetic data, for previews
"""
import datetime as dt
import json
import math
import os
import random
import re
import sys
import urllib.request

USERNAME = os.environ.get("USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "vignesh-poovanna"
TOKEN = os.environ.get("PROFILE_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT = os.environ.get("CITY_OUT", "assets/contribution-city.svg")

# ---- look & feel (edit freely) ---------------------------------------------
HW, HH = 10.0, 5.0          # half tile width / height (isometric projection)
FOOT = 0.78                 # building footprint within a cell (0-1)
MAX_H = 95.0                # tallest building, px
BASE_H = 7.0                # minimum height of an active day
FLAT_H = 1.4                # height of an empty-day slab
BG_TOP, BG_BOTTOM = "#050814", "#0d1530"
# base colour per level 0..4 (top face); side faces are darkened automatically
LEVELS = ["#1b2440", "#1f5f94", "#2490d0", "#2fc0ff", "#8ffbff"]
WINDOW = "#ffd98a"
FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
# -----------------------------------------------------------------------------


def http(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def fetch_graphql():
    if not TOKEN:
        raise RuntimeError("no token")
    query = """query($login:String!){user(login:$login){contributionsCollection{
      contributionCalendar{totalContributions weeks{contributionDays{date contributionCount weekday}}}}}}"""
    body = json.dumps({"query": query, "variables": {"login": USERNAME}}).encode()
    raw = http("https://api.github.com/graphql", body,
               {"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                "User-Agent": "contribution-city"})
    cal = json.loads(raw)["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return [[(d["date"], d["contributionCount"], d["weekday"]) for d in w["contributionDays"]]
            for w in cal["weeks"] if w["contributionDays"]]


def fetch_html():
    page = http(f"https://github.com/users/{USERNAME}/contributions",
                headers={"User-Agent": "Mozilla/5.0 contribution-city"})
    cells = re.findall(r'<td[^>]*?data-date="([\d-]+)"[^>]*?id="([^"]+)"', page)
    tips = {m[0]: m[1] for m in re.findall(r'for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page)}
    days = []
    for date, cid in cells:
        m = re.match(r"(\d+) contribution", tips.get(cid, "").strip())
        days.append((date, int(m.group(1)) if m else 0))
    if not days:
        raise RuntimeError("no cells parsed")
    days.sort()
    weeks, cur = [], []
    for date, n in days:
        wd = (dt.date.fromisoformat(date).weekday() + 1) % 7  # Sunday = 0
        if wd == 0 and cur:
            weeks.append(cur)
            cur = []
        cur.append((date, n, wd))
    if cur:
        weeks.append(cur)
    return weeks


def demo_data():
    rnd = random.Random(7)
    start = dt.date.today() - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)
    weeks, d = [], start
    while d <= dt.date.today():
        wk = []
        for _ in range(7):
            if d <= dt.date.today():
                n = 0 if rnd.random() < 0.45 else int(rnd.expovariate(1 / 5))
                wk.append((d.isoformat(), n, (d.weekday() + 1) % 7))
            d += dt.timedelta(days=1)
        weeks.append(wk)
    return weeks


def shade(hex_, f):
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(min(255, int(v * f)) for v in (r, g, b))


def level(n, mx):
    if n <= 0:
        return 0
    q = n / mx
    return 1 if q <= .25 else 2 if q <= .5 else 3 if q <= .75 else 4


def render(weeks):
    flat = [(c, wd, n, date) for c, w in enumerate(weeks) for date, n, wd in w]
    mx = max((n for _, _, n, _ in flat), default=0) or 1
    total = sum(n for _, _, n, _ in flat)
    best = max(flat, key=lambda t: t[2])

    ncols = len(weeks)
    heights = {}
    for c, r, n, _ in flat:
        heights[(c, r)] = FLAT_H if n == 0 else BASE_H + math.sqrt(n / mx) * (MAX_H - BASE_H)

    ox = 7 * HW + 24
    P = lambda c, r, z: (ox + (c - r) * HW, 118 + (c + r) * HH - z)
    width = ox + (ncols + 1) * HW + 24
    ground_bottom = P(ncols, 7, 0)[1]
    height = ground_bottom + 56
    pts = lambda *ps: " ".join(f"{x:.1f},{y:.1f}" for x, y in ps)

    o = []
    w = o.append
    w(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
      f'width="100%" role="img" aria-label="Contribution city: an isometric night skyline with one '
      f'building per day of the last year. {total:,} contributions, busiest day {best[3]} with {best[2]}.">')
    w('<defs>'
      f'<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG_TOP}"/>'
      f'<stop offset="1" stop-color="{BG_BOTTOM}"/></linearGradient>'
      '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.4"/></filter>'
      '<style>.s{animation:tw 4s ease-in-out infinite}@keyframes tw{0%,100%{opacity:.25}50%{opacity:1}}'
      f'text{{font-family:{FONT}}}</style></defs>')
    w(f'<rect width="{width:.0f}" height="{height:.0f}" fill="url(#sky)"/>')

    rnd = random.Random(42)
    for _ in range(70):
        x, y = rnd.uniform(0, width), rnd.uniform(0, height * 0.55)
        w(f'<circle class="s" style="animation-delay:{rnd.uniform(0, 4):.1f}s" cx="{x:.0f}" cy="{y:.0f}" '
          f'r="{rnd.choice([.6, .8, 1.1]):.1f}" fill="#cfe8ff"/>')

    # ground plate
    w(f'<polygon points="{pts(P(-.4, -.4, 0), P(ncols + .4, -.4, 0), P(ncols + .4, 7.4, 0), P(-.4, 7.4, 0))}" '
      f'fill="#0a1022" stroke="#1b2748" stroke-width="1"/>')

    glow = []
    # painter's algorithm: back to front
    for c, r, n, date in sorted(flat, key=lambda t: (t[0] + t[1], t[0])):
        z = heights[(c, r)]
        base = LEVELS[level(n, mx)]
        o0, s = (1 - FOOT) / 2, FOOT
        c0, r0, c1, r1 = c + o0, r + o0, c + o0 + s, r + o0 + s
        top = pts(P(c0, r0, z), P(c1, r0, z), P(c1, r1, z), P(c0, r1, z))
        left = pts(P(c1, r0, 0), P(c1, r1, 0), P(c1, r1, z), P(c1, r0, z))
        right = pts(P(c0, r1, 0), P(c1, r1, 0), P(c1, r1, z), P(c0, r1, z))
        w(f'<g><title>{date}: {n} contribution{"s" if n != 1 else ""}</title>'
          f'<polygon points="{left}" fill="{shade(base, .62)}"/>'
          f'<polygon points="{right}" fill="{shade(base, .42)}"/>')
        # lit windows on taller buildings
        if z > 16:
            wr = random.Random(c * 97 + r)
            for face in ("L", "R"):
                for k in range(int((z - 5) // 6)):
                    v0 = 4 + k * 6
                    for u0 in (0.14, 0.52):
                        if wr.random() < 0.42:
                            u1, v1 = u0 + 0.22, v0 + 3
                            if face == "L":
                                q = (P(c1, r0 + u0 * s / .78 * .78, v0), P(c1, r0 + u1 * s, v0),
                                     P(c1, r0 + u1 * s, v1), P(c1, r0 + u0 * s, v1))
                            else:
                                q = (P(c0 + u0 * s, r1, v0), P(c0 + u1 * s, r1, v0),
                                     P(c0 + u1 * s, r1, v1), P(c0 + u0 * s, r1, v1))
                            w(f'<polygon points="{pts(*q)}" fill="{WINDOW}" opacity="{wr.choice([.55, .8, 1]):.2f}"/>')
        w(f'<polygon points="{top}" fill="{base}"/></g>')
        if level(n, mx) >= 3:
            glow.append(f'<polygon points="{top}" fill="{base}" opacity=".85"/>')
    if glow:
        w('<g filter="url(#glow)">' + "".join(glow) + "</g>")

    w(f'<text x="24" y="30" fill="#7fb4ff" font-size="13" letter-spacing="2">// CONTRIBUTION CITY</text>')
    w(f'<text x="24" y="{height - 22:.0f}" fill="#5f7bb0" font-size="11">'
      f'{total:,} contributions · busiest day {best[3]} ({best[2]}) · one building per day</text>')
    w('</svg>')
    return "\n".join(o)


def main():
    if "--demo" in sys.argv:
        weeks = demo_data()
    else:
        weeks = None
        for fetch in (fetch_graphql, fetch_html):
            try:
                weeks = fetch()
                break
            except Exception as e:  # noqa: BLE001
                print(f"{fetch.__name__} failed: {e}", file=sys.stderr)
        if not weeks:
            print("No data; keeping existing SVG.", file=sys.stderr)
            return
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    svg = render(weeks)
    if os.path.exists(OUT) and open(OUT, encoding="utf-8").read() == svg:
        print("unchanged")
        return
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {OUT} ({len(svg) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
