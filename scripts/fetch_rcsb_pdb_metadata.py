"""
fetch_rcsb_pdb_metadata.py
---------------------------
Scrapes RCSB PDB metadata for FAISS indexing — NO local file downloads.

STRATEGY:
  1. Use RCSB Search API to get PDB IDs across curated categories
     (proteins, enzymes, nucleic acids, protein-ligand complexes, viruses, etc.)
  2. Use RCSB Data API (GraphQL, batched) to fetch rich metadata per PDB ID:
       title, description, organism, keywords, resolution, method,
       molecule type, polymer count, ligand names, release date
  3. Build embed_url and fetch_url for each entry (no download, on-demand render)
  4. Write rich faiss_text field for embedding generation

APIs used (all free, no auth):
  Search: https://search.rcsb.org/rcsbsearch/v2/query
  Data:   https://data.rcsb.org/graphql
  Embed:  https://3dmol.csb.pitt.edu/viewer.html?pdb=<ID>
  Fetch:  https://files.rcsb.org/download/<ID>.pdb  (only called at render time)

Run:
  pip install requests
  python fetch_rcsb_pdb_metadata.py

Output:
  metadata/rcsb_pdb_metadata.json  (~2000 entries, ~5MB, no 3D files)
"""

import json
import os
import time
import requests

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
SEARCH_URL  = "https://search.rcsb.org/rcsbsearch/v2/query"
GRAPHQL_URL = "https://data.rcsb.org/graphql"
OUTPUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "metadata")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "rcsb_pdb_metadata.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# How many PDB IDs to collect per category search
IDS_PER_CATEGORY = 150
# GraphQL batch size (RCSB recommends ≤100)
BATCH_SIZE = 50
# Polite delay between API calls (seconds)
DELAY = 0.3

# ---------------------------------------------------------------------------
# SEARCH CATEGORIES
# Each entry: (label, molecule_category, search_term, polymer_type filter or None)
# We cast a wide net across all major structure types
# ---------------------------------------------------------------------------
SEARCH_CATEGORIES = [
    # ── Proteins ──────────────────────────────────────────────────────────
    ("enzyme",                  "protein",          "enzyme catalysis",         None),
    ("kinase",                  "protein",          "kinase signaling",         None),
    ("antibody",                "protein",          "antibody immunoglobulin",  None),
    ("receptor",                "protein",          "receptor transmembrane",   None),
    ("ion_channel",             "protein",          "ion channel membrane",     None),
    ("transcription_factor",    "protein",          "transcription factor DNA", None),
    ("chaperone",               "protein",          "chaperone folding",        None),
    ("protease",                "protein",          "protease cleavage",        None),
    ("membrane_protein",        "protein",          "membrane protein lipid",   None),
    ("virus_capsid",            "protein",          "virus capsid coat protein",None),
    ("motor_protein",           "protein",          "motor protein myosin kinesin", None),
    ("structural_protein",      "protein",          "collagen fibrin actin tubulin", None),
    ("hormone_protein",         "protein",          "hormone growth insulin",   None),
    ("photosynthesis",          "protein",          "photosystem chlorophyll",  None),
    ("ribosomal_protein",       "protein",          "ribosomal protein translation", None),
    # ── Nucleic Acids ─────────────────────────────────────────────────────
    ("dna_structure",           "nucleic_acid",     "DNA double helix B-form",  None),
    ("rna_riboswitch",          "nucleic_acid",     "riboswitch RNA aptamer",   None),
    ("trna",                    "nucleic_acid",     "transfer RNA tRNA",        None),
    ("mrna",                    "nucleic_acid",     "mRNA messenger RNA",       None),
    ("ribozyme",                "nucleic_acid",     "ribozyme catalytic RNA",   None),
    ("dna_repair",              "nucleic_acid",     "DNA repair helicase",      None),
    # ── Protein–Nucleic Acid Complexes ────────────────────────────────────
    ("dna_protein_complex",     "protein_dna",      "protein DNA complex transcription", None),
    ("rna_protein_complex",     "protein_rna",      "RNA protein complex splicing", None),
    ("nucleosome",              "protein_dna",      "nucleosome histone",       None),
    ("crispr",                  "protein_dna",      "CRISPR Cas9 guide RNA",    None),
    # ── Protein–Ligand Complexes (Drug Targets) ───────────────────────────
    ("drug_target_kinase",      "protein_ligand",   "kinase inhibitor drug",    None),
    ("drug_target_protease",    "protein_ligand",   "protease inhibitor drug",  None),
    ("drug_target_gpcr",        "protein_ligand",   "GPCR agonist antagonist",  None),
    ("drug_target_nuclear",     "protein_ligand",   "nuclear receptor ligand",  None),
    ("antibiotic_target",       "protein_ligand",   "antibiotic resistance target", None),
    ("antiviral_target",        "protein_ligand",   "antiviral drug viral protein", None),
    # ── Carbohydrates / Glycoproteins ─────────────────────────────────────
    ("glycoprotein",            "glycoprotein",     "glycoprotein glycan sugar", None),
    ("polysaccharide",          "carbohydrate",     "polysaccharide cellulose starch", None),
    # ── Large Assemblies ──────────────────────────────────────────────────
    ("ribosome",                "large_assembly",   "ribosome 70S 80S",         None),
    ("proteasome",              "large_assembly",   "proteasome ubiquitin",     None),
    ("virus_structure",         "virus",            "virus structure capsid assembly", None),
    ("atp_synthase",            "large_assembly",   "ATP synthase F1 rotary",   None),
    # ── AlphaFold / Computed ──────────────────────────────────────────────
    ("alphafold_human",         "computed_model",   "AlphaFold human protein",  None),
]

