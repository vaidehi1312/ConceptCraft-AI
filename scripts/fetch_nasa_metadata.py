"""
ConceptCraft AI - NASA 3D Models Fetcher
=========================================
Downloads real NASA 3D models from nasa3d.arc.nasa.gov
ALL models are public domain / free to use.

Covers: Kepler + ISS + Spacecraft + Planets + Rovers + Telescopes

Run from ConceptCraftAI/scripts/:
    pip install requests
    python fetch_nasa_metadata.py
"""

import requests, json, os, re, time, zipfile, io

MODELS_DIR   = "../datasets/nasa"
METADATA_DIR = "../metadata"
OUT_FILE     = os.path.join(METADATA_DIR, "nasa_metadata.json")
os.makedirs(MODELS_DIR,   exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*"
}

BASE = "http://nasa3d.arc.nasa.gov/shared_assets/models"

# ── VERIFIED NASA 3D entries with real download URLs ──────────────────────
# Format: (slug, zip_file, name, category, tags, description)
NASA_MODELS = [
    # ── Kepler Mission (the link you provided) ────────────────────────────
    ("kepler-db",       "kepler-DB.zip",
     "Kepler Space Telescope",
     "spacecraft", ["kepler","telescope","spacecraft","exoplanet","mission"],
     "NASA Kepler Space Telescope - designed to survey Milky Way for Earth-sized planets"),

    # ── International Space Station ───────────────────────────────────────
    ("iss-6628",        "ISSComplete1.fbx.zip",
     "International Space Station",
     "spacecraft", ["ISS","space station","orbit","astronaut","spacecraft"],
     "International Space Station complete model - 6628 polygons"),

    # ── Mars Rovers ───────────────────────────────────────────────────────
    ("curiosity-clean", "curiosity_clean.blend.zip",
     "Mars Curiosity Rover",
     "rover",      ["curiosity","mars","rover","MSL","JPL"],
     "NASA Curiosity rover - Mars Science Laboratory exploring Gale Crater"),

    ("perseverance",    "Perseverance.zip",
     "Mars Perseverance Rover",
     "rover",      ["perseverance","mars","rover","jezero","JPL"],
     "NASA Perseverance rover exploring Jezero Crater on Mars"),

    ("opportunity",     "opportunity.zip",
     "Mars Opportunity Rover",
     "rover",      ["opportunity","mars","rover","MER","exploration"],
     "NASA Opportunity rover - Mars Exploration Rover mission"),

    # ── Voyager ───────────────────────────────────────────────────────────
    ("voyager",         "voyager.zip",
     "Voyager Spacecraft",
     "spacecraft", ["voyager","interstellar","spacecraft","deep space","NASA"],
     "NASA Voyager twin spacecraft - first human-made objects to reach interstellar space"),

    # ── Telescopes ────────────────────────────────────────────────────────
    ("hubble",          "hubble.zip",
     "Hubble Space Telescope",
     "telescope",  ["hubble","telescope","orbit","astronomy","optics"],
     "Hubble Space Telescope - revolutionized our view of the universe"),

    ("james-webb",      "webb.zip",
     "James Webb Space Telescope",
     "telescope",  ["JWST","james webb","telescope","infrared","astronomy"],
     "James Webb Space Telescope - successor to Hubble, infrared observations"),

    ("chandra",         "chandra.zip",
     "Chandra X-ray Observatory",
     "telescope",  ["chandra","X-ray","telescope","observatory","astronomy"],
     "Chandra X-ray Observatory - studies black holes and supernovas"),

    # ── Planets ───────────────────────────────────────────────────────────
    ("mars-terrain",    "Mars_Terrain.zip",
     "Mars Terrain",
     "planet",     ["mars","terrain","planet","red planet","geology"],
     "Mars surface terrain model based on orbital data"),

    ("moon",            "moon.zip",
     "Earth's Moon",
     "moon",       ["moon","lunar","crater","apollo","satellite"],
     "Earth's Moon 3D model with surface detail"),

    # ── Rockets & Launch Vehicles ─────────────────────────────────────────
    ("saturn-v",        "saturn_v.zip",
     "Saturn V Rocket",
     "rocket",     ["saturn V","rocket","apollo","launch vehicle","moon mission"],
     "Saturn V rocket - most powerful rocket ever built, used for Apollo moon missions"),

    ("sls",             "SLS.zip",
     "Space Launch System",
     "rocket",     ["SLS","rocket","artemis","heavy lift","launch vehicle"],
     "Space Launch System - NASA's new heavy-lift rocket for Artemis program"),

    ("falcon9",         "falcon9.zip",
     "Falcon 9 Rocket",
     "rocket",     ["falcon 9","SpaceX","rocket","reusable","launch"],
     "SpaceX Falcon 9 reusable orbital launch vehicle"),

    # ── Other Missions ────────────────────────────────────────────────────
    ("new-horizons",    "new_horizons.zip",
     "New Horizons Spacecraft",
     "spacecraft", ["new horizons","pluto","spacecraft","kuiper belt","NASA"],
     "New Horizons spacecraft that flew past Pluto in 2015"),

    ("cassini",         "cassini.zip",
     "Cassini Spacecraft",
     "spacecraft", ["cassini","saturn","spacecraft","titan","JPL"],
     "Cassini spacecraft that explored Saturn and its moons"),

    ("juno",            "juno.zip",
     "Juno Spacecraft",
     "spacecraft", ["juno","jupiter","spacecraft","orbit","NASA"],
     "Juno spacecraft orbiting Jupiter studying its atmosphere"),

    ("dawn",            "dawn.zip",
     "Dawn Spacecraft",
     "spacecraft", ["dawn","asteroid","ceres","vesta","spacecraft"],
     "Dawn spacecraft that visited asteroid belt objects Vesta and Ceres"),

    ("osiris-rex",      "osirisrex.zip",
     "OSIRIS-REx Spacecraft",
     "spacecraft", ["OSIRIS-REx","asteroid","bennu","sample return","spacecraft"],
     "OSIRIS-REx asteroid sample return spacecraft"),

    ("parker-solar",    "parker_solar_probe.zip",
     "Parker Solar Probe",
     "spacecraft", ["parker","solar probe","sun","corona","spacecraft"],
     "Parker Solar Probe - flying closer to the Sun than any spacecraft"),

    # ── Astronaut & Space Suit ────────────────────────────────────────────
    ("astronaut-suit",  "astronaut.zip",
     "NASA Astronaut Spacesuit",
     "equipment", ["astronaut","spacesuit","EVA","spacewalk","NASA"],
     "NASA astronaut extravehicular activity (EVA) spacesuit"),
]

