"""
build_indexes.py — ConceptCraftAI
Full pipeline: scrape all datasets → build FAISS indexes per domain

Domains (matches search.py exactly):
  biological   ← NIH 3D, RCSB Protein Data Bank, MedShapeNet
  astronomical ← NASA 3D Resources, NASA Kepler, Sketchfab Planets, SkyBot 3D, Solar System Scope
  chemical     ← PubChem, Materials Project, ATOM3D
  physical     ← (Sketchfab general mechanical/physical models via API)

Run:
  pip install requests beautifulsoup4 sentence-transformers faiss-cpu numpy python-dotenv tqdm
  python build_indexes.py

Output:
  indexes/biological.index   + indexes/biological.json
  indexes/astronomical.index + indexes/astronomical.json
  indexes/chemical.index     + indexes/chemical.json
  indexes/physical.index     + indexes/physical.json
"""

import os
import json
import time
import re
import requests
import numpy as np
import faiss
from pathlib import Path
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
INDEXES_DIR          = Path("indexes")
MINILM_MODEL         = "all-MiniLM-L6-v2"
SKETCHFAB_API_TOKEN  = os.getenv("SKETCHFAB_API_TOKEN", "")
SKETCHFAB_API_BASE   = "https://api.sketchfab.com/v3"
PUBCHEM_API_BASE     = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
RCSB_API_BASE        = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_DATA_BASE       = "https://data.rcsb.org/rest/v1/core/entry"
MATERIALS_API_BASE   = "https://api.materialsproject.org"
MATERIALS_API_KEY    = os.getenv("MATERIALS_PROJECT_API_KEY", "")

HEADERS = {"User-Agent": "ConceptCraftAI/1.0 (research scraper)"}
REQUEST_DELAY = 0.5   # seconds between requests — be polite

INDEXES_DIR.mkdir(exist_ok=True)

# ── Embedding model ───────────────────────────────────────────────────────────
print(f"Loading MiniLM: {MINILM_MODEL}")
minilm = SentenceTransformer(MINILM_MODEL)
print("  MiniLM ready ✅\n")


# ── Helpers ───────────────────────────────────────────────────────────────────
def get(url, params=None, headers=None, timeout=15, retries=3):
    """Safe GET with retries."""
    h = {**HEADERS, **(headers or {})}
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=h, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            if attempt == retries - 1:
                print(f"  [WARN] GET failed: {url} — {e}")
                return None
            time.sleep(1.5 ** attempt)
    return None


def make_embed_text(entry: dict) -> str:
    """
    Build the text string that will be embedded into FAISS.
    Combines name, description, tags, category, domain.
    """
    parts = [
        entry.get("name", ""),
        entry.get("description", ""),
        " ".join(entry.get("tags", [])),
        str(entry.get("category", "")),
        entry.get("domain", ""),
        entry.get("formula", ""),
        entry.get("formula_pretty", ""),
        " ".join(entry.get("elements", [])),
    ]
    return " ".join(p for p in parts if p).strip()


def build_faiss_index(entries: list[dict], domain: str):
    """
    Embed all entries with MiniLM → build FAISS IP index → save .index + .json
    """
    if not entries:
        print(f"  [SKIP] No entries for domain '{domain}'")
        return

    print(f"\n  Building FAISS index for '{domain}' ({len(entries)} entries)...")

    # Attach embed_text to each entry
    for e in entries:
        e["embed_text"] = make_embed_text(e)

    texts = [e["embed_text"] for e in entries]

    # Embed in batches
    batch_size = 64
    all_vecs = []
    for i in tqdm(range(0, len(texts), batch_size), desc=f"  Embedding {domain}"):
        batch = texts[i:i+batch_size]
        vecs  = minilm.encode(batch, convert_to_numpy=True).astype(np.float32)
        faiss.normalize_L2(vecs)
        all_vecs.append(vecs)

    matrix = np.vstack(all_vecs)
    dim    = matrix.shape[1]

    index = faiss.IndexFlatIP(dim)
    index.add(matrix)

    index_path = INDEXES_DIR / f"{domain}.index"
    json_path  = INDEXES_DIR / f"{domain}.json"

    faiss.write_index(index, str(index_path))

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    print(f"  Saved: {index_path} ({index.ntotal} vectors, dim={dim})")
    print(f"  Saved: {json_path}")


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPERS
# ══════════════════════════════════════════════════════════════════════════════

