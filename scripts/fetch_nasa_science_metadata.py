"""
ConceptCraft AI - NASA Science 3D Resources Fetcher (FIXED)
============================================================
Uses GitHub API to get ALL model slugs (no pagination issues),
then downloads .glb files directly from assets.science.nasa.gov

Run from ConceptCraftAI/scripts/:
    pip install requests
    python fetch_nasa_science_metadata.py
"""

import requests, json, os, re, time

MODELS_DIR   = "../datasets/nasa_science"
METADATA_DIR = "../metadata"
OUT_FILE     = os.path.join(METADATA_DIR, "nasa_science_metadata.json")
os.makedirs(MODELS_DIR,   exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

HEADERS     = {"User-Agent": "Mozilla/5.0 (ConceptCraftAI research)"}
GH_API      = "https://api.github.com/repos/nasa/NASA-3D-Resources/contents/3D%20Models"
ASSET_BASE  = "https://assets.science.nasa.gov/content/dam/science/cds/3d/resources/model"
SITE_BASE   = "https://science.nasa.gov/3d-resources"

# ── Category guesser ──────────────────────────────────────────────────────
def guess_category(name):
    t = name.lower()
    if any(k in t for k in ["asteroid","bennu","rq36","eros","vesta","ceres","comet","67p"]): return "asteroid"
    if any(k in t for k in ["mars","curiosity","perseverance","opportunity","spirit","insight"]): return "mars"
    if any(k in t for k in ["moon","lunar","apollo","artemis","gateway","lro"]): return "lunar"
    if any(k in t for k in ["hubble","webb","chandra","spitzer","kepler","tess","nustar","fermi","sofia","wise","telescope"]): return "telescope"
    if any(k in t for k in ["saturn v","sls","atlas","delta","rocket","falcon","ares","vulcan"]): return "rocket"
    if any(k in t for k in ["shuttle","columbia","challenger","discovery","endeavour","atlantis"]): return "shuttle"
    if any(k in t for k in ["iss","space station","gateway","mir"]): return "space_station"
    if any(k in t for k in ["jupiter","saturn","venus","neptune","uranus","mercury","pluto","planet"]): return "planet"
    if any(k in t for k in ["suit","spacesuit","eva","orion","helmet"]): return "equipment"
    if any(k in t for k in ["nebula","galaxy","pillars","crab","cassiopeia","supernova","pulsar","quasar"]): return "deep_space"
    if any(k in t for k in ["aircraft","x-plane","supersonic","drone","helicopter"]): return "aircraft"
    if any(k in t for k in ["satellite","acrimsat","goes","landsat","grace","ice","oco","acrimsat"]): return "satellite"
    if any(k in t for k in ["voyager","cassini","juno","new horizons","dawn","osiris","parker","pioneer"]): return "deep_space_probe"
    return "spacecraft"

def guess_tags(name):
    t = name.lower()
    tags = ["NASA", "astronomy", "space"]
    for k in ["mars","moon","asteroid","hubble","webb","kepler","cassini","voyager",
              "curiosity","perseverance","ISS","rocket","saturn","jupiter","venus",
              "telescope","shuttle","spacecraft","lunar","solar","orbit","planet",
              "nebula","galaxy","comet","satellite","rover","probe","apollo","artemis"]:
        if k.lower() in t:
            tags.append(k)
    return list(dict.fromkeys(tags))[:7]

# ── Step 1: Get all model folders from GitHub API ─────────────────────────
print("=" * 60)
print("ConceptCraft AI  —  NASA Science 3D Resources (Fixed)")
print("=" * 60)

print("\n[1/3] Fetching model list from NASA GitHub repo...")
try:
    r = requests.get(GH_API, headers={**HEADERS, "Accept": "application/vnd.github.v3+json"}, timeout=15)
    folders = r.json()
    model_names = [f["name"] for f in folders if f["type"] == "dir"]
    print(f"  Found {len(model_names)} models in GitHub repo")
except Exception as e:
    print(f"  GitHub API failed: {e}")
    print("  Using known model list as fallback...")
    # Fallback: known model names from the website's first page + common ones
    model_names = [
        "1999 RQ36 asteroid", "70 meter dish", "Active Cavity Irradiance Monitor Satellite (AcrimSAT) (A)",
        "Active Cavity Irradiance Monitor Satellite (AcrimSAT) (B)", "Advanced Composition Explorer",
        "Advanced Crew Escape Suit", "Aeronomy of Ice in the Mesosphere", "Agena Target Vehicle",
        "Apollo 11 - Landing Site", "Apollo 12 - Landing Site", "Apollo 14 - Landing Site",
        "Apollo 15 - Landing Site", "Apollo 16 - Landing Site", "Aqua", "Aquarius",
        "ARTEMIS", "Asteroid Redirect Mission", "ATS-6", "Aura",
        "Big Bang Observatory", "Binary Asteroid In-Space Tugboat", "Calipso",
        "Cassini", "Chandra", "Chandra X-ray Observatory",
        "Cluster II", "COBE", "Compton Gamma Ray Observatory",
        "Curiosity Rover", "Dawn", "Deep Impact",
        "Deep Space 1", "Deep Space Climate Observatory", "DSCOVR",
        "Earth", "EPOXI", "Europa",
        "Fermi Gamma-ray Space Telescope", "Galaxy Evolution Explorer",
        "Genesis", "GLAST", "GOES",
        "Gravity Probe B", "Hubble Space Telescope", "ICESat",
        "IMAGE", "International Space Station", "IRIS",
        "James Webb Space Telescope", "Juno", "Kepler",
        "Landsat 8", "LRO", "Magellan",
        "Mars 2020 Perseverance Rover", "Mars Global Surveyor", "Mars Odyssey",
        "Mars Pathfinder", "Mars Reconnaisance Orbiter", "Mars Science Laboratory",
        "MAVEN", "Mercury", "Mercury MESSENGER",
        "Moon", "MRO", "New Horizons",
        "NICER", "NuSTAR", "OCO-2",
        "Opportunity Rover", "OSIRIS-REx", "Parker Solar Probe",
        "Phoenix", "Pioneer 10", "Pioneer 11",
        "Pluto", "Polar", "Rosetta",
        "Saturn", "SOFIA", "Solar Dynamics Observatory",
        "Solar Maximum Mission", "SOHO", "Spirit Rover",
        "Spitzer", "Stardust", "STEREO",
        "SWIFT", "TESS", "THEMIS",
        "TOPEX Poseidon", "TRACE", "Ulysses",
        "Van Allen Probes", "Venus", "Viking",
        "Voyager", "WMAP", "XMM Newton",
    ]

# ── Step 2: Build download URLs and metadata ──────────────────────────────
print(f"\n[2/3] Building metadata + download URLs for {len(model_names)} models...")

def name_to_slug(name):
    """Convert model name to science.nasa.gov URL slug."""
    slug = name.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)   # remove special chars
    slug = re.sub(r'\s+', '-', slug.strip()) # spaces to hyphens
    slug = re.sub(r'-+', '-', slug)          # collapse multiple hyphens
    return slug

