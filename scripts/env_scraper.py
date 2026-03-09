#!/usr/bin/env python3
"""
Sketchfab Environment 3D Model Scraper
========================================
Scrapes Sketchfab's public API v3 by environment-related tags
and extracts embed URLs + full metadata. No login required.

Embed URL format:  https://sketchfab.com/models/{uid}/embed
Use in HTML as:    <iframe src="https://sketchfab.com/models/{uid}/embed" ...></iframe>

Covered environment types:
  terrain, forest, nature, outdoor-environment, landscape,
  mountain, desert, ocean, river, canyon

Usage:
    pip install requests

    python env_scraper.py                        # scrape all default tags
    python env_scraper.py --tags forest terrain  # specific tags only
    python env_scraper.py --count 50             # more results per tag
    python env_scraper.py --out results.json
    python env_scraper.py --token YOUR_SKETCHFAB_TOKEN  # optional, higher rate limits
"""

import argparse
import json
import time
from datetime import datetime, timezone

import requests

# ── Config ─────────────────────────────────────────────────────────────────────

API_BASE   = "https://api.sketchfab.com/v3"
EMBED_BASE = "https://sketchfab.com/models/{uid}/embed"
PAGE_BASE  = "https://sketchfab.com/3d-models/{uid}"

# Environment tags to scrape from Sketchfab
DEFAULT_TAGS = [
    "terrain",
    "forest",
    "nature",
    "outdoor-environment",
    "landscape",
    "mountain",
    "desert",
    "ocean",
    "river",
    "canyon",
]

HEADERS = {"User-Agent": "EnvModelScraper/1.0"}

# ── Helpers ─────────────────────────────────────────────────────────────────────

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def get_license(raw_license):
    if not raw_license:
        return "Unknown"
    return raw_license.get("label") or raw_license.get("slug") or "Unknown"

def get_thumbnail(raw):
    images = (raw.get("thumbnails") or {}).get("images", [])
    if not images:
        return ""
    return max(images, key=lambda x: x.get("width", 0)).get("url", "")

# ── API fetch ──────────────────────────────────────────────────────────────────

def fetch_tag_models(tag: str, count: int, token: str | None) -> list[dict]:
    """Fetch models for a given Sketchfab tag using the /v3/models endpoint."""
    headers = {**HEADERS}
    if token:
        headers["Authorization"] = f"Token {token}"

    params = {
        "tags":     tag,
        "count":    min(count, 24),
        "sort_by":  "-likeCount",
        "type":     "models",
    }

    results = []
    url = f"{API_BASE}/models"

    while url and len(results) < count:
        try:
            r = requests.get(
                url,
                params=params if "sketchfab.com/v3/models" in url else None,
                headers=headers,
                timeout=20,
            )
        except requests.RequestException as e:
            print(f"    [ERROR] {e}")
            break

        if r.status_code == 429:
            print("    [RATE LIMIT] Waiting 15s...")
            time.sleep(15)
            continue

        if not r.ok:
            print(f"    [HTTP {r.status_code}] {r.text[:120]}")
            break

        data = r.json()
        page = data.get("results", [])
        results.extend(page)

        next_url = data.get("next")
        url = next_url if next_url and len(results) < count else None
        params = None  # already encoded in next_url

        time.sleep(0.5)

    return results[:count]

# ── Parse one raw API model into clean entry ───────────────────────────────────

def parse_model(raw: dict, source_tag: str) -> dict:
    uid  = raw.get("uid", "")
    name = raw.get("name", "Untitled")

    user   = raw.get("user") or {}
    author = user.get("displayName") or user.get("username") or "Unknown"

    api_tags   = [t["name"] for t in (raw.get("tags") or []) if t.get("name")]
    categories = [c.get("name", "") for c in (raw.get("categories") or [])]

    return {
        # ── Identity
        "id":           f"MDL-{uid[:8].upper()}",
        "uid":          uid,
        "name":         name,
        "source_tag":   source_tag,

        # ── Embed (the main thing you wanted)
        "embed_url":    EMBED_BASE.format(uid=uid),
        "page_url":     PAGE_BASE.format(uid=uid),
        "thumbnail_url": get_thumbnail(raw),

        # ── Content
        "description":  (raw.get("description") or "")[:400].strip(),
        "tags":         list(dict.fromkeys([source_tag] + api_tags)),
        "categories":   categories,

        # ── Author / License
        "author":       author,
        "author_url":   f"https://sketchfab.com/{user.get('username', '')}",
        "license":      get_license(raw.get("license")),

        # ── Geometry
        "vertex_count":    raw.get("vertexCount"),
        "face_count":      raw.get("faceCount"),
        "animation_count": raw.get("animationCount", 0),
        "is_downloadable": raw.get("isDownloadable", False),

        # ── Stats
        "view_count":   raw.get("viewCount", 0),
        "like_count":   raw.get("likeCount", 0),
        "published_at": raw.get("publishedAt", ""),
        "scraped_at":   now_iso(),
    }

# ── Main ───────────────────────────────────────────────────────────────────────

def run(tags: list[str], count: int, token: str | None, out_file: str):
    all_models = []
    seen_uids  = set()

    for tag in tags:
        print(f"\n→ Tag: [{tag}]  (fetching up to {count})")
        raw_list = fetch_tag_models(tag, count, token)
        print(f"  API returned {len(raw_list)} results")

        added = 0
        for raw in raw_list:
            uid = raw.get("uid", "")
            if uid in seen_uids:
                continue
            seen_uids.add(uid)
            all_models.append(parse_model(raw, tag))
            added += 1

        print(f"  Added {added} unique models  (running total: {len(all_models)})")

    # ── Write output ────────────────────────────────────────────────────────────
    output = {
        "metadata_version": "1.0",
        "generated_at":     now_iso(),
        "source":           "Sketchfab API v3",
        "tags_scraped":     tags,
        "total_models":     len(all_models),
        "embed_usage":      "<iframe src='{embed_url}' width='640' height='480' frameborder='0'></iframe>",
        "models":           all_models,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✓  Saved {len(all_models)} models → {out_file}")

    # ── Quick embed URL preview ─────────────────────────────────────────────────
    print("\n── Sample Embed URLs ─────────────────────────────────────────────────")
    by_tag: dict[str, list] = {}
    for m in all_models:
        by_tag.setdefault(m["source_tag"], []).append(m)

    for tag, models in by_tag.items():
        print(f"\n  [{tag}]")
        for m in models[:3]:
            print(f"    {m['name'][:45]:45s}  {m['embed_url']}")

# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scrape Sketchfab environment 3D models and extract embed URLs"
    )
    parser.add_argument(
        "--tags", nargs="+", default=DEFAULT_TAGS,
        metavar="TAG",
        help=f"Tags to scrape (default: {' '.join(DEFAULT_TAGS)})"
    )
    parser.add_argument(
        "--count", type=int, default=24,
        help="Max models per tag (default: 24)"
    )
    parser.add_argument(
        "--token",
        help="Sketchfab API token (optional — get free at sketchfab.com/settings/password)"
    )
    parser.add_argument(
        "--out", default="env_models.json",
        help="Output JSON file (default: env_models.json)"
    )
    args = parser.parse_args()
    run(args.tags, args.count, args.token, args.out)

if __name__ == "__main__":
    main()