# ── 1. NIH 3D ─────────────────────────────────────────────────────────────────
def scrape_nih3d(limit=300) -> list[dict]:
    """
    Scrape NIH 3D Print Exchange via their search API.
    Returns biological anatomy/cell/virus models.
    """
    print("\n[NIH 3D] Scraping...")
    results = []
    base    = "https://3d.nih.gov/search/"
    queries = ["anatomy", "virus", "cell", "organ", "bacteria", "protein", "molecule"]

    seen = set()
    for q in queries:
        page = 1
        while len(results) < limit:
            r = get(base, params={"q": q, "page": page, "format": "json"})
            if not r:
                break
            try:
                data  = r.json()
                items = data.get("results", data.get("objects", []))
                if not items:
                    break
                for item in items:
                    uid = str(item.get("id") or item.get("nid") or item.get("uuid", ""))
                    if uid in seen:
                        continue
                    seen.add(uid)
                    results.append({
                        "name":          item.get("title") or item.get("name") or "NIH 3D Model",
                        "description":   item.get("body") or item.get("description") or "",
                        "tags":          item.get("tags") or [q],
                        "category":      item.get("category") or "anatomy",
                        "domain":        "biological",
                        "formats":       ["OBJ", "STL"],
                        "license":       "open",
                        "source":        "nih3d",
                        "url":           f"https://3d.nih.gov/entries/{uid}" if uid else "https://3d.nih.gov/",
                        "thumbnail_url": item.get("thumbnail") or item.get("image") or "",
                        "uid":           uid,
                        "embed_url":     "",
                    })
                page += 1
                time.sleep(REQUEST_DELAY)
            except Exception as e:
                print(f"  [WARN] NIH parse error: {e}")
                break

    # Fallback: scrape HTML if API returned nothing
    if not results:
        print("  [NIH 3D] API returned nothing — scraping HTML...")
        r = get("https://3d.nih.gov/")
        if r:
            soup  = BeautifulSoup(r.text, "html.parser")
            cards = soup.select(".views-row, .model-card, article")
            for card in cards[:limit]:
                title = card.select_one("h2, h3, .title")
                desc  = card.select_one("p, .description, .body")
                link  = card.select_one("a")
                results.append({
                    "name":        title.get_text(strip=True) if title else "NIH 3D Model",
                    "description": desc.get_text(strip=True)  if desc  else "",
                    "tags":        ["anatomy", "biology", "3d model"],
                    "category":    "anatomy",
                    "domain":      "biological",
                    "formats":     ["OBJ", "STL"],
                    "license":     "open",
                    "source":      "nih3d",
                    "url":         "https://3d.nih.gov" + link["href"] if link and link.get("href") else "https://3d.nih.gov/",
                    "thumbnail_url": "",
                    "embed_url":   "",
                })

    print(f"  [NIH 3D] Got {len(results)} entries")
    return results