def build_glb_url(name, slug):
    """Build the direct GLB download URL."""
    # Pattern confirmed: assets.science.nasa.gov/content/dam/science/cds/3d/resources/model/<slug>/<Name>.glb
    encoded_name = name.replace(" ", "%20")
    return f"{ASSET_BASE}/{slug}/{encoded_name}.glb"

metadata = []
for i, name in enumerate(model_names):
    slug     = name_to_slug(name)
    dl_url   = build_glb_url(name, slug)
    category = guess_category(name)
    tags     = guess_tags(name)

    metadata.append({
        "id":             i,
        "slug":           slug,
        "name":           name,
        "dataset":        "NASA Science 3D",
        "model_page_url": f"{SITE_BASE}/{slug}/",
        "download_url":   dl_url,
        "local_path":     "",
        "file_format":    "GLB",
        "description":    f"{name} - NASA 3D model, public domain. Category: {category}",
        "domain":         "astronomy",
        "category":       category,
        "tags":           tags,
        "license":        "US Government Public Domain",
        "source_type":    "download",
        "embedding_status": "pending"
    })

# Save metadata immediately
with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2, ensure_ascii=False)
print(f"  Metadata saved → {OUT_FILE}  ({len(metadata)} entries)")

# ── Step 3: Download GLB files ────────────────────────────────────────────
print(f"\n[3/3] Downloading GLB files...")
print(f"  Trying both .glb and .stl for each model\n")

MAX_DOWNLOADS = 80   # ← increase to download more

def try_download(slug, name):
    """Try GLB first, then STL, then alternate URL formats."""
    attempts = [
        f"{ASSET_BASE}/{slug}/{name}.glb",
        f"{ASSET_BASE}/{slug}/{name}.stl",
        # Some models use title case
        f"{ASSET_BASE}/{slug}/{name.title()}.glb",
        # Some use the raw GitHub file
        f"https://raw.githubusercontent.com/nasa/NASA-3D-Resources/master/3D%20Models/{name.replace(' ','%20')}/{name.replace(' ','%20')}.glb",
    ]
    for url in attempts:
        try:
            r = requests.get(url, headers={**HEADERS,"Accept":"*/*"}, timeout=25, stream=True)
            if r.status_code == 200:
                content = b"".join(r.iter_content(8192))
                if len(content) > 500:
                    ext  = url.rsplit(".", 1)[-1].split("?")[0].lower()
                    safe = re.sub(r'[^\w\-]', '_', slug)[:60]
                    path = os.path.join(MODELS_DIR, f"{safe}.{ext}")
                    with open(path, "wb") as f:
                        f.write(content)
                    print(f"  ✓  {safe}.{ext}  ({len(content)//1024} KB)")
                    return f"datasets/nasa_science/{safe}.{ext}"
        except:
            pass
    print(f"  ✗  {name}")
    return ""

downloaded = 0
for m in metadata[:MAX_DOWNLOADS]:
    local = try_download(m["slug"], m["name"])
    m["local_path"] = local
    if local:
        downloaded += 1
    time.sleep(0.3)

# Save final with local paths
with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2, ensure_ascii=False)

print(f"\n{'='*60}")
print(f"✅  DONE")
print(f"   JSON     →  {OUT_FILE}")
print(f"   Indexed  →  {len(metadata)} models")
print(f"   Files    →  {downloaded} downloaded")
print(f"{'='*60}")
print("\nFirst 5 entries:")
for m in metadata[:5]:
    print(f"  [{m['id']}] {m['name']}")
    print(f"       category : {m['category']} | tags: {m['tags'][:3]}")
    print(f"       file     : {m['local_path'] or '(not downloaded)'}")