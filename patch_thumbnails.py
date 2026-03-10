"""
patch_thumbnails.py — ConceptCraftAI
Patches indexes/biological.json with thumbnail URLs for sources that have them.

Sources patched:
  - RCSB PDB     : extracts PDB ID from embed_url → RCSB CDN thumbnail
  - Sketchfab    : extracts model UID from url → Sketchfab thumbnail API
  - NIH 3D Print : constructs thumbnail from model ID

Run once. Creates a backup at indexes/biological.json.bak before patching.
"""

import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BIOLOGICAL_JSON = Path("indexes/biological.json")
BACKUP_PATH     = Path("indexes/biological.json.bak")

# ── Load ──────────────────────────────────────────────────────────────────────
print("Loading biological.json...")
with open(BIOLOGICAL_JSON, encoding="utf-8") as f:
    data = json.load(f)
print(f"  {len(data)} entries loaded")

# ── Backup ────────────────────────────────────────────────────────────────────
if not BACKUP_PATH.exists():
    shutil.copy(BIOLOGICAL_JSON, BACKUP_PATH)
    print(f"  Backup saved to {BACKUP_PATH}")
else:
    print(f"  Backup already exists, skipping")

# ── Patch functions ───────────────────────────────────────────────────────────

def _has_thumbnail(m: dict) -> bool:
    return bool(m.get("thumbnail_url") or m.get("thumbnail") or m.get("image_url"))


def patch_rcsb(m: dict) -> bool:
    """
    Extract PDB ID from embed_url like:
      https://3dmol.csb.pitt.edu/viewer.html?pdb=2F43&style=cartoon
    → thumbnail: https://cdn.rcsb.org/images/structures/2f43/2f43_assembly-1.jpeg
    """
    embed = m.get("embed_url") or ""
    if "3dmol.csb.pitt.edu" not in embed:
        return False
    try:
        params = parse_qs(urlparse(embed).query)
        pdb_id = params.get("pdb", [None])[0]
        if not pdb_id:
            return False
        pdb_id = pdb_id.lower()
        m["thumbnail_url"] = f"https://cdn.rcsb.org/images/structures/{pdb_id[:2]}/{pdb_id}/{pdb_id}_assembly-1.jpeg"
        return True
    except Exception:
        return False


def patch_sketchfab(m: dict) -> bool:
    """
    Extract model UID from Sketchfab URL like:
      https://sketchfab.com/3d-models/some-name-UID
    → thumbnail: https://media.sketchfab.com/models/UID/thumbnails/UID-200x200.jpeg
    Falls back to checking 'uid' or 'model_uid' fields directly.
    """
    # Try direct uid field first
    uid = m.get("uid") or m.get("model_uid") or m.get("sketchfab_uid")
    if not uid:
        # Try extracting from URL
        url = m.get("url") or m.get("embed_url") or ""
        match = re.search(r'sketchfab\.com/3d-models/[^/]+-([a-f0-9]{32})', url)
        if match:
            uid = match.group(1)
    if not uid:
        return False
    m["thumbnail_url"] = f"https://media.sketchfab.com/models/{uid}/thumbnails/default.jpeg"
    return True


def patch_nih(m: dict) -> bool:
    """
    NIH 3D Print Exchange thumbnails.
    URL format: https://3dprint.nih.gov/discover/3dpx-XXXXXX
    → thumbnail: https://3dprint.nih.gov/sites/default/files/styles/preview/public/3dpx-XXXXXX.jpg
    """
    url = m.get("url") or m.get("embed_url") or ""
    match = re.search(r'3dprint\.nih\.gov/discover/(3dpx-\d+)', url)
    if not match:
        return False
    model_id = match.group(1)
    m["thumbnail_url"] = f"https://3dprint.nih.gov/sites/default/files/styles/preview/public/{model_id}.jpg"
    return True


def patch_animals_sketchfab(m: dict) -> bool:
    """
    Animals metadata from Sketchfab — URLs like:
      https://sketchfab.com/tags/cow
    These are tag pages, not model pages, so no direct thumbnail.
    Skip these — they need individual model UIDs.
    """
    return False


# ── Run patches ───────────────────────────────────────────────────────────────
stats = {
    "rcsb":      {"tried": 0, "patched": 0},
    "sketchfab": {"tried": 0, "patched": 0},
    "nih":       {"tried": 0, "patched": 0},
    "skipped":   0,
    "already":   0,
}

for m in data:
    if _has_thumbnail(m):
        stats["already"] += 1
        continue

    source = str(m.get("source") or m.get("source_file") or "").lower()
    patched = False

    # RCSB PDB
    if "rcsb" in source or "pdb" in source or "3dmol" in str(m.get("embed_url") or ""):
        stats["rcsb"]["tried"] += 1
        patched = patch_rcsb(m)
        if patched:
            stats["rcsb"]["patched"] += 1

    # Sketchfab
    elif "sketchfab" in source or "sketchfab" in str(m.get("url") or ""):
        stats["sketchfab"]["tried"] += 1
        patched = patch_sketchfab(m)
        if patched:
            stats["sketchfab"]["patched"] += 1

    # NIH
    elif "nih" in source or "3dprint.nih" in str(m.get("url") or ""):
        stats["nih"]["tried"] += 1
        patched = patch_nih(m)
        if patched:
            stats["nih"]["patched"] += 1

    if not patched and not _has_thumbnail(m):
        stats["skipped"] += 1

# ── Save ──────────────────────────────────────────────────────────────────────
print("\nSaving patched biological.json...")
with open(BIOLOGICAL_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

# ── Report ────────────────────────────────────────────────────────────────────
total_with_thumb = sum(1 for m in data if _has_thumbnail(m))

print("\n── Patch Results ─────────────────────────────────────────")
print(f"  Already had thumbnail : {stats['already']}")
print(f"  RCSB PDB patched      : {stats['rcsb']['patched']} / {stats['rcsb']['tried']} tried")
print(f"  Sketchfab patched     : {stats['sketchfab']['patched']} / {stats['sketchfab']['tried']} tried")
print(f"  NIH patched           : {stats['nih']['patched']} / {stats['nih']['tried']} tried")
print(f"  Skipped (no match)    : {stats['skipped']}")
print(f"──────────────────────────────────────────────────────────")
print(f"  Total with thumbnail  : {total_with_thumb} / {len(data)} ({100*total_with_thumb//len(data)}%)")
print(f"\nDone. Run your server and CLIP will now have images to compare against.")
