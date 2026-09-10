#!/usr/bin/env python3
"""Fill assets/profile-card-template.svg with live GitHub data -> dist/profile-card.svg."""

import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

USERNAME = os.environ.get("GITHUB_USERNAME", "Nrp02")
TOKEN = os.environ.get("GITHUB_TOKEN")
API_ROOT = "https://api.github.com"
TOP_N_LANGUAGES = 4

BAR_X = 470
BAR_WIDTH = 590
BAR_HEIGHT = 6
BAR_FIRST_Y = 316
BAR_ROW_SPACING = 34
BAR_COLORS = ["#93a6ef", "#6d7fd6", "#dbe2fb", "#4a5386"]

ROW_X = 470
VALUE_RIGHT = 1060
CHAR_W = 10.2  # widest advance in the template's monospace stack, at 17px


def dot_leader(key, value):
    """Dots filling the gap between a left-aligned key and a right-aligned value."""
    key_end = ROW_X + len(f". {key}:") * CHAR_W
    value_start = VALUE_RIGHT - len(value) * CHAR_W
    return "." * max(1, int((value_start - key_end) / CHAR_W) - 2)


def api_get(path):
    req = urllib.request.Request(API_ROOT + path)
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def graphql(query):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_repos():
    repos, page = [], 1
    while True:
        batch = api_get(f"/users/{USERNAME}/repos?per_page=100&page={page}&type=owner")
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def fetch_languages(repo_full_name):
    try:
        return api_get(f"/repos/{repo_full_name}/languages")
    except Exception:
        return {}


def build_language_stack_svg(language_bytes):
    top = sorted(language_bytes.items(), key=lambda kv: kv[1], reverse=True)[:TOP_N_LANGUAGES]
    if not top:
        return f'<text x="{BAR_X}" y="{BAR_FIRST_Y}"><tspan class="dim">. </tspan><tspan class="value">No language data yet</tspan></text>'

    shown_total = sum(count for _, count in top)
    rows = []
    for i, (lang, count) in enumerate(top):
        pct = round(100 * count / shown_total) if shown_total else 0
        y = BAR_FIRST_Y + i * BAR_ROW_SPACING
        bar_y = y + BAR_HEIGHT
        fill_width = round(BAR_WIDTH * pct / 100)
        color = BAR_COLORS[i % len(BAR_COLORS)]
        rows.append(
            f'<text x="{BAR_X}" y="{y}"><tspan class="key">{escape(lang)}</tspan></text>'
            f'<text x="{BAR_X + BAR_WIDTH}" y="{y}" text-anchor="end">'
            f'<tspan class="value">{pct}%</tspan></text>'
            f'<rect x="{BAR_X}" y="{bar_y}" width="{BAR_WIDTH}" height="{BAR_HEIGHT}" rx="0" fill="#3c4670"/>'
            f'<rect x="{BAR_X}" y="{bar_y}" width="{fill_width}" height="{BAR_HEIGHT}" rx="0" fill="{color}"/>'
        )
    return "\n    ".join(rows)


def fetch_total_commits():
    query = f'''
    {{
      user(login: "{USERNAME}") {{
        contributionsCollection {{
          totalCommitContributions
          restrictedContributionsCount
        }}
      }}
    }}
    '''
    data = graphql(query)
    collection = data["data"]["user"]["contributionsCollection"]
    return collection["totalCommitContributions"] + collection["restrictedContributionsCount"]


def main():
    user = api_get(f"/users/{USERNAME}")
    repos = fetch_repos()

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)

    language_bytes = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        for lang, byte_count in fetch_languages(repo["full_name"]).items():
            language_bytes[lang] = language_bytes.get(lang, 0) + byte_count
    language_stack_svg = build_language_stack_svg(language_bytes)

    try:
        total_commits = fetch_total_commits()
    except Exception as exc:
        print(f"warning: could not fetch commit count via GraphQL: {exc}", file=sys.stderr)
        total_commits = "N/A"

    repos_value = str(user.get("public_repos", len(repos)))
    commits_value = str(total_commits)
    followers_value = str(user.get("followers", 0))

    values = {
        "{{REPOS}}": repos_value,
        "{{STARS}}": str(total_stars),
        "{{COMMITS}}": commits_value,
        "{{FOLLOWERS}}": followers_value,
        "{{REPOS_DOTS}}": dot_leader("Repos", repos_value),
        "{{COMMITS_DOTS}}": dot_leader("Commits", commits_value),
        "{{FOLLOWERS_DOTS}}": dot_leader("Followers", followers_value),
    }

    with open("assets/profile-card-template.svg", "r", encoding="utf-8") as f:
        svg = f.read()

    svg = svg.replace("<!--{{LANGUAGE_STACK}}-->", language_stack_svg)
    for token, value in values.items():
        svg = svg.replace(token, value)

    os.makedirs("dist", exist_ok=True)
    with open("dist/profile-card.svg", "w", encoding="utf-8") as f:
        f.write(svg)

    print("Generated dist/profile-card.svg with:", values)


if __name__ == "__main__":
    main()