# ── 2. RCSB Protein Data Bank ─────────────────────────────────────────────────
def scrape_rcsb(limit=500) -> list[dict]:
    """
    Query RCSB Search API for protein structures.
    Uses full-text search across multiple biology keywords.
    """
    print("\n[RCSB PDB] Scraping...")
    results = []
    seen    = set()

    queries = [
        "virus capsid", "DNA", "RNA polymerase", "antibody", "enzyme",
        "membrane protein", "ribosome", "collagen", "hemoglobin", "insulin",
        "ATP synthase", "photosystem", "actin", "myosin", "tubulin"
    ]

    for q in queries:
        if len(results) >= limit:
            break

        payload = {
            "query": {
                "type": "terminal",
                "service": "full_text",
                "parameters": {"value": q}
            },
            "return_type": "entry",
            "request_options": {
                "paginate": {"start": 0, "rows": min(50, limit - len(results))},
                "sort": [{"sort_by": "score", "direction": "desc"}]
            }
        }

        r = get(RCSB_API_BASE, headers={"Content-Type": "application/json"})
        # RCSB uses POST for search
        try:
            resp = requests.post(RCSB_API_BASE, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  [WARN] RCSB search failed for '{q}': {e}")
            time.sleep(REQUEST_DELAY)
            continue

        for hit in data.get("result_set", []):
            pdb_id = hit.get("identifier", "")
            if not pdb_id or pdb_id in seen:
                continue
            seen.add(pdb_id)

            # Fetch entry details
            detail_r = get(f"{RCSB_DATA_BASE}/{pdb_id}")
            if not detail_r:
                entry_name = pdb_id
                entry_desc = q
                organism   = ""
            else:
                try:
                    d          = detail_r.json()
                    entry_name = d.get("struct", {}).get("title", pdb_id)
                    entry_desc = d.get("struct", {}).get("pdbx_descriptor", "")
                    organism   = d.get("rcsb_entry_info", {}).get("source_organism_commonname", "")
                except Exception:
                    entry_name = pdb_id
                    entry_desc = q
                    organism   = ""

            results.append({
                "name":        entry_name,
                "description": entry_desc,
                "tags":        ["protein", "structure", q] + ([organism] if organism else []),
                "category":    "protein",
                "domain":      "biological",
                "formats":     ["PDB", "CIF", "mmCIF"],
                "license":     "open",
                "source":      "rcsb_pdb",
                "url":         f"https://www.rcsb.org/structure/{pdb_id}",
                "embed_url":   f"https://www.rcsb.org/3d-view/{pdb_id}",
                "thumbnail_url": f"https://cdn.rcsb.org/images/structures/{pdb_id.lower()[1:3]}/{pdb_id.lower()}/{pdb_id.lower()}_assembly-1.jpeg",
                "pdb_id":      pdb_id,
                "organism":    organism,
            })
            time.sleep(0.1)

        time.sleep(REQUEST_DELAY)

    print(f"  [RCSB PDB] Got {len(results)} entries")
    return results


# ── 3. NASA 3D Resources ──────────────────────────────────────────────────────
def scrape_nasa(limit=200) -> list[dict]:
    """
    Scrape NASA 3D Resources page + NASA assets API.
    """
    print("\n[NASA 3D] Scraping...")
    results = []

    # NASA Images & Media API — filter for 3D models
    nasa_api = "https://images-api.nasa.gov/search"
    queries  = ["spacecraft 3D model", "satellite", "planet", "mars rover", "telescope", "moon", "rocket"]

    seen = set()
    for q in queries:
        if len(results) >= limit:
            break
        r = get(nasa_api, params={"q": q, "media_type": "image", "page_size": 20})
        if not r:
            continue
        try:
            items = r.json().get("collection", {}).get("items", [])
            for item in items:
                data  = item.get("data", [{}])[0]
                nasa_id = data.get("nasa_id", "")
                if not nasa_id or nasa_id in seen:
                    continue
                seen.add(nasa_id)
                links = item.get("links", [])
                thumb = links[0].get("href", "") if links else ""
                results.append({
                    "name":        data.get("title", "NASA Model"),
                    "description": data.get("description", "")[:500],
                    "tags":        data.get("keywords", []) or [q, "space", "nasa"],
                    "category":    "spacecraft" if "spacecraft" in q or "satellite" in q else "space",
                    "domain":      "astronomical",
                    "formats":     ["OBJ", "GLTF"],
                    "license":     "NASA open",
                    "source":      "nasa",
                    "url":         f"https://images.nasa.gov/details/{nasa_id}",
                    "embed_url":   "",
                    "thumbnail_url": thumb,
                    "nasa_id":     nasa_id,
                    "date":        data.get("date_created", ""),
                })
        except Exception as e:
            print(f"  [WARN] NASA parse error: {e}")
        time.sleep(REQUEST_DELAY)

    # Also scrape the static NASA 3D models page
    r = get("https://science.nasa.gov/3d-resources/")
    if r:
        soup  = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("article, .card, .model-item, li")
        for card in cards[:100]:
            title = card.select_one("h2, h3, h4, .title, strong")
            desc  = card.select_one("p, .desc")
            link  = card.select_one("a[href]")
            if not title:
                continue
            name = title.get_text(strip=True)
            if name in seen or len(name) < 3:
                continue
            seen.add(name)
            href = link["href"] if link else ""
            if href and not href.startswith("http"):
                href = "https://science.nasa.gov" + href
            results.append({
                "name":        name,
                "description": desc.get_text(strip=True) if desc else "",
                "tags":        ["space", "nasa", "3d model"],
                "category":    "space",
                "domain":      "astronomical",
                "formats":     ["OBJ", "GLTF"],
                "license":     "NASA open",
                "source":      "nasa",
                "url":         href or "https://science.nasa.gov/3d-resources/",
                "embed_url":   "",
                "thumbnail_url": "",
            })

    print(f"  [NASA 3D] Got {len(results)} entries")
    return results


# ── 4. Sketchfab API ──────────────────────────────────────────────────────────
def scrape_sketchfab(domain: str, queries: list[str], limit=200) -> list[dict]:
    """
    Pull models from Sketchfab API for a given domain + query list.
    Works with or without API token (token gives higher rate limits).
    """
    label = f"Sketchfab ({domain})"
    print(f"\n[{label}] Scraping...")

    if not SKETCHFAB_API_TOKEN:
        print(f"  [WARN] No SKETCHFAB_API_TOKEN — rate limits will be lower")

    headers = {}
    if SKETCHFAB_API_TOKEN:
        headers["Authorization"] = f"Token {SKETCHFAB_API_TOKEN}"

    results = []
    seen    = set()

    for q in queries:
        if len(results) >= limit:
            break
        cursor = None
        while len(results) < limit:
            params = {
                "q":           q,
                "type":        "models",
                "count":       24,
                "sort_by":     "-likeCount",
                "staffpicked": True,
            }
            if cursor:
                params["cursor"] = cursor

            r = get(f"{SKETCHFAB_API_BASE}/models", params=params, headers=headers)
            if not r:
                break
            try:
                data = r.json()
            except Exception:
                break

            for m in data.get("results", []):
                uid = m.get("uid", "")
                if not uid or uid in seen:
                    continue
                seen.add(uid)

                thumbnails = m.get("thumbnails", {}).get("images", [])
                thumb = next(
                    (img["url"] for img in thumbnails if img.get("width", 0) >= 200),
                    thumbnails[0]["url"] if thumbnails else ""
                )

                tags = [t["name"] for t in m.get("tags", [])]

                results.append({
                    "name":          m.get("name", "Untitled"),
                    "description":   (m.get("description") or "")[:500],
                    "tags":          tags or [q],
                    "category":      q,
                    "domain":        domain,
                    "formats":       ["GLTF", "GLB"],
                    "license":       m.get("license", {}).get("label", "varies") if m.get("license") else "varies",
                    "source":        "sketchfab",
                    "uid":           uid,
                    "url":           f"https://sketchfab.com/models/{uid}",
                    "embed_url":     f"https://sketchfab.com/models/{uid}/embed",
                    "thumbnail_url": thumb,
                    "viewCount":     m.get("viewCount", 0),
                    "likeCount":     m.get("likeCount", 0),
                    "isAnimated":    m.get("isAnimated", False),
                    "vertexCount":   m.get("vertexCount", 0),
                })

            next_url = data.get("next")
            if not next_url:
                break
            # Extract cursor from next URL
            match = re.search(r"cursor=([^&]+)", next_url)
            cursor = match.group(1) if match else None
            if not cursor:
                break
            time.sleep(REQUEST_DELAY)

        time.sleep(REQUEST_DELAY)

    print(f"  [{label}] Got {len(results)} entries")
    return results


# ── 5. PubChem ────────────────────────────────────────────────────────────────
def scrape_pubchem(limit=500) -> list[dict]:
    """
    Fetch compounds from PubChem REST API.
    Gets name, formula, description, synonyms, structure info.
    """
    print("\n[PubChem] Scraping...")

    # Common chemistry concepts to search
    compounds = [
        "glucose", "caffeine", "aspirin", "water", "ethanol", "ATP",
        "cholesterol", "dopamine", "serotonin", "insulin", "penicillin",
        "DNA", "RNA", "acetylcholine", "adrenaline", "testosterone",
        "vitamin C", "vitamin D", "hemoglobin", "chlorophyll",
        "methane", "benzene", "acetone", "ammonia", "sulfuric acid",
        "sodium chloride", "calcium carbonate", "carbon dioxide",
        "nitric oxide", "ozone", "silicon dioxide", "iron oxide",
        "silver", "gold", "platinum", "diamond", "graphene",
        "paracetamol", "ibuprofen", "morphine", "nicotine", "capsaicin",
        "sucrose", "fructose", "lactose", "starch", "cellulose",
    ]

    results = []
    seen    = set()

    for name in tqdm(compounds[:limit], desc="  PubChem compounds"):
        r = get(f"{PUBCHEM_API_BASE}/compound/name/{requests.utils.quote(name)}/JSON")
        if not r:
            time.sleep(REQUEST_DELAY)
            continue
        try:
            data = r.json()
            compounds_data = data.get("PC_Compounds", [])
            if not compounds_data:
                continue
            c   = compounds_data[0]
            cid = c.get("id", {}).get("id", {}).get("cid", "")
            if not cid or str(cid) in seen:
                continue
            seen.add(str(cid))

            props = {p["urn"]["label"]: p.get("value", {}) for p in c.get("props", []) if "urn" in p and "label" in p["urn"]}

            formula      = props.get("Molecular Formula", {}).get("sval", "")
            mol_weight   = props.get("Molecular Weight",  {}).get("fval", "")
            iupac        = props.get("IUPAC Name",        {}).get("sval", name)
            smiles       = props.get("Canonical SMILES",  {}).get("sval", "")

            # Get description
            desc_r = get(f"{PUBCHEM_API_BASE}/compound/cid/{cid}/description/JSON")
            description = ""
            if desc_r:
                desc_data   = desc_r.json().get("InformationList", {}).get("Information", [])
                description = next((d.get("Description", "") for d in desc_data if d.get("Description")), "")

            results.append({
                "name":          name.title(),
                "iupac_name":    iupac,
                "description":   description[:500],
                "formula":       formula,
                "formula_pretty": formula,
                "mol_weight":    str(mol_weight),
                "smiles":        smiles,
                "tags":          ["molecule", "compound", "chemistry", name.lower()],
                "category":      "molecule",
                "domain":        "chemical",
                "formats":       ["SDF", "JSON", "3D-SDF"],
                "license":       "open",
                "source":        "pubchem",
                "cid":           str(cid),
                "url":           f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
                "embed_url":     f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}#section=3D-Conformer",
                "thumbnail_url": f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG",
            })
        except Exception as e:
            print(f"  [WARN] PubChem parse error for '{name}': {e}")

        time.sleep(REQUEST_DELAY)

    print(f"  [PubChem] Got {len(results)} entries")
    return results


