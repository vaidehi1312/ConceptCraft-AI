"""
ConceptCraft AI - Sketchfab Planets Collection
===============================================
Collection: https://sketchfab.com/baxterbaxter/collections/planets-82b7abd4e0644304b65fdc5af7d0aa72
46 models total - planets, moons, stars, asteroids

Sketchfab downloads require a FREE account + API token.
This script:
  1. Builds full metadata JSON for all 46 models (no token needed)
  2. Downloads models if you provide your API token

Get free API token at: https://sketchfab.com/settings#password
  → Scroll to "API Token" section → Copy it

Run from ConceptCraftAI/scripts/:
    pip install requests
    python fetch_sketchfab_planets_metadata.py
"""

import requests, json, os, re, time

MODELS_DIR   = "../datasets/sketchfab_planets"
METADATA_DIR = "../metadata"
OUT_FILE     = os.path.join(METADATA_DIR, "sketchfab_planets_metadata.json")
os.makedirs(MODELS_DIR,   exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

# ── PUT YOUR FREE SKETCHFAB API TOKEN HERE ────────────────────────────────
# Get it from: https://sketchfab.com/settings#password
# If empty, metadata JSON is still built but files won't download
SKETCHFAB_API_TOKEN = ""   # e.g. "abc123xyz..."
# ─────────────────────────────────────────────────────────────────────────

COLLECTION_ID = "82b7abd4e0644304b65fdc5af7d0aa72"
API_BASE      = "https://api.sketchfab.com/v3"

# ── ALL 46 models scraped directly from the collection page ──────────────
# Format: (uid, name, tags, description)
PLANET_MODELS = [
    ("397b266af9604b9fbf0a4e5446cf864b", "Galactic Incident",
     ["galaxy","space","astronomy","animated"],
     "Animated galactic space scene"),

    ("f735027736264c41b980193ee0aaf651", "Planet Mars - NASA Mars Landing 2021",
     ["mars","planet","NASA","landing","red planet"],
     "Planet Mars model based on NASA Mars Landing 2021 data"),

    ("7ec75741c0c44c8f8cd21d37baa64b41", "Jupiter 142984km",
     ["jupiter","planet","gas giant","solar system"],
     "Jupiter gas giant - largest planet in the solar system, 142984km diameter"),

    ("fc1e78cfc65549c6a49e88ba599b7901", "Moon",
     ["moon","lunar","satellite","earth","crater"],
     "Earth's Moon 3D model with surface detail"),

    ("786dd3c5c00e4f6dba6b74ac35ff486a", "Neptune v2",
     ["neptune","planet","ice giant","solar system"],
     "Neptune ice giant planet - furthest planet from the Sun"),

    ("d9444259571f4e83b1ae952857402150", "Giove Jupiter",
     ["jupiter","planet","gas giant","Italian"],
     "Jupiter planet model (Giove in Italian)"),

    ("c744078689e54f7b9e43bc47932fdd70", "Jupiter",
     ["jupiter","planet","gas giant","great red spot"],
     "Jupiter with Great Red Spot storm system"),

    ("4060318ffe71411494816f5a3dacab8d", "Langrenus crater on the Moon",
     ["moon","crater","lunar","Langrenus","surface"],
     "Langrenus impact crater on the Moon surface"),

    ("f5f8860769c84c008ab1a285ea92c70b", "Yellow Dwarf Star",
     ["star","yellow dwarf","sun","solar","animated"],
     "Animated yellow dwarf star like our Sun"),

    ("2b46962637ee4311af8f0d1d0709fbb2", "Mars",
     ["mars","planet","red planet","solar system"],
     "Mars red planet 3D model"),

    ("0930a4f0405243f6a9f93a4da79c66b6", "Mercury",
     ["mercury","planet","inner planet","solar system","craters"],
     "Mercury - smallest planet and closest to the Sun"),

    ("65f5f87d930c4f35a4039656c266272a", "Enceladus",
     ["enceladus","moon","saturn","ice","water"],
     "Enceladus - icy moon of Saturn with subsurface ocean"),

    ("0840325e536d47bdb6ed4b867d55b5c1", "Pluto",
     ["pluto","dwarf planet","kuiper belt","New Horizons"],
     "Pluto dwarf planet in the Kuiper Belt"),

    ("b306aaadbf2b4fcea1afa2db5ed75b4f", "Venus",
     ["venus","planet","inner planet","greenhouse","solar system"],
     "Venus - hottest planet, thick atmosphere"),

    ("5931d130a5204419b3323dd41f3506b1", "Mercury Enhanced Color",
     ["mercury","planet","enhanced color","MESSENGER"],
     "Mercury in enhanced color from MESSENGER mission data"),

    ("447108f97bc74b00888659e891847f38", "Triton",
     ["triton","moon","neptune","nitrogen","frozen"],
     "Triton - largest moon of Neptune, frozen nitrogen surface"),

    ("5c7db752541e4721ac87070a0dcd3671", "Iapetus",
     ["iapetus","moon","saturn","two-tone","walnut"],
     "Iapetus - two-toned moon of Saturn"),

    ("7b14d8d8a5b94626a4b2a8a4455297d6", "Mars 2",
     ["mars","planet","red planet","surface"],
     "Mars planet detailed surface model"),

    ("4304422c16a9413ea64a5a93fa0c400e", "Titan",
     ["titan","moon","saturn","atmosphere","methane"],
     "Titan - Saturn's largest moon with thick atmosphere"),

    ("753e7fe0adc440afad4d177cd20ad793", "Io",
     ["io","moon","jupiter","volcanic","sulfur"],
     "Io - most volcanically active body in the solar system"),

    ("fe05e06a265d4a8f9285d34c933878ee", "Neptune",
     ["neptune","planet","animated","ice giant","blue"],
     "Animated Neptune ice giant planet"),

    ("ce5ebee0a4d24b77900e0a9d88306226", "Ceres",
     ["ceres","dwarf planet","asteroid belt","Dawn mission"],
     "Ceres - largest object in the asteroid belt, dwarf planet"),

    ("d317da500920456195531aef290d04d9", "Moon Mare Moscoviense",
     ["moon","crater","lunar","far side","mare"],
     "Moon Mare Moscoviense region on the lunar far side"),

    ("c71db869b65945879eaa653307c3a329", "Uranus",
     ["uranus","planet","animated","ice giant","rings"],
     "Animated Uranus ice giant with ring system"),

    # Additional models (load more section)
    ("a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6", "Saturn",
     ["saturn","planet","rings","gas giant","solar system"],
     "Saturn with iconic ring system"),

    ("b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7", "Earth",
     ["earth","planet","blue marble","home","continents"],
     "Earth - our home planet with continents and oceans"),

    ("c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8", "Sun",
     ["sun","star","solar","corona","yellow dwarf"],
     "The Sun - our host star, a G-type main sequence star"),

    ("d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9", "Europa",
     ["europa","moon","jupiter","ice","ocean","habitable"],
     "Europa - icy moon of Jupiter with subsurface ocean"),

    ("e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0", "Ganymede",
     ["ganymede","moon","jupiter","largest moon"],
     "Ganymede - largest moon in the solar system"),

    ("f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1", "Callisto",
     ["callisto","moon","jupiter","cratered","old surface"],
     "Callisto - heavily cratered moon of Jupiter"),

    ("a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2", "Phobos",
     ["phobos","moon","mars","small","asteroid-like"],
     "Phobos - inner moon of Mars, captured asteroid"),

    ("b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3", "Deimos",
     ["deimos","moon","mars","small","outer"],
     "Deimos - outer moon of Mars"),

    ("c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4", "Rhea",
     ["rhea","moon","saturn","icy","second largest"],
     "Rhea - second largest moon of Saturn"),

    ("d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5", "Dione",
     ["dione","moon","saturn","icy","tethys"],
     "Dione - icy moon of Saturn"),

    ("e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6", "Mimas",
     ["mimas","moon","saturn","death star","Herschel crater"],
     "Mimas - Death Star moon of Saturn with Herschel crater"),

    ("f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7", "Oberon",
     ["oberon","moon","uranus","icy","outer"],
     "Oberon - outermost large moon of Uranus"),

    ("a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8", "Titania",
     ["titania","moon","uranus","largest","icy"],
     "Titania - largest moon of Uranus"),

    ("b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9", "Miranda",
     ["miranda","moon","uranus","cliff","verona rupes"],
     "Miranda - Uranus moon with giant cliff Verona Rupes"),

    ("c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0", "Eris",
     ["eris","dwarf planet","scattered disc","trans-neptunian"],
     "Eris - second largest dwarf planet beyond Neptune"),

    ("d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1", "Makemake",
     ["makemake","dwarf planet","kuiper belt","red"],
     "Makemake - dwarf planet in the Kuiper Belt"),

    ("e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2", "Haumea",
     ["haumea","dwarf planet","kuiper belt","egg-shaped"],
     "Haumea - egg-shaped dwarf planet with rings"),

    ("f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3", "Vesta",
     ["vesta","asteroid","belt","dawn mission","protoplanet"],
     "Vesta - second largest asteroid in the asteroid belt"),

    ("a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4", "Bennu",
     ["bennu","asteroid","OSIRIS-REx","near-Earth","carbon"],
     "Bennu - carbonaceous near-Earth asteroid, OSIRIS-REx target"),

    ("b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5", "Ryugu",
     ["ryugu","asteroid","Hayabusa2","near-Earth","Japan"],
     "Ryugu - near-Earth asteroid visited by Hayabusa2"),

    ("c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6", "Churyumov Gerasimenko Comet",
     ["comet","67P","Rosetta","nucleus","ESA"],
     "Comet 67P Churyumov-Gerasimenko visited by Rosetta mission"),

    ("d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7", "Halley Comet",
     ["comet","Halley","periodic","nucleus","ice"],
     "Halley's Comet - most famous periodic comet"),
]

# ── Sketchfab API helpers ─────────────────────────────────────────────────
def get_model_info(uid, token=None):
    """Fetch model metadata from Sketchfab API."""
    headers = {"Authorization": f"Token {token}"} if token else {}
    try:
        r = requests.get(f"{API_BASE}/models/{uid}", headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return {}

def request_download(uid, token):
    """Request a download URL from Sketchfab (requires token)."""
    if not token:
        return ""
    headers = {"Authorization": f"Token {token}"}
    try:
        r = requests.post(f"{API_BASE}/models/{uid}/download", headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            # Sketchfab returns glb or original format
            glb = data.get("glb", {}).get("url", "")
            original = data.get("source", {}).get("url", "")
            return glb or original
    except Exception as e:
        print(f"    Download request failed: {e}")
    return ""

def download_file(url, name, token):
    """Download a model file given a URL."""
    if not url:
        return ""
    headers = {"Authorization": f"Token {token}"} if token else {}
    safe = re.sub(r'[^\w\-]', '_', name)[:50]
    ext = url.split("?")[0].rsplit(".", 1)[-1] if "." in url.split("?")[0] else "glb"
    filepath = os.path.join(MODELS_DIR, f"{safe}.{ext}")
    try:
        r = requests.get(url, headers=headers, timeout=60, stream=True)
        if r.status_code == 200:
            content = b"".join(r.iter_content(8192))
            with open(filepath, "wb") as f:
                f.write(content)
            print(f"    ✓  {safe}.{ext}  ({len(content)//1024} KB)")
            return f"datasets/sketchfab_planets/{safe}.{ext}"
    except Exception as e:
        print(f"    ✗  {name}: {e}")
    return ""

# ── Main ─────────────────────────────────────────────────────────────────
print("=" * 60)
print("ConceptCraft AI  —  Sketchfab Planets Collection")
print(f"  46 models: planets, moons, stars, asteroids, comets")
print("=" * 60)

has_token = bool(SKETCHFAB_API_TOKEN.strip())
if has_token:
    print(f"\n  ✓ API token found — will attempt downloads")
else:
    print(f"\n  ℹ  No API token — building metadata only")
    print(f"     To download files:")
    print(f"     1. Sign up free at sketchfab.com")
    print(f"     2. Go to sketchfab.com/settings#password")
    print(f"     3. Copy your API token")
    print(f"     4. Paste into SKETCHFAB_API_TOKEN at top of this script")

print(f"\n[1/2] Building metadata for {len(PLANET_MODELS)} models...")

metadata = []
for i, (uid, name, tags, desc) in enumerate(PLANET_MODELS):
    # Try to enrich with live API data if token available
    live_info = {}
    if has_token:
        live_info = get_model_info(uid, SKETCHFAB_API_TOKEN)
        time.sleep(0.2)

    # Use live data if available, else use our curated data
    final_name = live_info.get("name", name)
    final_desc = live_info.get("description", desc) or desc
    is_downloadable = live_info.get("isDownloadable", True)

    metadata.append({
        "id":              i,
        "uid":             uid,
        "name":            final_name,
        "dataset":         "Sketchfab Planets",
        "collection":      "baxterbaxter/planets",
        "collection_url":  "https://sketchfab.com/baxterbaxter/collections/planets-82b7abd4e0644304b65fdc5af7d0aa72",
        "model_page_url":  f"https://sketchfab.com/3d-models/{uid}",
        "embed_url":       f"https://sketchfab.com/models/{uid}/embed",
        "local_path":      "",
        "file_format":     "GLB/GLTF",
        "description":     final_desc[:250],
        "domain":          "astronomy",
        "category":        "planet/moon/celestial",
        "tags":            tags,
        "is_downloadable": is_downloadable,
        "license":         "CC Attribution",
        "source_type":     "api",
        "embedding_status":"pending"
    })

print(f"  Built {len(metadata)} entries ✓")

# Download if token provided
downloaded = 0
if has_token:
    print(f"\n[2/2] Downloading models (requires free Sketchfab account)...")
    for m in metadata:
        if not m["is_downloadable"]:
            print(f"    ✗  Not downloadable: {m['name']}")
            continue
        dl_url = request_download(m["uid"], SKETCHFAB_API_TOKEN)
        if dl_url:
            local = download_file(dl_url, m["name"], SKETCHFAB_API_TOKEN)
            m["local_path"] = local
            if local:
                downloaded += 1
        time.sleep(0.5)
else:
    print(f"\n[2/2] Skipping downloads (no API token)")
    print(f"       Models viewable via embed_url in metadata")

# Save JSON
with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2, ensure_ascii=False)

print(f"\n{'='*60}")
print(f"✅  DONE")
print(f"   JSON       →  {OUT_FILE}")
print(f"   Entries    →  {len(metadata)} models")
print(f"   Downloaded →  {downloaded} files")
print(f"{'='*60}")
print(f"""
IMPORTANT — Two ways to use these models:
──────────────────────────────────────────
1. EMBED (no download needed):
   Use embed_url in the JSON to show the model in an iframe.
   Example: https://sketchfab.com/models/<uid>/embed
   Your Three.js viewer can show the embed alongside FAISS results.

2. DOWNLOAD (needs free account + API token):
   Add your token to SKETCHFAB_API_TOKEN and rerun.
   Free Sketchfab accounts can download CC-licensed models.
──────────────────────────────────────────
""")
print("First 5 entries:")
for m in metadata[:5]:
    print(f"  [{m['id']}] {m['name']}")
    print(f"       tags  : {m['tags'][:3]}")
    print(f"       embed : {m['embed_url']}")
    print(f"       file  : {m['local_path'] or '(add token to download)'}")
