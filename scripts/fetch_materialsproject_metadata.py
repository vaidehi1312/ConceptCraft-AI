"""
fetch_materialsproject_metadata.py
------------------------------------
Scrapes Materials Project metadata → materialsproject_metadata.json
No local downloads. Metadata only.

SETUP (one time):
  1. pip install requests python-dotenv
  2. Copy .env.example to .env
  3. Paste your MP API key into .env
  4. Run: python fetch_materialsproject_metadata.py

Get a free API key at: https://next-gen.materialsproject.org/api
"""

import json, os, time, requests
from collections import Counter
from dotenv import load_dotenv

# Load .env file from project root (one level up from scripts/)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

API_KEY = os.environ.get("MP_API_KEY", "")

BASE_URL    = "https://api.materialsproject.org"
OUTPUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "metadata")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "materialsproject_metadata.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DELAY         = 0.3
PAGE_SIZE     = 1000
MAX_PER_QUERY = 2000

HEADERS = {
    "X-API-KEY": API_KEY,
    "accept":    "application/json",
}

FIELDS = ",".join([
    "material_id",
    "formula_pretty",
    "formula_anonymous",
    "chemsys",
    "elements",
    "nelements",
    "nsites",
    "volume",
    "density",
    "density_atomic",
    "symmetry",
    "crystal_system",
    "spacegroup_symbol",
    "spacegroup_number",
    "point_group",
    "is_stable",
    "is_metal",
    "is_magnetic",
    "ordering",
    "total_magnetization",
    "band_gap",
    "cbm",
    "vbm",
    "efermi",
    "energy_per_atom",
    "energy_above_hull",
    "formation_energy_per_atom",
    "decomposes_to",
    "theoretical",
    "database_IDs",
    "has_props",
])