# ── 6. Materials Project ──────────────────────────────────────────────────────
def scrape_materials_project(limit=300) -> list[dict]:
    """
    Fetch crystal structures from Materials Project API.
    Requires free API key from materialsproject.org
    """
    print("\n[Materials Project] Scraping...")

    if not MATERIALS_API_KEY:
        print("  [WARN] No MATERIALS_PROJECT_API_KEY in .env — using public fallback")
        return _scrape_materials_fallback(limit)

    results = []
    headers = {"X-API-KEY": MATERIALS_API_KEY}

    # Search for common materials
    element_groups = [
        "Fe,O",    # Iron oxides
        "Si,O",    # Silicates
        "Ca,C,O",  # Carbonates
        "Al,O",    # Alumina
        "Ti,O",    # Titanium oxide
        "Cu",      # Copper
        "Au",      # Gold
        "C",       # Carbon (diamond, graphite)
        "Na,Cl",   # Salt
        "Li,O",    # Lithium compounds (batteries)
    ]

    for chemsys in element_groups:
        if len(results) >= limit:
            break
        r = get(
            f"{MATERIALS_API_BASE}/materials/core/",
            params={"chemsys": chemsys, "_limit": 20, "_fields": "material_id,formula_pretty,structure,symmetry,elements,chemsys,theoretical,energy_above_hull"},
            headers=headers
        )
        if not r:
            time.sleep(REQUEST_DELAY)
            continue
        try:
            for m in r.json().get("data", []):
                mid     = m.get("material_id", "")
                formula = m.get("formula_pretty", "")
                sym     = m.get("symmetry", {})
                results.append({
                    "name":           formula or mid,
                    "description":    f"{formula} crystal structure. Space group: {sym.get('symbol', '')}. System: {sym.get('crystal_system', '')}.",
                    "formula":        formula,
                    "formula_pretty": formula,
                    "elements":       m.get("elements", []),
                    "chemsys":        m.get("chemsys", ""),
                    "crystal_system": sym.get("crystal_system", ""),
                    "space_group":    sym.get("symbol", ""),
                    "tags":           ["crystal", "material", "structure"] + m.get("elements", []),
                    "category":       "material",
                    "domain":         "chemical",
                    "formats":        ["CIF", "JSON"],
                    "license":        "open",
                    "source":         "materials_project",
                    "material_id":    mid,
                    "url":            f"https://next-gen.materialsproject.org/materials/{mid}",
                    "embed_url":      f"https://next-gen.materialsproject.org/materials/{mid}",
                    "thumbnail_url":  "",
                    "has_props":      True,
                })
        except Exception as e:
            print(f"  [WARN] Materials Project parse error: {e}")
        time.sleep(REQUEST_DELAY)

    print(f"  [Materials Project] Got {len(results)} entries")
    return results


