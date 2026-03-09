#!/usr/bin/env python3
"""
Objaverse Full Metadata Scraper
=================================
Streams all 800K+ object annotations directly from HuggingFace
(https://huggingface.co/datasets/allenai/objaverse) and extracts
embed URLs + full metadata with domain classification for FAISS indexing.

No objaverse package needed. No model downloads. Pure metadata.

Each annotation already contains an embedUrl field:
  https://sketchfab.com/models/{uid}/embed

Domain classification is attached to every entry so you can build
FAISS indexes per-domain or filter before indexing.

Output: objaverse_metadata.jsonl  (one JSON object per line, ~800K lines)
        objaverse_metadata.json   (full structured output, use --format json)

Usage:
    pip install requests tqdm

    # Full scrape (all 800K objects, ~160 chunks):
    python objaverse_scraper.py

    # Scrape only first N chunks (each chunk ~5K objects):
    python objaverse_scraper.py --chunks 10

    # Only keep objects matching specific domains:
    python objaverse_scraper.py --domains nature environment architecture vehicle

    # Output format (jsonl = streaming friendly, json = all in one file):
    python objaverse_scraper.py --format jsonl
    python objaverse_scraper.py --format json

    # Resume a partial scrape (skips already-written UIDs):
    python objaverse_scraper.py --resume

    # Custom output path:
    python objaverse_scraper.py --out my_metadata.jsonl
"""

import argparse
import gzip
import json
import re
import sys
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import requests
from tqdm import tqdm

# ── Constants ──────────────────────────────────────────────────────────────────

HF_BASE     = "https://huggingface.co/datasets/allenai/objaverse/resolve/main"
METADATA_URL = HF_BASE + "/metadata/{chunk_id}.json.gz"
LVIS_URL     = HF_BASE + "/lvis-annotations.json.gz"

TOTAL_CHUNKS = 160   # 000-000 through 159-000 (format: {i//1000:03d}-{i%1000:03d})
EMBED_BASE   = "https://sketchfab.com/models/{uid}/embed"
PAGE_BASE    = "https://sketchfab.com/3d-models/{uid}"

HEADERS = {
    "User-Agent": "ObjaverseScraper/1.0 (metadata-only, no model downloads)"
}

# ── Domain taxonomy for FAISS indexing ────────────────────────────────────────
# Each domain maps to a list of keyword signals (checked against name + tags + categories).
# Order matters: first match wins. "general" is the fallback.