# ---------------------------------------------------------------------------
# QUERIES  (label, category, query_params)
# ---------------------------------------------------------------------------
QUERIES = [
    # Semiconductors
    ("silicon",             "semiconductor",    {"chemsys": "Si"}),
    ("silicon_compounds",   "semiconductor",    {"elements": "Si", "nelements_max": 3}),
    ("germanium",           "semiconductor",    {"chemsys": "Ge"}),
    ("gallium_arsenide",    "semiconductor",    {"chemsys": "Ga-As"}),
    ("gallium_nitride",     "semiconductor",    {"chemsys": "Ga-N"}),
    ("indium_phosphide",    "semiconductor",    {"chemsys": "In-P"}),
    ("zinc_oxide",          "semiconductor",    {"chemsys": "Zn-O"}),
    ("cadmium_telluride",   "semiconductor",    {"chemsys": "Cd-Te"}),
    ("perovskite_oxide",    "semiconductor",    {"chemsys": "Ba-Ti-O"}),
    ("wide_bandgap",        "semiconductor",    {"band_gap_min": 2.5, "band_gap_max": 6.0, "is_metal": False}),
    ("narrow_bandgap",      "semiconductor",    {"band_gap_min": 0.1, "band_gap_max": 1.5, "is_metal": False}),
    # Metals
    ("iron",                "metal",            {"chemsys": "Fe"}),
    ("iron_alloys",         "metal",            {"elements": "Fe", "nelements_max": 3, "is_metal": True}),
    ("copper",              "metal",            {"chemsys": "Cu"}),
    ("copper_alloys",       "metal",            {"elements": "Cu", "nelements_max": 3, "is_metal": True}),
    ("aluminum",            "metal",            {"chemsys": "Al"}),
    ("titanium",            "metal",            {"chemsys": "Ti"}),
    ("titanium_alloys",     "metal",            {"elements": "Ti", "nelements_max": 3, "is_metal": True}),
    ("nickel",              "metal",            {"chemsys": "Ni"}),
    ("gold",                "metal",            {"chemsys": "Au"}),
    ("silver",              "metal",            {"chemsys": "Ag"}),
    ("platinum",            "metal",            {"chemsys": "Pt"}),
    ("tungsten",            "metal",            {"chemsys": "W"}),
    # Magnetic
    ("ferromagnetic",       "magnetic",         {"is_magnetic": True, "ordering": "FM"}),
    ("antiferromagnetic",   "magnetic",         {"is_magnetic": True, "ordering": "AFM"}),
    ("iron_magnetic",       "magnetic",         {"elements": "Fe", "is_magnetic": True}),
    ("cobalt_magnetic",     "magnetic",         {"elements": "Co", "is_magnetic": True}),
    ("manganese_magnetic",  "magnetic",         {"elements": "Mn", "is_magnetic": True}),
    # Battery
    ("lithium_compounds",   "battery",          {"elements": "Li", "nelements_max": 4}),
    ("lithium_iron",        "battery",          {"chemsys": "Li-Fe-O"}),
    ("lithium_cobalt",      "battery",          {"chemsys": "Li-Co-O"}),
    ("lithium_manganese",   "battery",          {"chemsys": "Li-Mn-O"}),
    ("lithium_nickel",      "battery",          {"chemsys": "Li-Ni-O"}),
    ("sodium_compounds",    "battery",          {"elements": "Na", "nelements_max": 3}),
    ("phosphate_cathode",   "battery",          {"chemsys": "Li-Fe-P-O"}),
    # Ceramics
    ("alumina",             "ceramic",          {"chemsys": "Al-O"}),
    ("silica",              "ceramic",          {"chemsys": "Si-O"}),
    ("titania",             "ceramic",          {"chemsys": "Ti-O"}),
    ("iron_oxide",          "ceramic",          {"chemsys": "Fe-O"}),
    ("zinc_sulfide",        "ceramic",          {"chemsys": "Zn-S"}),
    ("calcium_carbonate",   "ceramic",          {"chemsys": "Ca-C-O"}),
    ("zirconia",            "ceramic",          {"chemsys": "Zr-O"}),
    ("magnesium_oxide",     "ceramic",          {"chemsys": "Mg-O"}),
    # 2D Materials
    ("molybdenum_disulfide","2d_material",      {"chemsys": "Mo-S"}),
    ("graphene_like",       "2d_material",      {"chemsys": "C"}),
    ("boron_nitride",       "2d_material",      {"chemsys": "B-N"}),
    ("tungsten_disulfide",  "2d_material",      {"chemsys": "W-S"}),
    ("tungsten_diselenide", "2d_material",      {"chemsys": "W-Se"}),
    ("black_phosphorus",    "2d_material",      {"chemsys": "P"}),
    # Superconductors
    ("yttrium_barium",      "superconductor",   {"chemsys": "Y-Ba-Cu-O"}),
    ("niobium",             "superconductor",   {"chemsys": "Nb"}),
    ("lanthanum_compounds", "superconductor",   {"elements": "La", "nelements_max": 4}),
    # Catalysts
    ("platinum_catalysts",  "catalyst",         {"elements": "Pt", "nelements_max": 3}),
    ("palladium_catalysts", "catalyst",         {"elements": "Pd", "nelements_max": 3}),
    ("vanadium_oxide",      "catalyst",         {"chemsys": "V-O"}),
    ("cerium_oxide",        "catalyst",         {"chemsys": "Ce-O"}),
    # Thermoelectrics
    ("bismuth_telluride",   "thermoelectric",   {"chemsys": "Bi-Te"}),
    ("lead_telluride",      "thermoelectric",   {"chemsys": "Pb-Te"}),
    ("tin_selenide",        "thermoelectric",   {"chemsys": "Sn-Se"}),
    # Minerals
    ("diamond",             "mineral",          {"chemsys": "C"}),
    ("pyrite",              "mineral",          {"chemsys": "Fe-S"}),
    ("halite",              "mineral",          {"chemsys": "Na-Cl"}),
    ("fluorite",            "mineral",          {"chemsys": "Ca-F"}),
    ("corundum",            "mineral",          {"chemsys": "Al-O"}),
    # Rare Earth
    ("neodymium_magnet",    "rare_earth",       {"chemsys": "Nd-Fe-B"}),
    ("samarium_cobalt",     "rare_earth",       {"chemsys": "Sm-Co"}),
    ("cerium_compounds",    "rare_earth",       {"elements": "Ce", "nelements_max": 3}),
    # Stable
    ("stable_binary",       "stable",           {"is_stable": True, "nelements_max": 2}),
    ("stable_ternary",      "stable",           {"is_stable": True, "nelements_min": 3, "nelements_max": 3}),
    # Crystal systems
    ("cubic",               "crystal_system",   {"crystal_system": "cubic",        "nelements_max": 3}),
    ("hexagonal",           "crystal_system",   {"crystal_system": "hexagonal",    "nelements_max": 3}),
    ("tetragonal",          "crystal_system",   {"crystal_system": "tetragonal",   "nelements_max": 3}),
    ("monoclinic",          "crystal_system",   {"crystal_system": "monoclinic",   "nelements_max": 3}),
    ("orthorhombic",        "crystal_system",   {"crystal_system": "orthorhombic", "nelements_max": 3}),
    ("trigonal",            "crystal_system",   {"crystal_system": "trigonal",     "nelements_max": 3}),
    # Piezoelectric
    ("barium_titanate",     "piezoelectric",    {"chemsys": "Ba-Ti-O"}),
    ("potassium_niobate",   "piezoelectric",    {"chemsys": "K-Nb-O"}),
    # Topological
    ("bismuth_compounds",   "topological",      {"elements": "Bi", "nelements_max": 3}),
    ("telluride_compounds", "topological",      {"elements": "Te", "nelements_max": 3}),
]