def _scrape_materials_fallback(limit=100) -> list[dict]:
    """Fallback: hardcoded common crystal materials when no API key."""
    materials = [
        ("diamond",       "C",       ["carbon"],               "Cubic",       "Fd-3m"),
        ("graphite",      "C",       ["carbon"],               "Hexagonal",   "P6_3/mmc"),
        ("quartz",        "SiO2",    ["silicon", "oxygen"],    "Trigonal",    "P3_121"),
        ("iron",          "Fe",      ["iron"],                 "Cubic",       "Im-3m"),
        ("gold",          "Au",      ["gold"],                 "Cubic",       "Fm-3m"),
        ("silver",        "Ag",      ["silver"],               "Cubic",       "Fm-3m"),
        ("copper",        "Cu",      ["copper"],               "Cubic",       "Fm-3m"),
        ("salt",          "NaCl",    ["sodium", "chlorine"],   "Cubic",       "Fm-3m"),
        ("calcite",       "CaCO3",   ["calcium", "carbon"],    "Trigonal",    "R-3c"),
        ("hematite",      "Fe2O3",   ["iron", "oxygen"],       "Trigonal",    "R-3c"),
        ("rutile",        "TiO2",    ["titanium", "oxygen"],   "Tetragonal",  "P4_2/mnm"),
        ("corundum",      "Al2O3",   ["aluminum", "oxygen"],   "Trigonal",    "R-3c"),
        ("pyrite",        "FeS2",    ["iron", "sulfur"],       "Cubic",       "Pa-3"),
        ("fluorite",      "CaF2",    ["calcium", "fluorine"],  "Cubic",       "Fm-3m"),
        ("galena",        "PbS",     ["lead", "sulfur"],       "Cubic",       "Fm-3m"),
        ("silicon",       "Si",      ["silicon"],              "Cubic",       "Fd-3m"),
        ("graphene",      "C",       ["carbon"],               "Hexagonal",   "P6/mmm"),
        ("aluminium",     "Al",      ["aluminum"],             "Cubic",       "Fm-3m"),
        ("magnesium",     "Mg",      ["magnesium"],            "Hexagonal",   "P6_3/mmc"),
        ("zinc oxide",    "ZnO",     ["zinc", "oxygen"],       "Hexagonal",   "P6_3mc"),
    ]
    results = []
    for name, formula, elements, crystal_system, space_group in materials[:limit]:
        results.append({
            "name":           name.title(),
            "description":    f"{formula} crystal. {crystal_system} system, space group {space_group}.",
            "formula":        formula,
            "formula_pretty": formula,
            "elements":       elements,
            "chemsys":        "-".join(sorted(set(elements))),
            "crystal_system": crystal_system,
            "space_group":    space_group,
            "tags":           ["crystal", "material", name] + elements,
            "category":       "material",
            "domain":         "chemical",
            "formats":        ["CIF", "JSON"],
            "license":        "open",
            "source":         "materials_project_fallback",
            "url":            "https://next-gen.materialsproject.org",
            "embed_url":      "",
            "thumbnail_url":  "",
            "has_props":      True,
        })
    return results