# ---------------------------------------------------------------------------
# STEP 1: SEARCH API — get PDB IDs per category
# ---------------------------------------------------------------------------
def search_pdb_ids(search_term: str, max_rows: int = IDS_PER_CATEGORY) -> list[str]:
    """Full-text search across all PDB fields, returns list of PDB IDs."""
    payload = {
        "query": {
            "type": "terminal",
            "service": "full_text",
            "parameters": {"value": search_term}
        },
        "request_options": {
            "paginate": {"start": 0, "rows": max_rows},
            "sort": [{"sort_by": "score", "direction": "desc"}],
            "results_content_type": ["experimental"]
        },
        "return_type": "entry"
    }
    try:
        r = requests.post(SEARCH_URL, json=payload, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return [hit["identifier"] for hit in data.get("result_set", [])]
        elif r.status_code == 204:
            return []  # no results
        else:
            print(f"    [WARN] Search returned {r.status_code} for '{search_term}'")
            return []
    except Exception as e:
        print(f"    [ERROR] Search failed for '{search_term}': {e}")
        return []


# ---------------------------------------------------------------------------
# STEP 2: GRAPHQL DATA API — batch fetch rich metadata
# ---------------------------------------------------------------------------
GRAPHQL_QUERY = """
query fetchEntries($ids: [String!]!) {
  entries(entry_ids: $ids) {
    rcsb_id
    struct {
      title
      pdbx_descriptor
    }
    struct_keywords {
      pdbx_keywords
      text
    }
    rcsb_entry_info {
      resolution_combined
      experimental_method
      polymer_entity_count_protein
      polymer_entity_count_nucleic_acid
      polymer_entity_count_DNA
      polymer_entity_count_RNA
      nonpolymer_entity_count
      molecular_weight
      deposited_atom_count
      assembly_count
    }
    rcsb_accession_info {
      deposit_date
      initial_release_date
      revision_date
    }
    polymer_entities {
      rcsb_entity_source_organism {
        scientific_name
        common_name
        ncbi_taxonomy_id
      }
      entity_poly {
        type
        pdbx_seq_one_letter_code_can
        rcsb_sample_sequence_length
      }
      rcsb_polymer_entity {
        pdbx_description
        pdbx_fragment
        pdbx_mutation
        pdbx_ec
      }
    }
    nonpolymer_entities {
      nonpolymer_comp {
        chem_comp {
          id
          name
          type
          formula
          formula_weight
        }
        rcsb_chem_comp_info {
          initial_release_date
        }
      }
    }
  }
}
"""

def fetch_metadata_batch(pdb_ids: list[str]) -> list[dict]:
    """Fetch rich metadata for a batch of PDB IDs via GraphQL."""
    try:
        r = requests.post(
            GRAPHQL_URL,
            json={"query": GRAPHQL_QUERY, "variables": {"ids": pdb_ids}},
            timeout=30
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("data", {}).get("entries", []) or []
        else:
            print(f"    [WARN] GraphQL returned {r.status_code}")
            return []
    except Exception as e:
        print(f"    [ERROR] GraphQL batch failed: {e}")
        return []


# ---------------------------------------------------------------------------
# STEP 3: TRANSFORM raw GraphQL entry → clean metadata dict
# ---------------------------------------------------------------------------
def transform_entry(raw: dict, category_label: str, molecule_category: str) -> dict:
    """Convert raw GraphQL response into a clean, FAISS-ready metadata entry."""
    pdb_id = raw.get("rcsb_id", "")

    # Title & description
    struct = raw.get("struct") or {}
    title = struct.get("title", "")
    descriptor = struct.get("pdbx_descriptor", "") or ""

    # Keywords
    kw_block = raw.get("struct_keywords") or {}
    pdbx_keywords = kw_block.get("pdbx_keywords", "") or ""
    kw_text = kw_block.get("text", "") or ""
    keywords_combined = f"{pdbx_keywords} {kw_text}".strip()
    tags = [k.strip().lower() for k in keywords_combined.replace(",", " ").split() if len(k.strip()) > 2]
    tags = list(dict.fromkeys(tags))[:30]  # deduplicate, cap at 30

    # Entry info
    info = raw.get("rcsb_entry_info") or {}
    resolution = info.get("resolution_combined")
    if isinstance(resolution, list):
        resolution = resolution[0] if resolution else None
    exp_method = info.get("experimental_method", "") or ""
    protein_count = info.get("polymer_entity_count_protein", 0) or 0
    na_count = info.get("polymer_entity_count_nucleic_acid", 0) or 0
    dna_count = info.get("polymer_entity_count_DNA", 0) or 0
    rna_count = info.get("polymer_entity_count_RNA", 0) or 0
    ligand_count = info.get("nonpolymer_entity_count", 0) or 0
    mol_weight = info.get("molecular_weight")
    atom_count = info.get("deposited_atom_count")

    # Organism
    organisms = []
    ec_numbers = []
    chain_descriptions = []
    sequence_lengths = []
    for poly in (raw.get("polymer_entities") or []):
        for org in (poly.get("rcsb_entity_source_organism") or []):
            sci = org.get("scientific_name", "")
            common = org.get("common_name", "")
            if sci and sci not in organisms:
                organisms.append(sci)
            if common and common not in organisms:
                organisms.append(common)
        poly_entity = poly.get("rcsb_polymer_entity") or {}
        desc = poly_entity.get("pdbx_description", "")
        if desc:
            chain_descriptions.append(desc)
        ec = poly_entity.get("pdbx_ec", "")
        if ec:
            ec_numbers.append(ec)
        ep = poly.get("entity_poly") or {}
        seqlen = ep.get("rcsb_sample_sequence_length")
        if seqlen:
            sequence_lengths.append(seqlen)

    # Ligands
    ligand_names = []
    ligand_formulas = []
    for npe in (raw.get("nonpolymer_entities") or []):
        comp = (npe.get("nonpolymer_comp") or {}).get("chem_comp") or {}
        lname = comp.get("name", "")
        lform = comp.get("formula", "")
        if lname and lname not in ("HOH", "WATER") and lname not in ligand_names:
            ligand_names.append(lname)
        if lform:
            ligand_formulas.append(lform)

    # Dates
    acc = raw.get("rcsb_accession_info") or {}
    release_date = acc.get("initial_release_date", "")[:10] if acc.get("initial_release_date") else ""

    # Infer molecule_type
    if protein_count > 0 and (dna_count > 0 or rna_count > 0):
        mol_type = "protein_nucleic_acid_complex"
    elif protein_count > 0 and ligand_count > 0:
        mol_type = "protein_ligand_complex"
    elif protein_count > 0:
        mol_type = "protein"
    elif rna_count > 0:
        mol_type = "rna"
    elif dna_count > 0:
        mol_type = "dna"
    elif na_count > 0:
        mol_type = "nucleic_acid"
    else:
        mol_type = "other"

    # URLs (no download — on-demand only)
    embed_url = f"https://3dmol.csb.pitt.edu/viewer.html?pdb={pdb_id}&style=cartoon"
    fetch_url_pdb = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    fetch_url_cif = f"https://files.rcsb.org/download/{pdb_id}.cif"
    rcsb_page = f"https://www.rcsb.org/structure/{pdb_id}"

    entry = {
        "id": f"rcsb_{pdb_id.lower()}",
        "pdb_id": pdb_id,
        "name": title,
        "category": category_label,
        "molecule_category": molecule_category,
        "molecule_type": mol_type,
        "description": descriptor or title,
        "chain_descriptions": chain_descriptions[:5],
        "keywords": keywords_combined,
        "tags": tags,
        "organisms": organisms[:5],
        "ec_numbers": ec_numbers,
        "ligand_names": ligand_names[:10],
        "ligand_formulas": ligand_formulas[:10],
        "experimental_method": exp_method,
        "resolution_angstrom": resolution,
        "molecular_weight_kda": round(mol_weight / 1000, 2) if mol_weight else None,
        "deposited_atom_count": atom_count,
        "protein_chain_count": protein_count,
        "nucleic_acid_chain_count": na_count,
        "ligand_count": ligand_count,
        "sequence_lengths": sequence_lengths[:5],
        "release_date": release_date,
        # Rendering
        "source": "RCSB PDB",
        "source_type": "structure_database",
        "render_type": "molecule_viewer",
        "embed_url": embed_url,
        "fetch_url_pdb": fetch_url_pdb,
        "fetch_url_cif": fetch_url_cif,
        "rcsb_page": rcsb_page,
        "local_file": None,
        "runtime_fetch": True,
        "license": "CC-BY 4.0 (wwPDB)",
    }

    entry["faiss_text"] = build_faiss_text(entry)
    return entry


# ---------------------------------------------------------------------------
# STEP 4: FAISS TEXT BUILDER
# ---------------------------------------------------------------------------
def build_faiss_text(e: dict) -> str:
    """Generates rich embedding text — more fields = better semantic search."""
    parts = [
        f"PDB ID: {e['pdb_id']}.",
        f"Name: {e['name']}." if e['name'] else "",
        f"Molecule type: {e['molecule_type'].replace('_', ' ')}." if e['molecule_type'] else "",
        f"Category: {e['category'].replace('_', ' ')}.",
        f"Description: {e['description']}." if e['description'] else "",
    ]
    if e["chain_descriptions"]:
        parts.append("Chains: " + "; ".join(e["chain_descriptions"][:3]) + ".")
    if e["organisms"]:
        parts.append("Organism: " + ", ".join(e["organisms"][:3]) + ".")
    if e["ligand_names"]:
        parts.append("Ligands: " + ", ".join(e["ligand_names"][:5]) + ".")
    if e["ec_numbers"]:
        parts.append("EC numbers: " + ", ".join(e["ec_numbers"]) + ".")
    if e["keywords"]:
        parts.append(f"Keywords: {e['keywords']}.")
    if e["experimental_method"]:
        parts.append(f"Determined by: {e['experimental_method']}.")
    if e["resolution_angstrom"]:
        parts.append(f"Resolution: {e['resolution_angstrom']} Å.")
    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    all_ids_by_category: dict[str, tuple[str, list[str]]] = {}

    print("=" * 60)
    print("  RCSB PDB Metadata Scraper")
    print("  No local downloads — metadata only")
    print("=" * 60)

    # ── Phase 1: Collect PDB IDs ──────────────────────────────────────────
    print(f"\n[1/3] Searching PDB for IDs across {len(SEARCH_CATEGORIES)} categories...")
    all_ids_set = set()

    for label, mol_cat, search_term, _ in SEARCH_CATEGORIES:
        print(f"  Searching: '{search_term}' ({label})...", end=" ", flush=True)
        ids = search_pdb_ids(search_term, max_rows=IDS_PER_CATEGORY)
        # Deduplicate globally but keep category mapping
        new_ids = [i for i in ids if i not in all_ids_set]
        all_ids_set.update(new_ids)
        all_ids_by_category[label] = (mol_cat, new_ids)
        print(f"{len(new_ids)} new IDs (total so far: {len(all_ids_set)})")
        time.sleep(DELAY)

    total_ids = len(all_ids_set)
    print(f"\n  Total unique PDB IDs collected: {total_ids}")

    # Build flat list with category annotation for batching
    id_to_categories: dict[str, tuple[str, str]] = {}
    for label, (mol_cat, ids) in all_ids_by_category.items():
        for pid in ids:
            if pid not in id_to_categories:
                id_to_categories[pid] = (label, mol_cat)

    all_ids_list = list(id_to_categories.keys())

    # ── Phase 2: Batch fetch metadata via GraphQL ─────────────────────────
    print(f"\n[2/3] Fetching metadata for {len(all_ids_list)} entries in batches of {BATCH_SIZE}...")
    raw_entries: list[dict] = []
    batches = [all_ids_list[i:i+BATCH_SIZE] for i in range(0, len(all_ids_list), BATCH_SIZE)]

    for i, batch in enumerate(batches):
        print(f"  Batch {i+1}/{len(batches)} ({len(batch)} IDs)...", end=" ", flush=True)
        results = fetch_metadata_batch(batch)
        raw_entries.extend(results)
        print(f"got {len(results)} entries")
        time.sleep(DELAY)

    print(f"\n  Raw entries fetched: {len(raw_entries)}")

    # ── Phase 3: Transform to clean metadata ─────────────────────────────
    print(f"\n[3/3] Transforming to FAISS-ready metadata...")
    metadata = []
    seen_pdb_ids = set()

    for raw in raw_entries:
        pdb_id = raw.get("rcsb_id", "")
        if not pdb_id or pdb_id in seen_pdb_ids:
            continue
        seen_pdb_ids.add(pdb_id)

        label, mol_cat = id_to_categories.get(pdb_id, ("unknown", "unknown"))
        try:
            entry = transform_entry(raw, label, mol_cat)
            metadata.append(entry)
        except Exception as e:
            print(f"  [WARN] Failed to transform {pdb_id}: {e}")

    # ── Write output ──────────────────────────────────────────────────────
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # ── Summary ───────────────────────────────────────────────────────────
    from collections import Counter
    print(f"\n{'='*60}")
    print(f"  ✅ Written → {OUTPUT_FILE}")
    print(f"  Total entries: {len(metadata)}")
    print(f"\n  Breakdown by molecule_type:")
    mol_types = Counter(e["molecule_type"] for e in metadata)
    for mt, count in sorted(mol_types.items(), key=lambda x: -x[1]):
        print(f"    {mt:<35} {count}")
    print(f"\n  Breakdown by experimental_method:")
    methods = Counter(e["experimental_method"] for e in metadata if e["experimental_method"])
    for m, count in sorted(methods.items(), key=lambda x: -x[1])[:8]:
        print(f"    {m:<35} {count}")
    print(f"\n  Entries with ligands:      {sum(1 for e in metadata if e['ligand_count'] > 0)}")
    print(f"  Entries with organisms:    {sum(1 for e in metadata if e['organisms'])}")
    print(f"  Entries with resolution:   {sum(1 for e in metadata if e['resolution_angstrom'])}")

    print(f"""
{'='*60}
  FAISS INDEXING — HOW TO USE THIS FILE
{'='*60}
  from sentence_transformers import SentenceTransformer
  import faiss, json, numpy as np

  with open("metadata/rcsb_pdb_metadata.json") as f:
      data = json.load(f)

  texts = [e["faiss_text"] for e in data]
  model = SentenceTransformer("all-MiniLM-L6-v2")
  embeddings = model.encode(texts, show_progress_bar=True)
  embeddings = np.array(embeddings).astype("float32")

  index = faiss.IndexFlatL2(embeddings.shape[1])
  index.add(embeddings)
  faiss.write_index(index, "rcsb_pdb.index")

  # At query time:
  def search(query, k=5):
      q_vec = model.encode([query]).astype("float32")
      distances, indices = index.search(q_vec, k)
      return [data[i] for i in indices[0]]

  # Results have embed_url ready for 3Dmol.js iframe rendering:
  #   result["embed_url"]       → 3Dmol.js iframe src
  #   result["fetch_url_pdb"]   → live PDB file fetch (NGL Viewer etc.)
  #   result["rcsb_page"]       → RCSB structure page link
{'='*60}
""")


if __name__ == "__main__":
    main()
