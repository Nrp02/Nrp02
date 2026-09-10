#!/usr/bin/env python3
"""Fill assets/profile-card-template.svg with live GitHub data -> dist/profile-card.svg."""

import json
import os
import sys
import urllib.request

USERNAME = os.environ.get("GITHUB_USERNAME", "Nrp02")
TOKEN = os.environ.get("GITHUB_TOKEN")
API_ROOT = "https://api.github.com"
TOP_N_LANGUAGES = 4


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
    top_languages = sorted(language_bytes, key=language_bytes.get, reverse=True)[:TOP_N_LANGUAGES]

    try:
        total_commits = fetch_total_commits()
    except Exception as exc:
        print(f"warning: could not fetch commit count via GraphQL: {exc}", file=sys.stderr)
        total_commits = "N/A"

    values = {
        "{{REPOS}}": str(user.get("public_repos", len(repos))),
        "{{STARS}}": str(total_stars),
        "{{COMMITS}}": str(total_commits),
        "{{FOLLOWERS}}": str(user.get("followers", 0)),
        "{{LANGUAGES}}": ", ".join(top_languages) if top_languages else "N/A",
    }

    with open("assets/profile-card-template.svg", "r", encoding="utf-8") as f:
        svg = f.read()

    for token, value in values.items():
        svg = svg.replace(token, value)

    os.makedirs("dist", exist_ok=True)
    with open("dist/profile-card.svg", "w", encoding="utf-8") as f:
        f.write(svg)

    print("Generated dist/profile-card.svg with:", values)


if __name__ == "__main__":
    main()