# ── 7. SkyBot 3D (asteroids) ──────────────────────────────────────────────────
def scrape_skybot(limit=100) -> list[dict]:
    """
    Fetch asteroid data from IMCCE SkyBot3D API.
    """
    print("\n[SkyBot 3D] Scraping...")
    results = []

    # Known asteroid names to query
    asteroids = [
        "Ceres", "Vesta", "Pallas", "Hygiea", "Interamnia",
        "Davida", "Herculina", "Eunomia", "Juno", "Psyche",
        "Eros", "Itokawa", "Ryugu", "Bennu", "Apophis",
        "Ida", "Gaspra", "Mathilde", "Braille", "Lutetia",
    ]

    for name in asteroids[:limit]:
        r = get(
            "https://ssp.imcce.fr/webservices/skybot3d/api/",
            params={"name": name, "format": "json"}
        )
        if r:
            try:
                data = r.json()
                obj  = data.get("data", {}) or data
                results.append({
                    "name":        name,
                    "description": f"Asteroid {name}. {obj.get('description', '')}",
                    "tags":        ["asteroid", "solar system", "rocky body", name.lower()],
                    "category":    "asteroid",
                    "domain":      "astronomical",
                    "formats":     ["OBJ", "GLTF"],
                    "license":     "research",
                    "source":      "skybot3d",
                    "url":         f"https://ssp.imcce.fr/webservices/skybot3d/?name={name}",
                    "embed_url":   "",
                    "thumbnail_url": "",
                    "diameter_km": obj.get("diameter", ""),
                    "albedo":      obj.get("albedo", ""),
                })
            except Exception:
                # If API fails, add basic entry
                results.append({
                    "name":        name,
                    "description": f"Asteroid {name} in the solar system.",
                    "tags":        ["asteroid", "solar system", "rocky body", name.lower()],
                    "category":    "asteroid",
                    "domain":      "astronomical",
                    "formats":     ["OBJ"],
                    "license":     "research",
                    "source":      "skybot3d",
                    "url":         "https://ssp.imcce.fr/webservices/skybot3d/",
                    "embed_url":   "",
                    "thumbnail_url": "",
                })
        time.sleep(REQUEST_DELAY)

    print(f"  [SkyBot 3D] Got {len(results)} entries")
    return results


