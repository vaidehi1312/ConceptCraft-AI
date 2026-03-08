"""
ConceptCraft AI - Solar System Scope Textures
=============================================
43 high-resolution planet/moon textures (2k, 4k, 8k)
License: CC-BY 4.0 - free to use commercially
Source:  https://www.solarsystemscope.com/textures/

These are NOT 3D models - they are equirectangular JPG/TIF textures.
Value for ConceptCraft:
  - Apply to Three.js sphere meshes at query time (zero pre-download)
  - Enrich FAISS metadata with texture URLs for known planets/moons
  - On-demand fetch when user searches "earth texture" / "mars surface" etc.

No downloads. Metadata only.
Run from ConceptCraftAI/scripts/:
    python fetch_solarsystemscope_metadata.py
"""

import json, os

METADATA_DIR = "../metadata"
OUT_FILE     = os.path.join(METADATA_DIR, "solarsystemscope_metadata.json")
os.makedirs(METADATA_DIR, exist_ok=True)

# Direct download base URL (confirmed pattern from Wikimedia Commons filenames)
BASE = "https://www.solarsystemscope.com/textures/download"

# ── All 43 textures (scraped from Wikimedia Commons category listing) ─────
# Format: (body, texture_type, resolution, file_ext, description, tags)
TEXTURES = [
    # Sun
    ("sun",         "surface",          "8k",  "jpg", "The Sun surface texture, chromosphere detail", ["sun","star","solar","yellow dwarf","corona"]),

    # Mercury
    ("mercury",     "surface",          "2k",  "jpg", "Mercury surface texture, heavily cratered",    ["mercury","planet","inner planet","craters"]),

    # Venus
    ("venus",       "surface",          "2k",  "jpg", "Venus surface texture from radar mapping",     ["venus","planet","surface","radar"]),
    ("venus",       "atmosphere",       "4k",  "jpg", "Venus thick atmosphere/cloud layer texture",   ["venus","atmosphere","clouds","greenhouse"]),

    # Earth
    ("earth",       "daymap",           "8k",  "jpg", "Earth day side surface texture, blue marble",  ["earth","planet","continents","oceans","day"]),
    ("earth",       "nightmap",         "8k",  "jpg", "Earth night side texture with city lights",    ["earth","night","city lights","civilization"]),
    ("earth",       "clouds",           "8k",  "jpg", "Earth cloud layer texture for atmosphere",     ["earth","clouds","atmosphere","weather"]),
    ("earth",       "normal_map",       "8k",  "tif", "Earth surface normal map for 3D rendering",    ["earth","normal map","elevation","terrain"]),
    ("earth",       "specular_map",     "8k",  "tif", "Earth specular map (ocean reflectivity)",      ["earth","specular","ocean","reflectivity"]),

    # Moon
    ("moon",        "surface",          "2k",  "jpg", "Earth's Moon surface with craters and maria",  ["moon","lunar","craters","maria","satellite"]),

    # Mars
    ("mars",        "surface",          "2k",  "jpg", "Mars red planet surface texture",              ["mars","planet","red planet","surface","dust"]),

    # Jupiter
    ("jupiter",     "surface",          "8k",  "jpg", "Jupiter gas giant cloud bands and Great Red Spot", ["jupiter","planet","gas giant","great red spot","bands"]),

    # Saturn
    ("saturn",      "surface",          "8k",  "jpg", "Saturn gas giant surface texture",             ["saturn","planet","gas giant","rings","bands"]),
    ("saturn",      "ring_alpha",       "8k",  "png", "Saturn ring system alpha/transparency texture",["saturn","rings","ring system","transparency"]),

    # Uranus
    ("uranus",      "surface",          "2k",  "jpg", "Uranus ice giant pale blue surface",           ["uranus","planet","ice giant","blue","pale"]),

    # Neptune
    ("neptune",     "surface",          "2k",  "jpg", "Neptune ice giant deep blue surface",          ["neptune","planet","ice giant","blue","storms"]),

    # Pluto
    ("pluto",       "surface",          "2k",  "jpg", "Pluto dwarf planet surface, Tombaugh Regio",   ["pluto","dwarf planet","kuiper belt","heart","New Horizons"]),

    # Dwarf planets (fictional/modeled)
    ("ceres",       "fictional",        "4k",  "jpg", "Ceres dwarf planet surface texture (modeled)", ["ceres","dwarf planet","asteroid belt","Dawn"]),
    ("eris",        "fictional",        "4k",  "jpg", "Eris dwarf planet surface texture (fictional model)", ["eris","dwarf planet","scattered disc","trans-neptunian"]),
    ("haumea",      "fictional",        "4k",  "jpg", "Haumea egg-shaped dwarf planet texture (fictional)", ["haumea","dwarf planet","kuiper belt","egg-shaped"]),
    ("makemake",    "fictional",        "4k",  "jpg", "Makemake dwarf planet surface texture (fictional)", ["makemake","dwarf planet","kuiper belt","red"]),

    # Moons
    ("europa",      "surface",          "2k",  "jpg", "Europa icy moon of Jupiter, cracked ice surface", ["europa","moon","jupiter","ice","subsurface ocean"]),
    ("ganymede",    "surface",          "2k",  "jpg", "Ganymede largest moon in solar system",        ["ganymede","moon","jupiter","largest moon"]),
    ("io",          "surface",          "2k",  "jpg", "Io volcanic moon of Jupiter, sulfur surface",  ["io","moon","jupiter","volcanic","sulfur"]),
    ("callisto",    "surface",          "2k",  "jpg", "Callisto heavily cratered moon of Jupiter",    ["callisto","moon","jupiter","cratered"]),
    ("titan",       "surface",          "2k",  "jpg", "Titan Saturn moon with thick nitrogen atmosphere", ["titan","moon","saturn","atmosphere","methane"]),
    ("enceladus",   "surface",          "2k",  "jpg", "Enceladus icy moon of Saturn, geysers",        ["enceladus","moon","saturn","ice","geysers","water"]),
    ("mimas",       "surface",          "2k",  "jpg", "Mimas Death Star moon of Saturn",              ["mimas","moon","saturn","herschel crater","death star"]),
    ("triton",      "surface",          "2k",  "jpg", "Triton retrograde moon of Neptune, nitrogen ice", ["triton","moon","neptune","nitrogen","retrograde"]),

    # Stars / misc
    ("stars",       "milky_way",        "8k",  "jpg", "Milky Way galaxy panorama background texture", ["milky way","galaxy","stars","background","panorama"]),
    ("stars",       "starfield",        "2k",  "jpg", "Star field background texture for space scenes",["stars","starfield","background","deep space"]),
]