DOMAIN_TAXONOMY = {
    # ── Natural environments
    "nature":           ["tree", "forest", "plant", "flower", "grass", "leaf",
                         "bush", "botanical", "vegetation", "fungus", "mushroom",
                         "coral", "seaweed", "moss", "fern", "bark", "wood", "log"],
    "terrain":          ["terrain", "landscape", "mountain", "hill", "valley",
                         "cliff", "canyon", "rock", "stone", "boulder", "island",
                         "glacier", "tundra", "mesa", "plateau", "dune", "sand"],
    "water":            ["ocean", "sea", "river", "lake", "pond", "waterfall",
                         "wave", "underwater", "aquatic", "coast", "beach",
                         "reef", "tide", "stream", "creek", "bay", "fjord"],
    "sky_weather":      ["cloud", "sky", "atmosphere", "storm", "fog", "mist",
                         "rain", "snow", "lightning", "aurora", "nebula"],
    "animal":           ["animal", "bird", "fish", "insect", "mammal", "reptile",
                         "dinosaur", "creature", "wildlife", "pet", "dog", "cat",
                         "horse", "dragon", "monster", "beast", "deer", "wolf",
                         "bear", "shark", "whale", "butterfly", "spider"],

    # ── Built environment
    "architecture":     ["building", "house", "castle", "temple", "church",
                         "mosque", "tower", "bridge", "arch", "ruin", "monument",
                         "statue", "facade", "interior", "room", "apartment",
                         "skyscraper", "barn", "cabin", "lighthouse", "wall",
                         "staircase", "pillar", "column", "roof"],
    "urban":            ["city", "street", "road", "highway", "urban", "town",
                         "sidewalk", "alley", "intersection", "district", "block",
                         "suburb", "neighborhood", "plaza", "park", "square"],
    "infrastructure":   ["bridge", "dam", "pipeline", "power", "rail", "tunnel",
                         "airport", "port", "harbor", "crane", "factory",
                         "warehouse", "sewer", "utility"],

    # ── Vehicles & transport
    "vehicle_land":     ["car", "truck", "bus", "motorcycle", "bicycle", "tank",
                         "tractor", "train", "van", "suv", "jeep", "trailer",
                         "ambulance", "police car", "fire truck"],
    "vehicle_air":      ["airplane", "aircraft", "helicopter", "drone", "jet",
                         "rocket", "shuttle", "blimp", "glider", "ufo"],
    "vehicle_water":    ["boat", "ship", "submarine", "yacht", "canoe", "kayak",
                         "ferry", "destroyer", "carrier", "sailboat"],
    "vehicle_space":    ["spaceship", "spacecraft", "satellite", "probe",
                         "space station", "lander", "capsule"],

    # ── Human figure
    "character_human":  ["human", "person", "man", "woman", "girl", "boy",
                         "character", "avatar", "body", "face", "head",
                         "soldier", "warrior", "knight", "civilian"],
    "character_fantasy": ["elf", "orc", "goblin", "troll", "vampire", "zombie",
                          "alien", "robot", "android", "cyborg", "mech"],

    # ── Objects & props
    "weapon":           ["sword", "gun", "rifle", "pistol", "bow", "arrow",
                         "axe", "spear", "shield", "armor", "knife", "blade"],
    "furniture":        ["chair", "table", "desk", "sofa", "couch", "bed",
                         "shelf", "cabinet", "lamp", "wardrobe", "bench"],
    "food":             ["food", "fruit", "vegetable", "bread", "meat", "cake",
                         "drink", "bottle", "cup", "bowl", "meal", "snack"],
    "tool":             ["tool", "wrench", "hammer", "drill", "saw", "screwdriver",
                         "key", "lock", "gear", "machine", "engine", "pump"],
    "electronics":      ["computer", "laptop", "phone", "tablet", "camera",
                         "tv", "monitor", "speaker", "headphone", "console",
                         "circuit", "chip", "keyboard", "mouse"],
    "clothing":         ["shirt", "shoe", "hat", "jacket", "dress", "pants",
                         "helmet", "glove", "bag", "backpack", "uniform"],

    # ── Art & abstract
    "art_sculpture":    ["sculpture", "bust", "figurine", "abstract", "art",
                         "painting", "relief", "carving", "mosaic"],
    "symbol_logo":      ["logo", "symbol", "icon", "sign", "badge", "emblem",
                         "text", "letter", "number", "flag"],

    # ── Science & medical
    "science":          ["molecule", "cell", "dna", "brain", "heart", "organ",
                         "skeleton", "bone", "anatomical", "laboratory",
                         "microscope", "chemical", "crystal", "mineral"],

    # ── Space & sci-fi
    "space":            ["space", "planet", "moon", "star", "galaxy", "asteroid",
                         "cosmos", "universe", "nebula", "exoplanet"],

    # ── Game assets
    "game_asset":       ["game", "asset", "prop", "level", "dungeon", "arena",
                         "rpg", "fps", "voxel", "low poly", "pbr"],
}

ALL_DOMAINS = list(DOMAIN_TAXONOMY.keys()) + ["general"]

# ── Helpers ────────────────────────────────────────────────────────────────────

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def chunk_id(i: int) -> str:
    return f"{i // 1000:03d}-{i % 1000:03d}"