# ── 8. Solar System Scope ─────────────────────────────────────────────────────
def scrape_solar_system_scope() -> list[dict]:
    """
    Build entries for Solar System Scope planets.
    The site serves texture maps — we create rich metadata entries for each planet.
    """
    print("\n[Solar System Scope] Building planet entries...")

    planets = [
        ("Sun",     "G-type main-sequence star at the center of the solar system. Surface temperature ~5778K.",          ["star", "sun", "solar", "plasma"],              "stellar"),
        ("Mercury", "Smallest planet, no atmosphere, heavily cratered surface.",                                          ["planet", "rocky", "mercury", "inner planet"],   "planets"),
        ("Venus",   "Hottest planet, thick CO2 atmosphere, volcanic surface.",                                            ["planet", "rocky", "venus", "atmosphere"],       "planets"),
        ("Earth",   "Only known planet with life. Blue oceans, green landmasses, white clouds.",                          ["planet", "earth", "ocean", "life", "biosphere"],"planets"),
        ("Moon",    "Earth's only natural satellite. Heavily cratered, no atmosphere.",                                   ["moon", "lunar", "satellite", "craters"],        "moon"),
        ("Mars",    "Red planet with iron oxide surface. Thin atmosphere, largest volcano Olympus Mons.",                 ["planet", "mars", "red planet", "rocky"],        "planets"),
        ("Jupiter", "Largest planet. Gas giant with Great Red Spot storm. 95 known moons.",                              ["planet", "gas giant", "jupiter", "storm"],      "planets"),
        ("Saturn",  "Gas giant with iconic ring system made of ice and rock.",                                            ["planet", "saturn", "rings", "gas giant"],       "planets"),
        ("Uranus",  "Ice giant, rotates on its side. Blue-green methane atmosphere.",                                     ["planet", "ice giant", "uranus"],               "planets"),
        ("Neptune", "Farthest planet. Strongest winds in solar system. Ice giant.",                                       ["planet", "ice giant", "neptune", "wind"],       "planets"),
        ("Pluto",   "Dwarf planet in Kuiper Belt. Heart-shaped nitrogen ice plain Tombaugh Regio.",                       ["dwarf planet", "pluto", "kuiper belt"],         "dwarf planet"),
        ("Io",      "Jupiter's moon, most volcanically active body in the solar system.",                                 ["moon", "io", "jupiter", "volcano"],             "moon"),
        ("Europa",  "Jupiter's moon with subsurface ocean beneath ice crust. Potential for life.",                        ["moon", "europa", "ocean", "jupiter"],           "moon"),
        ("Ganymede","Largest moon in solar system. Larger than Mercury.",                                                 ["moon", "ganymede", "jupiter"],                  "moon"),
        ("Titan",   "Saturn's largest moon. Thick nitrogen atmosphere, liquid methane lakes.",                            ["moon", "titan", "saturn", "atmosphere"],        "moon"),
    ]

    results = []
    for name, description, tags, category in planets:
        results.append({
            "name":          name,
            "description":   description,
            "tags":          tags,
            "category":      category,
            "domain":        "astronomical",
            "formats":       ["PNG", "JPG"],
            "license":       "educational",
            "source":        "solar_system_scope",
            "url":           f"https://www.solarsystemscope.com/textures/",
            "embed_url":     "",
            "thumbnail_url": f"https://www.solarsystemscope.com/spacescapes/preview/{name.lower()}.jpg",
        })

    print(f"  [Solar System Scope] Built {len(results)} entries")
    return results