# ---------------------------------------------------------------------------
# API HELPER
# ---------------------------------------------------------------------------
def query_materials(params: dict, max_results: int = MAX_PER_QUERY) -> list[dict]:
    all_results = []
    offset = 0
    while len(all_results) < max_results:
        limit = min(PAGE_SIZE, max_results - len(all_results))
        query_params = {
            **params,
            "_fields": FIELDS,
            "_limit":  limit,
            "_skip":   offset,
            "deprecated": False,
        }
        try:
            r = requests.get(
                f"{BASE_URL}/materials/summary/",
                headers=HEADERS,
                params=query_params,
                timeout=30,
            )
            if r.status_code == 200:
                data    = r.json()
                results = data.get("data", [])
                all_results.extend(results)
                if len(results) < limit:
                    break
                offset += len(results)
            elif r.status_code == 401:
                print("\n  [ERROR] Invalid API key — check your .env file.")
                return []
            else:
                print(f"\n  [WARN] {r.status_code}: {r.text[:150]}")
                break
        except Exception as e:
            print(f"\n  [ERROR] {e}")
            break
        time.sleep(DELAY)
    return all_results


# ---------------------------------------------------------------------------
# TRANSFORM
# ---------------------------------------------------------------------------
def transform(raw: dict, label: str, category: str) -> dict:
    mp_id       = raw.get("material_id", "")
    formula     = raw.get("formula_pretty", "")
    symmetry    = raw.get("symmetry") or {}
    crystal_sys = raw.get("crystal_system") or symmetry.get("crystal_system", "")
    spacegroup  = raw.get("spacegroup_symbol") or symmetry.get("symbol", "")
    band_gap    = raw.get("band_gap")
    is_metal    = raw.get("is_metal")
    is_magnetic = raw.get("is_magnetic")
    formation_e = raw.get("formation_energy_per_atom")
    e_hull      = raw.get("energy_above_hull")
    has_props   = raw.get("has_props", [])
    if isinstance(has_props, dict):
        has_props = list(has_props.keys())

    mat_type = "metal" if is_metal else (
        "insulator"    if band_gap and band_gap > 3 else
        "semiconductor" if band_gap else "unknown"
    )

    desc = [f"{formula} is a {crystal_sys} {mat_type}."]
    if spacegroup:               desc.append(f"Space group: {spacegroup}.")
    if band_gap is not None:     desc.append(f"Band gap: {band_gap:.2f} eV.")
    if is_magnetic:              desc.append("Magnetic material.")
    if formation_e is not None:  desc.append(f"Formation energy: {formation_e:.3f} eV/atom.")
    if e_hull == 0:              desc.append("Thermodynamically stable.")
    if has_props:                desc.append(f"Properties: {', '.join(has_props[:6])}.")

    return {
        "id":                        f"mp_{mp_id}",
        "material_id":               mp_id,
        "name":                      formula,
        "label":                     label,
        "category":                  category,
        "description":               " ".join(desc),
        "formula_pretty":            formula,
        "formula_anonymous":         raw.get("formula_anonymous", ""),
        "chemsys":                   raw.get("chemsys", ""),
        "elements":                  raw.get("elements", []),
        "nelements":                 raw.get("nelements"),
        "nsites":                    raw.get("nsites"),
        "volume":                    raw.get("volume"),
        "density":                   raw.get("density"),
        "crystal_system":            crystal_sys,
        "spacegroup_symbol":         spacegroup,
        "spacegroup_number":         raw.get("spacegroup_number") or symmetry.get("number"),
        "point_group":               raw.get("point_group") or symmetry.get("point_group", ""),
        "is_stable":                 raw.get("is_stable"),
        "is_metal":                  is_metal,
        "is_magnetic":               is_magnetic,
        "magnetic_ordering":         raw.get("ordering"),
        "total_magnetization":       raw.get("total_magnetization"),
        "band_gap":                  band_gap,
        "cbm":                       raw.get("cbm"),
        "vbm":                       raw.get("vbm"),
        "energy_per_atom":           raw.get("energy_per_atom"),
        "energy_above_hull":         e_hull,
        "formation_energy_per_atom": formation_e,
        "theoretical":               raw.get("theoretical"),
        "has_props":                 has_props,
        "icsd_ids":                  (raw.get("database_IDs") or {}).get("icsd", []),
        "source":                    "Materials Project",
        "source_type":               "crystal_structure_database",
        "render_type":               "crystal_viewer",
        "embed_url":                 f"https://next-gen.materialsproject.org/materials/{mp_id}",
        "fetch_url_cif":             f"https://materialsproject.org/materials/{mp_id}/cif",
        "fetch_url_json":            f"{BASE_URL}/materials/{mp_id}/?_fields=structure",
        "mp_page":                   f"https://next-gen.materialsproject.org/materials/{mp_id}",
        "local_file":                None,
        "runtime_fetch":             True,
        "license":                   "CC BY 4.0 (Materials Project)",
    }


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    if not API_KEY:
        print("\n" + "="*60)
        print("  ERROR: MP_API_KEY not found!")
        print("  Steps:")
        print("  1. Get free key → https://next-gen.materialsproject.org/api")
        print("  2. Copy .env.example to .env in your project root")
        print("  3. Set MP_API_KEY=your_key in .env")
        print("="*60 + "\n")
        return

    print("=" * 60)
    print("  Materials Project Metadata Scraper")
    print(f"  {len(QUERIES)} queries — no local downloads")
    print("=" * 60)

    id_to_entry: dict[str, dict] = {}

    for i, (label, category, params) in enumerate(QUERIES):
        print(f"  [{i+1}/{len(QUERIES)}] {label}...", end=" ", flush=True)
        results = query_materials(params)
        if not results and i == 0:
            print("\n  Stopping — check API key.")
            return
        new = 0
        for raw in results:
            mp_id = raw.get("material_id", "")
            if mp_id and mp_id not in id_to_entry:
                id_to_entry[mp_id] = transform(raw, label, category)
                new += 1
        print(f"{new} new  (total: {len(id_to_entry)})")

    metadata = sorted(id_to_entry.values(), key=lambda x: x["material_id"])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"  ✅ Written → {OUTPUT_FILE}")
    print(f"  Total entries:    {len(metadata)}")
    print(f"  Metals:           {sum(1 for e in metadata if e['is_metal'])}")
    print(f"  Magnetic:         {sum(1 for e in metadata if e['is_magnetic'])}")
    print(f"  Stable:           {sum(1 for e in metadata if e.get('energy_above_hull') == 0)}")
    print(f"  With band gap:    {sum(1 for e in metadata if e['band_gap'] is not None)}")
    print(f"\n  By category:")
    for cat, count in sorted(Counter(e['category'] for e in metadata).items(), key=lambda x: -x[1]):
        print(f"    {cat:<25} {count}")
    print("=" * 60)


if __name__ == "__main__":
    main()