def classify_domain(name: str, tags: list[str], categories: list[str]) -> list[str]:
    """
    Classify an object into one or more domains for FAISS indexing.
    Returns a list of matched domains (can be multiple). Falls back to ['general'].
    Uses keyword matching against name + tags + categories combined.
    """
    # Build a single lowercased search text
    tag_names  = [t["name"].lower() if isinstance(t, dict) else t.lower() for t in tags]
    cat_names  = [c["name"].lower() if isinstance(c, dict) else c.lower() for c in categories]
    search_txt = " ".join([name.lower()] + tag_names + cat_names)

    matched = []
    for domain, keywords in DOMAIN_TAXONOMY.items():
        if any(kw in search_txt for kw in keywords):
            matched.append(domain)

    return matched if matched else ["general"]

def build_faiss_text(entry: dict) -> str:
    """
    Build the text string that should be embedded for FAISS indexing.
    Combines name, description, tags, categories, and domain.
    """
    parts = [
        entry.get("name", ""),
        entry.get("description", ""),
        " ".join(entry.get("tags", [])),
        " ".join(entry.get("categories", [])),
        " ".join(entry.get("domains", [])),
    ]
    return " | ".join(p for p in parts if p.strip())

def get_thumbnail(raw: dict) -> str:
    images = (raw.get("thumbnails") or {}).get("images", [])
    if not images:
        return ""
    return max(images, key=lambda x: x.get("width", 0)).get("url", "")

def get_license(raw: dict) -> str:
    lic = raw.get("license") or {}
    if isinstance(lic, dict):
        return lic.get("label") or lic.get("slug") or "Unknown"
    return str(lic) or "Unknown"

# ── Fetch one metadata chunk ───────────────────────────────────────────────────

def fetch_chunk(chunk_idx: int, retries: int = 3) -> dict:
    cid = chunk_id(chunk_idx)
    url = METADATA_URL.format(chunk_id=cid)

    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            if r.status_code == 404:
                return {}  # chunk doesn't exist (sparse numbering at edges)
            r.raise_for_status()
            buf = BytesIO(r.content)
            with gzip.open(buf, "rb") as f:
                return json.load(f)
        except Exception as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"\n  [WARN] chunk {cid} attempt {attempt+1} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"\n  [ERROR] chunk {cid} failed after {retries} attempts: {e}", file=sys.stderr)
                return {}

# ── Parse one raw annotation into clean entry ──────────────────────────────────

def parse_annotation(uid: str, raw: dict, lvis_map: dict) -> dict:
    name        = raw.get("name", "Untitled") or "Untitled"
    description = (raw.get("description") or "")[:500].strip()
    tags_raw    = raw.get("tags") or []
    cats_raw    = raw.get("categories") or []

    tag_names = [t["name"] if isinstance(t, dict) else t for t in tags_raw]
    cat_names = [c["name"] if isinstance(c, dict) else c for c in cats_raw]

    lvis_categories = lvis_map.get(uid, [])
    domains = classify_domain(name, tag_names + lvis_categories, cat_names)

    entry = {
        # ── Identity
        "uid":          uid,
        "name":         name,

        # ── Embed (ready for iframe / viewer)
        "embed_url":    raw.get("embedUrl") or EMBED_BASE.format(uid=uid),
        "page_url":     raw.get("viewerUrl") or PAGE_BASE.format(uid=uid),
        "thumbnail_url": get_thumbnail(raw),

        # ── Content
        "description":  description,
        "tags":         tag_names,
        "categories":   cat_names,
        "lvis_categories": lvis_categories,

        # ── Domain classification (for FAISS indexing / filtering)
        "domains":      domains,
        "primary_domain": domains[0],

        # ── FAISS-ready text field (embed this string with your encoder)
        "faiss_text":   build_faiss_text({
            "name": name, "description": description,
            "tags": tag_names, "categories": cat_names,
            "domains": domains,
        }),

        # ── Author / License
        "author":       (raw.get("user") or {}).get("displayName") or
                        (raw.get("user") or {}).get("username") or "Unknown",
        "license":      get_license(raw),

        # ── Stats
        "view_count":       raw.get("viewCount", 0),
        "like_count":       raw.get("likeCount", 0),
        "comment_count":    raw.get("commentCount", 0),
        "animation_count":  raw.get("animationCount", 0),
        "is_downloadable":  raw.get("isDownloadable", False),
        "is_staff_picked":  raw.get("staffpickedAt") is not None,
        "published_at":     raw.get("publishedAt", ""),

        # ── Source info
        "source":       "objaverse-1.0",
        "source_url":   "https://objaverse.allenai.org/",
        "hf_dataset":   "allenai/objaverse",
        "scraped_at":   now_iso(),
    }

    return entry