# ── 9. MedShapeNet (PyPI info) ────────────────────────────────────────────────
def scrape_medshapenet() -> list[dict]:
    """
    MedShapeNet doesn't have a public API — build rich metadata entries
    for the known organ categories it covers.
    """
    print("\n[MedShapeNet] Building organ entries...")

    organs = [
        ("Heart",         "Human heart 3D anatomy. Four chambers: left/right ventricle and atrium. Cardiac muscle.",               ["heart", "cardiac", "anatomy", "organ"]),
        ("Brain",         "Human brain 3D anatomy. Cerebral cortex, cerebellum, brainstem, hippocampus.",                          ["brain", "neural", "anatomy", "organ", "neuroscience"]),
        ("Lung",          "Human lungs 3D anatomy. Alveoli, bronchi, lobes. Respiratory system.",                                  ["lung", "respiratory", "anatomy", "organ"]),
        ("Liver",         "Human liver 3D anatomy. Largest internal organ. Bile production, detoxification.",                      ["liver", "hepatic", "anatomy", "organ"]),
        ("Kidney",        "Human kidney 3D anatomy. Nephrons, cortex, medulla. Filtration organ.",                                 ["kidney", "renal", "anatomy", "organ"]),
        ("Skull",         "Human skull 3D anatomy. Cranium, mandible, facial bones.",                                              ["skull", "cranium", "bone", "anatomy"]),
        ("Spine",         "Human vertebral column. Cervical, thoracic, lumbar vertebrae, intervertebral discs.",                   ["spine", "vertebra", "bone", "anatomy"]),
        ("Femur",         "Human femur — thigh bone. Largest and strongest bone in the body.",                                     ["femur", "bone", "anatomy", "leg"]),
        ("Pelvis",        "Human pelvis 3D anatomy. Hip bones, sacrum, coccyx.",                                                   ["pelvis", "hip", "bone", "anatomy"]),
        ("Aorta",         "Human aorta — main artery of the body. Ascending, arch, descending sections.",                         ["aorta", "artery", "vascular", "anatomy"]),
        ("Pancreas",      "Human pancreas. Endocrine and exocrine functions. Insulin production.",                                 ["pancreas", "organ", "anatomy", "endocrine"]),
        ("Spleen",        "Human spleen. Immune system organ. Filters blood.",                                                     ["spleen", "organ", "anatomy", "immune"]),
        ("Prostate",      "Human prostate gland 3D anatomy.",                                                                      ["prostate", "gland", "anatomy", "organ"]),
        ("Colon",         "Human large intestine / colon 3D anatomy. Digestive system.",                                          ["colon", "intestine", "digestive", "anatomy"]),
        ("Stomach",       "Human stomach 3D anatomy. Digestive organ, gastric folds.",                                             ["stomach", "gastric", "digestive", "anatomy"]),
    ]

    results = []
    for name, description, tags in organs:
        results.append({
            "name":        f"{name} — MedShapeNet",
            "description": description,
            "tags":        tags,
            "category":    "anatomy",
            "domain":      "biological",
            "formats":     ["STL", "OBJ"],
            "license":     "research",
            "source":      "medshapenet",
            "url":         "https://medshapenet.ikim.nrw/",
            "embed_url":   "",
            "thumbnail_url": "",
        })

    print(f"  [MedShapeNet] Built {len(results)} entries")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — Run all scrapers → group by domain → build indexes
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("ConceptCraftAI — Full Dataset Scraper + Indexer")
    print("=" * 60)

    # ── Collect all entries grouped by domain ─────────────────────────────────
    domain_entries = {
        "biological":   [],
        "astronomical": [],
        "chemical":     [],
        "physical":     [],
    }

    # BIOLOGICAL
    domain_entries["biological"] += scrape_nih3d(limit=300)
    domain_entries["biological"] += scrape_rcsb(limit=400)
    domain_entries["biological"] += scrape_medshapenet()
    domain_entries["biological"] += scrape_sketchfab(
        domain="biological",
        queries=["anatomy organ", "human body", "cell biology", "DNA molecule", "virus bacteria", "brain neuron", "heart", "skeleton bone"],
        limit=200
    )

    # ASTRONOMICAL
    domain_entries["astronomical"] += scrape_nasa(limit=200)
    domain_entries["astronomical"] += scrape_skybot(limit=80)
    domain_entries["astronomical"] += scrape_solar_system_scope()
    domain_entries["astronomical"] += scrape_sketchfab(
        domain="astronomical",
        queries=["planet solar system", "spacecraft satellite", "black hole galaxy", "moon crater", "asteroid meteor", "telescope observatory"],
        limit=200
    )

    # CHEMICAL
    domain_entries["chemical"] += scrape_pubchem(limit=400)
    domain_entries["chemical"] += scrape_materials_project(limit=300)
    domain_entries["chemical"] += scrape_sketchfab(
        domain="chemical",
        queries=["molecule chemistry", "crystal structure", "chemical compound", "atom molecular"],
        limit=150
    )

    # PHYSICAL
    domain_entries["physical"] += scrape_sketchfab(
        domain="physical",
        queries=["mechanical engineering", "engine machine", "gear turbine", "physics pendulum", "bridge structure", "lever pulley", "circuit electronics"],
        limit=300
    )

    # ── Deduplicate within each domain ────────────────────────────────────────
    for domain, entries in domain_entries.items():
        seen  = set()
        dedup = []
        for e in entries:
            key = e.get("name", "") + e.get("url", "")
            if key not in seen:
                seen.add(key)
                dedup.append(e)
        domain_entries[domain] = dedup
        print(f"\n  [{domain}] {len(dedup)} unique entries after dedup")

    # ── Save raw scraped data ─────────────────────────────────────────────────
    raw_path = Path("scraped_data.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(domain_entries, f, indent=2, ensure_ascii=False)
    print(f"\n  Raw data saved: {raw_path}")

    # ── Build FAISS index per domain ──────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Building FAISS indexes...")
    print("=" * 60)

    for domain, entries in domain_entries.items():
        build_faiss_index(entries, domain)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Done! Index summary:")
    for domain in domain_entries:
        idx_path  = INDEXES_DIR / f"{domain}.index"
        json_path = INDEXES_DIR / f"{domain}.json"
        if idx_path.exists():
            idx = faiss.read_index(str(idx_path))
            print(f"  {domain:15} {idx.ntotal:>5} vectors  →  {idx_path}")
        else:
            print(f"  {domain:15} FAILED — no index file")

    print("\nRun 'python app.py' to start the backend.")
    print("=" * 60)


if __name__ == "__main__":
    main()
