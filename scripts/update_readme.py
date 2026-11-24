#!/usr/bin/env python3
"""
GitSkins-style Dynamic Profile SVG Generator for @SujoyBehera.
Automatically fetches live GitHub stats, contributions, repository-weighted language
percentages, and featured projects via GitHub GraphQL API (in GitHub Actions)
or local cached/scraped data, and renders:
  - assets/profile-header.svg
  - assets/contribution-city.svg
  - assets/stack-and-projects.svg
"""

import json
import math
import os
import re
import urllib.request
from datetime import datetime
from PIL import Image, ImageEnhance

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(ROOT_DIR, "assets")
AVATAR_FILE = os.path.join(ASSETS_DIR, "avatar.jpg")
USERNAME = "SujoyBehera"

os.makedirs(ASSETS_DIR, exist_ok=True)


def xml_esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def fetch_via_graphql(token: str) -> dict:
    query = """
    query($login: String!) {
      user(login: $login) {
        name
        bio
        followers { totalCount }
        repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, orderBy: {field: UPDATED_AT, direction: DESC}) {
          totalCount
          nodes {
            name
            description
            stargazerCount
            isFork
            updatedAt
            defaultBranchRef {
              target {
                ... on Commit {
                  history { totalCount }
                }
              }
            }
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              totalSize
              edges {
                size
                node { name }
              }
            }
          }
        }
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    payload = json.dumps({"query": query, "variables": {"login": USERNAME}}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "SujoyBehera-Profile-Generator",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        res = json.loads(resp.read().decode("utf-8"))

    u = res["data"]["user"]
    repos = []
    repo_weighted = {}

    for node in u["repositories"]["nodes"]:
        langs_edges = node.get("languages", {}).get("edges", [])
        tot_sz = node.get("languages", {}).get("totalSize", 0) or 0
        pct_by_lang = {}
        if tot_sz > 0 and not node["isFork"]:
            for edge in langs_edges:
                lname = edge["node"]["name"]
                share = edge["size"] / tot_sz
                pct_by_lang[lname] = round(share * 100, 1)
                repo_weighted[lname] = repo_weighted.get(lname, 0.0) + share

        commits = 0
        if node.get("defaultBranchRef") and node["defaultBranchRef"].get("target"):
            commits = node["defaultBranchRef"]["target"].get("history", {}).get("totalCount", 0)

        repos.append({
            "name": node["name"],
            "desc": node.get("description") or "",
            "stars": node.get("stargazerCount", 0),
            "fork": node.get("isFork", False),
            "updated": node.get("updatedAt", ""),
            "commits": commits,
            "pct_by_lang": pct_by_lang,
        })

    tot_rw = sum(repo_weighted.values()) or 1.0
    rw_pct = {k: round(v / tot_rw * 100, 1) for k, v in sorted(repo_weighted.items(), key=lambda x: -x[1])}

    cal = u["contributionsCollection"]["contributionCalendar"]
    days = []
    for wk in cal["weeks"]:
        for d in wk["contributionDays"]:
            cnt = d["contributionCount"]
            days.append({"date": d["date"], "count": cnt, "level": 0 if cnt == 0 else min(4, 1 + cnt // 5)})

    active_days = sum(1 for d in days if d["count"] > 0)
    busiest = max(days, key=lambda d: d["count"]) if days else {"date": "", "count": 0}

    return {
        "name": u.get("name") or "Sujoy Behera",
        "bio": u.get("bio") or "CS Undergrad @ SRM KTR '29 · Python Backend & AI Engineering",
        "followers": u["followers"]["totalCount"],
        "repos": repos,
        "repo_weighted_pct": rw_pct,
        "contributions": {
            "total": cal["totalContributions"],
            "active_days": active_days,
            "busiest": busiest,
            "days": days,
        },
    }


def load_data() -> dict:
    local_override = os.environ.get("LOCAL_GITHUB_DATA_JSON")
    if local_override and os.path.exists(local_override):
        with open(local_override, "r", encoding="utf-8") as f:
            return json.load(f)

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return fetch_via_graphql(token)

    raise RuntimeError("Set GITHUB_TOKEN or LOCAL_GITHUB_DATA_JSON")


# ==============================================================================
# 1. HEADER SVG (1000 x 255)
# ==============================================================================
def generate_header_svg(data: dict):
    W, H = 1000, 255
    num_repos = len(data["repos"])
    total_stars = sum(r.get("stars", 0) for r in data["repos"])
    total_contribs = data["contributions"]["total"]
    followers = data.get("followers", 17)

    # LED Dot-Matrix Portrait seamlessly integrated into starry dark header
    cols, rows = 46, 44
    dot_spacing = 4.9
    grid_x0 = 744
    grid_y0 = 22

    led_dots = []
    if os.path.exists(AVATAR_FILE):
        img = Image.open(AVATAR_FILE).convert("RGB")
        iw, ih = img.size
        crop_box = (int(iw * 0.14), int(ih * 0.18), int(iw * 0.85), int(ih * 0.96))
        img_cropped = img.crop(crop_box)
        img_cropped = ImageEnhance.Contrast(img_cropped).enhance(1.25)
        img_cropped = ImageEnhance.Color(img_cropped).enhance(1.30)
        img_small = img_cropped.resize((cols, rows), Image.Resampling.LANCZOS)

        cx_norm, cy_norm = (cols - 1) / 2.0, (rows - 1) / 2.0
        for r_idx in range(rows):
            for c_idx in range(cols):
                dx = (c_idx - cx_norm) / (cols / 2.0)
                dy = (r_idx - cy_norm) / (rows / 2.0)
                dist = math.sqrt(dx * dx * 0.92 + dy * dy * 0.92)
                if dist > 1.06:
                    continue

                pr, pg, pb = img_small.getpixel((c_idx, r_idx))
                lum = (0.299 * pr + 0.587 * pg + 0.114 * pb) / 255.0

                # Smooth continuous foreground weight (hair + warm skin + smooth elliptical shirt region)
                dark_hair_w = max(0.0, min(1.0, (0.42 - lum) * 3.2)) * max(0.0, 1.0 - abs(dx) * 1.35)
                warm_skin_w = max(0.0, min(1.0, (pr - pb - 8) / 42.0))
                shirt_ell = ((c_idx - 21.5) / 14.5) ** 2 + ((r_idx - 34.5) / 14.0) ** 2
                shirt_w = max(0.0, min(1.0, (1.15 - shirt_ell) * 1.8)) * max(0.0, min(1.0, (lum - 0.45) * 2.5))

                fg_w = max(dark_hair_w, warm_skin_w, shirt_w)
                edge_fade = max(0.06, min(1.0, (1.06 - dist) * 1.75))

                # Blend pixel smoothly between ambient cyber-matrix backdrop and true portrait color
                bg_r = pr * 0.12 + 8
                bg_g = pg * 0.24 + 18
                bg_b = pb * 0.42 + 36

                out_r = int(min(255, bg_r * (1.0 - fg_w) + pr * fg_w))
                out_g = int(min(255, bg_g * (1.0 - fg_w) + pg * fg_w))
                out_b = int(min(255, bg_b * (1.0 - fg_w) + pb * fg_w))

                radius = (1.30 + 0.68 * fg_w) * edge_fade
                opacity = round((0.46 + 0.49 * fg_w) * edge_fade, 2)
                hex_col = f"#{out_r:02x}{out_g:02x}{out_b:02x}"

                cx = grid_x0 + c_idx * dot_spacing
                cy = grid_y0 + r_idx * dot_spacing
                led_dots.append(
                    f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.2f}" fill="{hex_col}" opacity="{opacity}"/>'
                )

    stars_coords = [
        (45, 28, 1.3, "2.8s", "0s"), (168, 38, 1.7, "3.5s", "0.6s"),
        (292, 22, 1.2, "2.4s", "1.1s"), (395, 48, 2.0, "4.0s", "0.3s"),
        (462, 26, 1.5, "3.1s", "1.5s"), (548, 30, 1.1, "2.7s", "0.9s"),
        (668, 25, 1.8, "3.6s", "0.2s"), (715, 62, 1.4, "2.9s", "1.8s"),
        (702, 205, 1.5, "3.3s", "0.7s"), (445, 198, 1.3, "2.6s", "1.3s"),
        (342, 166, 1.1, "3.8s", "0.4s"), (630, 226, 1.4, "3.0s", "1.0s"),
    ]
    stars_svg = [
        f'<circle cx="{sx}" cy="{sy}" r="{sr}" fill="#e0f2fe" style="animation: twinkle {dur} ease-in-out {delay} infinite;"/>'
        for sx, sy, sr, dur, delay in stars_coords
    ]
    for spx, spy, spsz in [(448, 34, 6), (706, 38, 5), (474, 184, 4.5)]:
        d = f"M {spx} {spy-spsz} Q {spx} {spy} {spx+spsz} {spy} Q {spx} {spy} {spx} {spy+spsz} Q {spx} {spy} {spx-spsz} {spy} Q {spx} {spy} {spx} {spy-spsz} Z"
        stars_svg.append(f'<path d="{d}" fill="#7dd3fc" opacity="0.85" style="animation: twinkle 3.2s ease-in-out infinite;"/>')

    pills = [
        ("C++", "#f34b7d", 74),
        ("Python", "#38bdf8", 90),
        ("TypeScript", "#818cf8", 112),
        ("Java", "#f59e0b", 74),
    ]
    pills_svg = []
    px = 42
    for label, dot_col, pw in pills:
        pills_svg.append(f'''
        <g transform="translate({px}, 188)">
          <rect x="0" y="0" width="{pw}" height="28" rx="8" fill="#0f172a" stroke="#1e293b" stroke-width="1.2"/>
          <circle cx="15" cy="14" r="4" fill="{dot_col}"/>
          <text x="26" y="18.5" fill="#e2e8f0" font-size="12.5" font-weight="600" class="sans">{xml_esc(label)}</text>
        </g>''')
        px += pw + 10

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none">
  <defs>
    <linearGradient id="hdrBg" x1="0" y1="0" x2="{W}" y2="{H}" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#070b14"/>
      <stop offset="55%" stop-color="#0b1324"/>
      <stop offset="100%" stop-color="#080f1d"/>
    </linearGradient>
    <linearGradient id="hdrBorder" x1="0" y1="0" x2="{W}" y2="{H}" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#1e3a5f" stop-opacity="0.85"/>
      <stop offset="50%" stop-color="#0ea5e9" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="#14b8a6" stop-opacity="0.7"/>
    </linearGradient>
    <radialGradient id="ambientCyan" cx="84%" cy="50%" r="32%">
      <stop offset="0%" stop-color="#0ea5e9" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#0ea5e9" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="ambientLeft" cx="18%" cy="35%" r="40%">
      <stop offset="0%" stop-color="#2dd4bf" stop-opacity="0.08"/>
      <stop offset="100%" stop-color="#2dd4bf" stop-opacity="0"/>
    </radialGradient>
    <style>
      @keyframes twinkle {{
        0%, 100% {{ opacity: 0.92; }}
        50% {{ opacity: 0.22; }}
      }}
      .sans {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', Ubuntu, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace; }}
    </style>
  </defs>

  <rect x="1.5" y="1.5" width="{W-3}" height="{H-3}" rx="18" fill="url(#hdrBg)" stroke="url(#hdrBorder)" stroke-width="1.6"/>
  <rect x="2" y="2" width="{W-4}" height="{H-4}" rx="18" fill="url(#ambientCyan)"/>
  <rect x="2" y="2" width="{W-4}" height="{H-4}" rx="18" fill="url(#ambientLeft)"/>

  {''.join(stars_svg)}

  <!-- Profile Identity -->
  <text x="42" y="64" fill="#38bdf8" font-size="14.5" font-weight="600" class="mono">@SujoyBehera</text>
  <text x="42" y="114" fill="#f8fafc" font-size="40" font-weight="800" letter-spacing="-0.8" class="sans">Sujoy Behera</text>
  <text x="42" y="146" fill="#94a3b8" font-size="14.2" font-weight="500" class="sans">Backend &amp; AI Engineering · B.Tech CSE @ SRM KTR '29</text>

  {''.join(pills_svg)}

  <!-- Subtle Vertical Divider -->
  <line x1="494" y1="44" x2="494" y2="211" stroke="#1e293b" stroke-width="1" stroke-dasharray="3 3"/>

  <!-- Live GitHub Stats -->
  <g transform="translate(520, 50)">
    <rect x="0" y="0" width="26" height="26" rx="6" fill="#0f1e36" stroke="#1e3a5f" stroke-width="1"/>
    <path d="M7 6.5h12a1.5 1.5 0 0 1 1.5 1.5v10a1.5 1.5 0 0 1-1.5 1.5H7A1.5 1.5 0 0 1 5.5 18V8A1.5 1.5 0 0 1 7 6.5Zm0 3h12" stroke="#38bdf8" stroke-width="1.5" stroke-linecap="round"/>
    <text x="38" y="18" fill="#f8fafc" font-size="15.5" font-weight="700" class="sans">{num_repos} <tspan fill="#94a3b8" font-weight="500">Repositories</tspan></text>
  </g>

  <g transform="translate(520, 92)">
    <rect x="0" y="0" width="26" height="26" rx="6" fill="#1c1917" stroke="#451a03" stroke-width="1"/>
    <path d="M13 5.5l2.1 4.3 4.7.7-3.4 3.3.8 4.7L13 16.3 8.8 18.5l.8-4.7-3.4-3.3 4.7-.7L13 5.5Z" stroke="#fbbf24" stroke-width="1.5" stroke-linejoin="round"/>
    <text x="38" y="18" fill="#f8fafc" font-size="15.5" font-weight="700" class="sans">{total_stars} <tspan fill="#94a3b8" font-weight="500">Stars</tspan></text>
  </g>

  <g transform="translate(520, 134)">
    <rect x="0" y="0" width="26" height="26" rx="6" fill="#062825" stroke="#115e59" stroke-width="1"/>
    <path d="M5.5 16.5l4.2-4.5 3.3 3 5.5-6.5M15 8.5h3.5V12" stroke="#2dd4bf" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
    <text x="38" y="18" fill="#f8fafc" font-size="15.5" font-weight="700" class="sans">{total_contribs} <tspan fill="#94a3b8" font-weight="500">Contributions</tspan></text>
  </g>

  <g transform="translate(520, 176)">
    <rect x="0" y="0" width="26" height="26" rx="6" fill="#1e1b4b" stroke="#312e81" stroke-width="1"/>
    <circle cx="13" cy="10" r="3.2" stroke="#a78bfa" stroke-width="1.5"/>
    <path d="M7.5 19.5c0-2.8 2.5-4.5 5.5-4.5s5.5 1.7 5.5 4.5" stroke="#a78bfa" stroke-width="1.5" stroke-linecap="round"/>
    <text x="38" y="18" fill="#f8fafc" font-size="15.5" font-weight="700" class="sans">{followers} <tspan fill="#94a3b8" font-weight="500">Followers</tspan></text>
  </g>

  <!-- LED Dot-Matrix Portrait -->
  <g>
    {''.join(led_dots)}
  </g>
</svg>'''
    with open(os.path.join(ASSETS_DIR, "profile-header.svg"), "w", encoding="utf-8") as f:
        f.write(svg)


# ==============================================================================
# 2. 3D CONTRIBUTION CITY SVG (1000 x 326)
# ==============================================================================
def generate_city_svg(data: dict):
    W, H = 1000, 326
    contribs = data["contributions"]
    total_c = contribs["total"]
    active_days = contribs["active_days"]
    busiest_cnt = contribs["busiest"]["count"] if contribs.get("busiest") else 0
    days = contribs["days"]

    first_dt = datetime.strptime(days[0]["date"], "%Y-%m-%d")
    first_sun_offset = (first_dt.weekday() + 1) % 7

    cells = []
    for idx, d in enumerate(days):
        pos = idx + first_sun_offset
        cells.append((pos // 7, pos % 7, d["count"]))

    ox, oy = 298.0, 232.0
    ux, uy = 9.5, -2.0
    vx, vy = 17.2, 9.0

    def iso_pt(w, d, z=0.0):
        return (ox + w * ux + d * vx, oy + w * uy + d * vy - z)

    cells_sorted = sorted(cells, key=lambda c: (c[1] * vy + c[0] * uy))
    bars_svg = []
    max_cnt = max(busiest_cnt, 1)

    for w_idx, dow, cnt in cells_sorted:
        p = 0.08
        w0, w1 = w_idx + p, w_idx + 1.0 - p
        d0, d1 = dow + p, dow + 1.0 - p

        if cnt == 0:
            b0, b1, b2, b3 = iso_pt(w0, d0), iso_pt(w1, d0), iso_pt(w1, d1), iso_pt(w0, d1)
            pts = f"{b0[0]:.1f},{b0[1]:.1f} {b1[0]:.1f},{b1[1]:.1f} {b2[0]:.1f},{b2[1]:.1f} {b3[0]:.1f},{b3[1]:.1f}"
            bars_svg.append(f'<polygon points="{pts}" fill="#0a2629" stroke="#134e4a" stroke-width="0.75" opacity="0.92"/>')
        else:
            norm = cnt / max_cnt
            h = 10.0 + 80.0 * (norm ** 0.68)
            if norm >= 0.65:
                top_c, left_c, right_c, edge_c = "#99f6e4", "#2dd4bf", "#0d9488", "#ccfbf1"
            elif norm >= 0.30:
                top_c, left_c, right_c, edge_c = "#5eead4", "#14b8a6", "#0f766e", "#99f6e4"
            elif norm >= 0.12:
                top_c, left_c, right_c, edge_c = "#2dd4bf", "#0d9488", "#115e59", "#5eead4"
            else:
                top_c, left_c, right_c, edge_c = "#14b8a6", "#0f766e", "#134e4a", "#2dd4bf"

            base0, base2, base3 = iso_pt(w0, d0, 0), iso_pt(w1, d1, 0), iso_pt(w0, d1, 0)
            top0, top1, top2, top3 = iso_pt(w0, d0, h), iso_pt(w1, d0, h), iso_pt(w1, d1, h), iso_pt(w0, d1, h)

            fl_pts = f"{base0[0]:.1f},{base0[1]:.1f} {base3[0]:.1f},{base3[1]:.1f} {top3[0]:.1f},{top3[1]:.1f} {top0[0]:.1f},{top0[1]:.1f}"
            fr_pts = f"{base3[0]:.1f},{base3[1]:.1f} {base2[0]:.1f},{base2[1]:.1f} {top2[0]:.1f},{top2[1]:.1f} {top3[0]:.1f},{top3[1]:.1f}"
            rf_pts = f"{top0[0]:.1f},{top0[1]:.1f} {top1[0]:.1f},{top1[1]:.1f} {top2[0]:.1f},{top2[1]:.1f} {top3[0]:.1f},{top3[1]:.1f}"

            bars_svg.append(
                f'<g>'
                f'<polygon points="{fl_pts}" fill="{left_c}" stroke="#042f2e" stroke-width="0.45"/>'
                f'<polygon points="{fr_pts}" fill="{right_c}" stroke="#042f2e" stroke-width="0.45"/>'
                f'<polygon points="{rf_pts}" fill="{top_c}" stroke="{edge_c}" stroke-width="0.55"/>'
                f'</g>'
            )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none">
  <defs>
    <linearGradient id="cityBg" x1="0" y1="0" x2="{W}" y2="{H}" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#070b14"/>
      <stop offset="60%" stop-color="#0a1220"/>
      <stop offset="100%" stop-color="#07151b"/>
    </linearGradient>
    <linearGradient id="cityBorder" x1="0" y1="0" x2="{W}" y2="{H}" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#1e293b"/>
      <stop offset="60%" stop-color="#115e59" stop-opacity="0.75"/>
      <stop offset="100%" stop-color="#2dd4bf" stop-opacity="0.55"/>
    </linearGradient>
    <radialGradient id="cityGlow" cx="68%" cy="62%" r="36%">
      <stop offset="0%" stop-color="#14b8a6" stop-opacity="0.22"/>
      <stop offset="65%" stop-color="#0ea5e9" stop-opacity="0.06"/>
      <stop offset="100%" stop-color="#0ea5e9" stop-opacity="0"/>
    </radialGradient>
    <style>
      @keyframes blink {{
        0%, 49% {{ opacity: 1; }}
        50%, 100% {{ opacity: 0; }}
      }}
      .sans {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', Ubuntu, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace; }}
    </style>
  </defs>

  <rect x="1.5" y="1.5" width="{W-3}" height="{H-3}" rx="18" fill="url(#cityBg)" stroke="url(#cityBorder)" stroke-width="1.6"/>
  <rect x="2" y="2" width="{W-4}" height="{H-4}" rx="18" fill="url(#cityGlow)"/>

  <text x="42" y="48" fill="#f8fafc" font-size="21" font-weight="700" letter-spacing="-0.3" class="sans">The city I built this year</text>
  <text x="958" y="46" text-anchor="end" fill="#22d3ee" font-size="13" font-weight="600" class="mono">&gt; github-profile-3d<tspan style="animation: blink 1.1s infinite;">_</tspan></text>

  <text x="42" y="104" fill="#2dd4bf" font-size="11.5" font-weight="700" letter-spacing="1.4" class="sans">CONTRIBUTIONS</text>
  <text x="42" y="154" fill="#ffffff" font-size="46" font-weight="800" letter-spacing="-1" class="sans">{total_c}</text>
  <text x="42" y="186" fill="#cbd5e1" font-size="14.5" font-weight="500" class="sans">{active_days} active days</text>
  <text x="42" y="210" fill="#64748b" font-size="13.5" font-weight="500" class="sans">Busiest day: {busiest_cnt}</text>

  <g transform="translate(42, 256)">
    <text x="0" y="11" fill="#64748b" font-size="11" class="mono">Less</text>
    <rect x="34" y="1" width="11" height="11" rx="2.5" fill="#0a2629" stroke="#134e4a" stroke-width="0.8"/>
    <rect x="49" y="1" width="11" height="11" rx="2.5" fill="#0f766e"/>
    <rect x="64" y="1" width="11" height="11" rx="2.5" fill="#14b8a6"/>
    <rect x="79" y="1" width="11" height="11" rx="2.5" fill="#2dd4bf"/>
    <rect x="94" y="1" width="11" height="11" rx="2.5" fill="#99f6e4"/>
    <text x="112" y="11" fill="#64748b" font-size="11" class="mono">More</text>
  </g>

  <g>
    {''.join(bars_svg)}
  </g>
</svg>'''
    with open(os.path.join(ASSETS_DIR, "contribution-city.svg"), "w", encoding="utf-8") as f:
        f.write(svg)


# ==============================================================================
# 3. BOTTOM SPLIT ROW SVG (1000 x 305)
# ==============================================================================
def generate_bottom_svg(data: dict):
    W, H = 1000, 305
    rw = data.get("repo_weighted_pct", {})
    palette = [
        ("#a855f7", "#d946ef"),
        ("#f97316", "#fb7185"),
        ("#38bdf8", "#60a5fa"),
        ("#22d3ee", "#818cf8"),
        ("#facc15", "#f59e0b"),
    ]
    top_langs = list(rw.items())[:5]

    lang_rows_svg = []
    defs_grads = []
    bar_x = 186
    bar_max_w = 238
    for idx, (lname, pct) in enumerate(top_langs):
        c1, c2 = palette[idx % len(palette)]
        gid = f"lgBar{idx}"
        defs_grads.append(
            f'<linearGradient id="{gid}" x1="0%" y1="0%" x2="100%" y2="0%">'
            f'<stop offset="0%" stop-color="{c1}"/><stop offset="100%" stop-color="{c2}"/>'
            f'</linearGradient>'
        )
        ry = 108 + idx * 37
        fill_w = max(14, min(bar_max_w, bar_max_w * (pct / 32.0)))
        pct_disp = f"{round(pct)}%"
        lang_rows_svg.append(f'''
        <g transform="translate(28, {ry})">
          <circle cx="7" cy="8" r="4.5" fill="{c1}"/>
          <text x="22" y="12.5" fill="#e2e8f0" font-size="13.5" font-weight="600" class="sans">{xml_esc(lname)}</text>
          <text x="144" y="12.5" text-anchor="end" fill="#94a3b8" font-size="13" font-weight="600" class="mono">{pct_disp}</text>
          <rect x="{bar_x - 28}" y="3" width="{bar_max_w}" height="10" rx="5" fill="#131c2e"/>
          <rect x="{bar_x - 28}" y="3" width="{fill_w:.1f}" height="10" rx="5" fill="url(#{gid})"/>
        </g>''')

    # Lookup live stars & commits for our 2 featured repos so they auto-update too!
    repos_by_name = {r["name"]: r for r in data["repos"]}
    r_py = repos_by_name.get("python-backend-ai", {"stars": 2, "commits": 16, "pct_by_lang": {"Python": 100}})
    r_nx = repos_by_name.get("Nexus_Tab", {"stars": 1, "commits": 50, "pct_by_lang": {"TypeScript": 69}})

    py_pct = round(r_py.get("pct_by_lang", {}).get("Python", 100))
    nx_pct = round(r_nx.get("pct_by_lang", {}).get("TypeScript", 69))
    py_stars = r_py.get("stars", 2)
    nx_stars = r_nx.get("stars", 1)
    py_commits = r_py.get("commits") or 16
    nx_commits = r_nx.get("commits") or 50

    def project_mini_card(x, y, w, h, name, line1, line2, pct, ring_c1, ring_c2, tag1, tag2, footer_txt, ring_id):
        r_rad = 19.5
        circ = 2 * math.pi * r_rad
        dash = circ * (pct / 100.0)
        return f'''
        <g transform="translate({x}, {y})">
          <defs>
            <linearGradient id="{ring_id}" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="{ring_c1}"/>
              <stop offset="100%" stop-color="{ring_c2}"/>
            </linearGradient>
          </defs>
          <rect x="0" y="0" width="{w}" height="{h}" rx="13" fill="#0d1526" stroke="#1e293b" stroke-width="1.2"/>
          <circle cx="17" cy="24" r="4" fill="{ring_c1}"/>
          <text x="28" y="28.5" fill="#f8fafc" font-size="13.5" font-weight="700" class="sans">{xml_esc(name)}</text>

          <text x="16" y="56" fill="#94a3b8" font-size="11.8" class="sans">{xml_esc(line1)}</text>
          <text x="16" y="74" fill="#94a3b8" font-size="11.8" class="sans">{xml_esc(line2)}</text>

          <g transform="translate({w - 34}, 66)">
            <circle cx="0" cy="0" r="{r_rad}" stroke="#1e293b" stroke-width="3.8" fill="none"/>
            <circle cx="0" cy="0" r="{r_rad}" stroke="url(#{ring_id})" stroke-width="3.8" fill="none"
                    stroke-dasharray="{dash:.1f} {circ:.1f}" stroke-linecap="round" transform="rotate(-90)"/>
            <text x="0" y="3.8" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="700" class="mono">{pct}%</text>
          </g>

          <rect x="16" y="106" width="76" height="22" rx="6" fill="#111c33" stroke="#1e3a5f" stroke-width="0.9"/>
          <text x="54" y="120.5" text-anchor="middle" fill="#38bdf8" font-size="10.5" font-weight="600" class="mono">{xml_esc(tag1)}</text>

          <rect x="98" y="106" width="68" height="22" rx="6" fill="#111c33" stroke="#1e3a5f" stroke-width="0.9"/>
          <text x="132" y="120.5" text-anchor="middle" fill="#94a3b8" font-size="10.5" font-weight="600" class="mono">{xml_esc(tag2)}</text>

          <text x="16" y="156" fill="#64748b" font-size="11.5" font-weight="500" class="sans">{xml_esc(footer_txt)}</text>
        </g>'''

    card1 = project_mini_card(
        x=496, y=102, w=236, h=176,
        name="python-backend-ai",
        line1="Backend & AI progression:",
        line2="FastAPI, pytest & RAG.",
        pct=py_pct, ring_c1="#38bdf8", ring_c2="#818cf8",
        tag1="python-3.12", tag2="backend",
        footer_txt=f"★ {py_stars}  ·  {py_commits} commits  ·  Python",
        ring_id="ringPy"
    )
    card2 = project_mini_card(
        x=744, y=102, w=236, h=176,
        name="Nexus_Tab",
        line1="Autonomous cybernetic",
        line2="in-browser MV3 AI agent.",
        pct=nx_pct, ring_c1="#f97316", ring_c2="#ec4899",
        tag1="typescript", tag2="mv3-ai",
        footer_txt=f"★ {nx_stars}  ·  {nx_commits} commits  ·  MV3",
        ring_id="ringTs"
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none">
  <defs>
    <linearGradient id="panelBg" x1="0" y1="0" x2="500" y2="305" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#070b14"/>
      <stop offset="100%" stop-color="#0b1324"/>
    </linearGradient>
    <linearGradient id="panelBorder" x1="0" y1="0" x2="1000" y2="305" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#1e293b"/>
      <stop offset="50%" stop-color="#1e3a5f" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#0ea5e9" stop-opacity="0.45"/>
    </linearGradient>
    {''.join(defs_grads)}
    <style>
      .sans {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', Ubuntu, sans-serif; }}
      .mono {{ font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace; }}
    </style>
  </defs>

  <!-- LEFT CARD: Language Stack -->
  <rect x="1.5" y="1.5" width="458" height="{H-3}" rx="18" fill="url(#panelBg)" stroke="url(#panelBorder)" stroke-width="1.6"/>
  <text x="28" y="44" fill="#f8fafc" font-size="20" font-weight="700" class="sans">Language Stack</text>
  <text x="434" y="42" text-anchor="end" fill="#22d3ee" font-size="12.5" font-weight="600" class="mono">&gt; stack_scan_</text>
  <text x="28" y="68" fill="#64748b" font-size="12.5" font-weight="500" class="sans">Repository-weighted technologies</text>

  {''.join(lang_rows_svg)}

  <!-- RIGHT CARD: Projects.list -->
  <rect x="476" y="1.5" width="522.5" height="{H-3}" rx="18" fill="url(#panelBg)" stroke="url(#panelBorder)" stroke-width="1.6"/>
  <text x="500" y="44" fill="#f8fafc" font-size="20" font-weight="700" class="sans">Projects.list</text>
  <text x="976" y="42" text-anchor="end" fill="#22d3ee" font-size="12.5" font-weight="600" class="mono">./projects.sh --all</text>
  <text x="500" y="68" fill="#64748b" font-size="12.5" font-weight="500" class="sans">Highlighted public repositories &amp; language share</text>

  {card1}
  {card2}
</svg>'''
    with open(os.path.join(ASSETS_DIR, "stack-and-projects.svg"), "w", encoding="utf-8") as f:
        f.write(svg)


def main():
    data = load_data()
    generate_header_svg(data)
    generate_city_svg(data)
    generate_bottom_svg(data)
    print("Successfully generated all GitSkins SVG cards!")


if __name__ == "__main__":
    main()