# ── Load LVIS annotations (uid → [category, ...]) ─────────────────────────────

def load_lvis(cache_path: Path) -> dict:
    """
    Returns a reverse map: { uid: [lvis_category, ...] }
    Downloaded from HuggingFace and cached locally.
    """
    if cache_path.exists():
        print("  Loading LVIS annotations from cache...")
        with gzip.open(cache_path, "rb") as f:
            raw = json.load(f)
    else:
        print("  Downloading LVIS annotations from HuggingFace...")
        r = requests.get(LVIS_URL, headers=HEADERS, timeout=120)
        r.raise_for_status()
        cache_path.write_bytes(r.content)
        with gzip.open(BytesIO(r.content), "rb") as f:
            raw = json.load(f)

    # raw = { category: [uid1, uid2, ...] }
    # Invert to: { uid: [cat1, cat2, ...] }
    uid_to_cats: dict[str, list[str]] = {}
    for cat, uids in raw.items():
        for uid in uids:
            uid_to_cats.setdefault(uid, []).append(cat)

    print(f"  LVIS: {len(uid_to_cats):,} objects across {len(raw):,} categories")
    return uid_to_cats

# ── Main scrape loop ───────────────────────────────────────────────────────────

def run(
    n_chunks: int,
    domains_filter: list[str] | None,
    out_file: str,
    fmt: str,
    resume: bool,
):
    out_path   = Path(out_file)
    cache_dir  = Path(".objaverse_cache")
    cache_dir.mkdir(exist_ok=True)
    lvis_cache = cache_dir / "lvis-annotations.json.gz"

    # Load LVIS category annotations
    print("\n[1/3] Loading LVIS annotations...")
    try:
        lvis_map = load_lvis(lvis_cache)
    except Exception as e:
        print(f"  [WARN] Could not load LVIS: {e}. Continuing without it.", file=sys.stderr)
        lvis_map = {}

    # Resume: load already-seen UIDs
    seen_uids: set[str] = set()
    if resume and out_path.exists():
        print(f"\n[2/3] Resuming — scanning existing output for seen UIDs...")
        with open(out_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    if obj.get("uid"):
                        seen_uids.add(obj["uid"])
                except Exception:
                    pass
        print(f"  Found {len(seen_uids):,} already-scraped objects.")
    else:
        print("\n[2/3] Starting fresh scrape...")

    # Domain stats tracker
    domain_counts: dict[str, int] = {d: 0 for d in ALL_DOMAINS}

    # Open output file
    file_mode = "a" if resume else "w"
    all_entries = []  # used for json format only
    total_written = 0

    print(f"\n[3/3] Streaming {n_chunks} chunks from HuggingFace...")
    print(f"      Output: {out_path}  |  Format: {fmt}")
    if domains_filter:
        print(f"      Domain filter: {domains_filter}")
    print()

    with open(out_path, file_mode, encoding="utf-8") as out_f:
        chunk_bar = tqdm(range(n_chunks), unit="chunk", desc="Chunks", position=0)

        for i in chunk_bar:
            data = fetch_chunk(i)
            if not data:
                continue

            chunk_entries = []
            for uid, raw in data.items():
                if uid in seen_uids:
                    continue

                entry = parse_annotation(uid, raw, lvis_map)

                # Domain filter
                if domains_filter:
                    if not any(d in entry["domains"] for d in domains_filter):
                        continue

                # Track domain counts
                for d in entry["domains"]:
                    domain_counts[d] = domain_counts.get(d, 0) + 1

                chunk_entries.append(entry)
                seen_uids.add(uid)

            # Write this chunk
            for entry in chunk_entries:
                if fmt == "jsonl":
                    out_f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                else:
                    all_entries.append(entry)

            total_written += len(chunk_entries)
            chunk_bar.set_postfix({
                "written": f"{total_written:,}",
                "chunk": chunk_id(i),
            })

            time.sleep(0.2)  # polite delay

    # For json format, write all at once
    if fmt == "json":
        top_domains = sorted(domain_counts.items(), key=lambda x: -x[1])
        output = {
            "metadata_version": "1.0",
            "generated_at":     now_iso(),
            "source":           "allenai/objaverse via HuggingFace",
            "source_url":       "https://objaverse.allenai.org/",
            "hf_dataset_url":   "https://huggingface.co/datasets/allenai/objaverse",
            "chunks_scraped":   n_chunks,
            "total_objects":    total_written,
            "domains_present":  ALL_DOMAINS,
            "domain_counts":    dict(top_domains),
            "faiss_notes": {
                "text_field":   "faiss_text",
                "id_field":     "uid",
                "filter_field": "primary_domain",
                "all_domains":  ALL_DOMAINS,
                "usage":        "Encode `faiss_text` with a sentence-transformer. Use `primary_domain` to build per-domain FAISS indexes.",
            },
            "models": all_entries,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    # Print domain summary
    print(f"\n✓ Done! {total_written:,} objects written → {out_path}")
    print("\n── Domain Distribution ───────────────────────────────────────────────")
    top = sorted(domain_counts.items(), key=lambda x: -x[1])
    for domain, count in top:
        if count > 0:
            bar = "█" * min(40, int(count / max(1, total_written) * 40))
            print(f"  {domain:22s}  {count:7,}  {bar}")

    print("\n── FAISS Indexing Tips ────────────────────────────────────────────────")
    print("  • Encode the `faiss_text` field per object with a sentence-transformer")
    print("  • Use `primary_domain` to build separate per-domain FAISS indexes")
    print("  • Use `uid` as the FAISS index ID (maps back to embed_url)")
    print("  • Filter by `domains` list for multi-domain objects")
    print(f"  • embed_url = https://sketchfab.com/models/{{uid}}/embed")

# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scrape all Objaverse metadata with embed URLs + domain classification"
    )
    parser.add_argument(
        "--chunks", type=int, default=TOTAL_CHUNKS,
        help=f"Number of metadata chunks to scrape (default: {TOTAL_CHUNKS} = all ~800K objects). Each chunk ~5K objects."
    )
    parser.add_argument(
        "--domains", nargs="+",
        choices=ALL_DOMAINS,
        metavar="DOMAIN",
        help=f"Only keep objects matching these domains. Choices: {', '.join(ALL_DOMAINS)}"
    )
    parser.add_argument(
        "--format", choices=["jsonl", "json"], default="jsonl",
        help="Output format: jsonl (one object per line, streaming-friendly) or json (full structured). Default: jsonl"
    )
    parser.add_argument(
        "--out", default="objaverse_metadata.jsonl",
        help="Output file path (default: objaverse_metadata.jsonl)"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume a partial scrape (skips UIDs already in the output file)"
    )
    args = parser.parse_args()

    print("━" * 60)
    print("  Objaverse Full Metadata Scraper")
    print("  Source: allenai/objaverse (HuggingFace)")
    print(f"  Chunks: {args.chunks} / {TOTAL_CHUNKS} (~{args.chunks * 5000:,} objects)")
    print(f"  Format: {args.format}")
    print(f"  Output: {args.out}")
    print("━" * 60)

    run(
        n_chunks=args.chunks,
        domains_filter=args.domains,
        out_file=args.out,
        fmt=args.format,
        resume=args.resume,
    )

if __name__ == "__main__":
    main()