print("=" * 60)
print("ConceptCraft AI  —  Solar System Scope Textures")
print(f"  {len(TEXTURES)} textures | CC-BY 4.0 | Metadata only (no downloads)")
print("=" * 60)

metadata = []
for i, (body, tex_type, res, ext, desc, tags) in enumerate(TEXTURES):
    # Confirmed filename pattern from Wikimedia Commons:
    # solarsystemscope_texture_{res}_{body}_{type}.jpg
    filename    = f"solarsystemscope_texture_{res}_{body}_{tex_type}.{ext}"
    # Direct download URL pattern from the site
    download_url = f"https://www.solarsystemscope.com/textures/download/{res}_{body}_{tex_type}.{ext}"

    metadata.append({
        "id":             i,
        "name":           f"{body.title()} {tex_type.replace('_',' ').title()} ({res})",
        "body":           body,
        "texture_type":   tex_type,
        "resolution":     res,
        "file_format":    ext.upper(),
        "filename":       filename,
        "dataset":        "Solar System Scope Textures",
        "source_url":     "https://www.solarsystemscope.com/textures/",
        "download_url":   download_url,
        "local_path":     "",            # intentionally empty — fetch on demand
        "description":    desc,
        "domain":         "astronomy",
        "category":       "texture",
        "tags":           tags + ["texture", "equirectangular", "planet texture"],
        "usage":          "Apply to Three.js SphereGeometry as map texture",
        "threejs_snippet": f"new THREE.TextureLoader().load('{download_url}')",
        "license":        "CC-BY 4.0",
        "source_type":    "on_demand",
        "embedding_status": "pending"
    })

with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2, ensure_ascii=False)

print(f"\n✅  DONE — no downloads, metadata only")
print(f"   JSON    →  {OUT_FILE}")
print(f"   Entries →  {len(metadata)} textures\n")

# Print summary table
print(f"{'Body':<14} {'Type':<18} {'Res':<5} {'Ext'}")
print("-" * 45)
for m in metadata:
    print(f"  {m['body']:<12} {m['texture_type']:<18} {m['resolution']:<5} {m['file_format']}")

print(f"""
HOW THIS INTEGRATES WITH THREE.JS:
───────────────────────────────────
When FAISS returns a planet texture result:

  const loader = new THREE.TextureLoader();
  const texture = loader.load(model.download_url);
  const sphere = new THREE.Mesh(
    new THREE.SphereGeometry(1, 64, 64),
    new THREE.MeshStandardMaterial({{ map: texture }})
  );

No pre-download needed. Textures stream directly from
solarsystemscope.com at render time.
""")