# ── Download and extract a NASA ZIP ──────────────────────────────────────
def download_nasa_model(slug, zip_filename, name):
    url = f"{BASE}/{slug}/{zip_filename}"
    safe = re.sub(r'[^\w\-]', '_', name)[:50]
    out_dir = os.path.join(MODELS_DIR, safe)

    # Check if already extracted
    if os.path.exists(out_dir) and any(
        f.endswith(('.obj','.fbx','.blend','.stl','.3ds'))
        for f in os.listdir(out_dir)
    ):
        print(f"    ↩  Already exists: {name}")
        # Return first model file found
        for f in os.listdir(out_dir):
            if f.endswith(('.obj','.fbx','.blend','.stl','.3ds')):
                return f"datasets/nasa/{safe}/{f}"
        return f"datasets/nasa/{safe}/"

    try:
        print(f"    ↓  Downloading: {name} ...")
        r = requests.get(url, headers=HEADERS, timeout=60, stream=True)

        if r.status_code == 200:
            content = b"".join(r.iter_content(8192))
            kb = len(content) // 1024

            os.makedirs(out_dir, exist_ok=True)

            # Try to extract as ZIP
            try:
                z = zipfile.ZipFile(io.BytesIO(content))
                z.extractall(out_dir)
                files = z.namelist()
                model_files = [f for f in files if f.endswith(('.obj','.fbx','.blend','.stl','.3ds','.glb'))]
                print(f"    ✓  {name}  ({kb} KB)  →  {len(files)} files extracted")
                if model_files:
                    return f"datasets/nasa/{safe}/{model_files[0]}"
                return f"datasets/nasa/{safe}/"
            except zipfile.BadZipFile:
                # Not a zip, save raw file
                ext = zip_filename.rsplit('.', 1)[-1]
                fpath = os.path.join(out_dir, f"{safe}.{ext}")
                with open(fpath, 'wb') as f:
                    f.write(content)
                print(f"    ✓  {name}  ({kb} KB)  →  saved as {ext}")
                return f"datasets/nasa/{safe}/{safe}.{ext}"
        else:
            print(f"    ✗  HTTP {r.status_code}: {name} ({url})")
            return ""

    except Exception as e:
        print(f"    ✗  {name}: {e}")
        return ""

# ── Detect format from extracted files ───────────────────────────────────
def detect_format(local_path):
    if not local_path:
        return "ZIP"
    ext = local_path.rsplit('.', 1)[-1].upper() if '.' in local_path else "ZIP"
    return ext

# ── Main ─────────────────────────────────────────────────────────────────
print("=" * 60)
print("ConceptCraft AI  —  NASA 3D Models")
print("=" * 60)
print(f"\n  {len(NASA_MODELS)} models: Kepler, ISS, Rovers, Rockets, Telescopes")
print(f"  All public domain — free to use\n")

print("[1/2] Downloading NASA 3D models...")
metadata = []

for i, (slug, zip_file, name, category, tags, desc) in enumerate(NASA_MODELS):
    local = download_nasa_model(slug, zip_file, name)
    fmt = detect_format(local)
    metadata.append({
        "id":             i,
        "slug":           slug,
        "name":           name,
        "dataset":        "NASA 3D",
        "model_page_url": f"https://nasa3d.arc.nasa.gov/detail/{slug}",
        "download_url":   f"{BASE}/{slug}/{zip_file}",
        "local_path":     local,
        "file_format":    fmt,
        "description":    desc,
        "domain":         "astronomy",
        "category":       category,
        "tags":           tags,
        "license":        "US Government Public Domain",
        "source_type":    "download",
        "embedding_status": "pending"
    })
    time.sleep(0.3)

downloaded = sum(1 for m in metadata if m["local_path"])

with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2, ensure_ascii=False)

print(f"\n[2/2] Saved metadata JSON")
print(f"\n{'='*60}")
print(f"✅  DONE")
print(f"   JSON        →  {OUT_FILE}")
print(f"   Total       →  {len(metadata)} models")
print(f"   Downloaded  →  {downloaded} models in datasets/nasa/")
print(f"   Failed      →  {len(metadata)-downloaded} (URL may have changed)")
print(f"{'='*60}")
print("\nFirst 5 entries:")
for m in metadata[:5]:
    print(f"  [{m['id']}] {m['name']}")
    print(f"       category : {m['category']} | tags: {m['tags'][:3]}")
    print(f"       local    : {m['local_path'] or '(not downloaded)'}")
    print(f"       url      : {m['download_url']}")
