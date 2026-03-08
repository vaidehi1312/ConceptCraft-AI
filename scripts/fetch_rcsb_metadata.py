"""
ConceptCraft AI - RCSB Protein Data Bank
=========================================
TWO modes:
  1. BUILD MODE (run this script): Creates rcsb_metadata.json with
     200,000+ proteins accessible via URL — no local download needed.
     Optionally caches a few locally.

  2. QUERY MODE (used by your backend at runtime):
     User searches "insulin" → FAISS finds PDB ID → fetch_on_demand("2ZJQ")
     → returns file content live from RCSB API.

Run from ConceptCraftAI/scripts/:
    pip install requests
    python fetch_rcsb_metadata.py
"""

import requests, json, os, re, time

MODELS_DIR   = "../datasets/rcsb"
METADATA_DIR = "../metadata"
OUT_FILE     = os.path.join(METADATA_DIR, "rcsb_metadata.json")
os.makedirs(MODELS_DIR,   exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

HEADERS = {"User-Agent": "ConceptCraftAI/1.0 (academic research)"}

# ═══════════════════════════════════════════════════════════════════════════
# PART A — CURATED INDEX  (these go into FAISS)
# 200,000+ proteins exist on RCSB. We index the most meaningful ones.
# ANY protein can be fetched on-demand using: fetch_on_demand(pdb_id)
# ═══════════════════════════════════════════════════════════════════════════

PROTEINS = [
    # ── COVID / Respiratory Viruses ────────────────────────────────────────
    ("6VXX", "SARS-CoV-2 Spike Protein",
     ["covid","spike","virus","protein","coronavirus"],
     "Prefusion structure of SARS-CoV-2 spike glycoprotein"),
    ("7BZ5", "SARS-CoV-2 RNA Polymerase",
     ["covid","RNA polymerase","virus","replication"],
     "SARS-CoV-2 RNA-dependent RNA polymerase"),
    ("6LU7", "SARS-CoV-2 Main Protease",
     ["covid","protease","enzyme","drug target"],
     "SARS-CoV-2 main protease Mpro - key drug target"),
    ("7DF3", "SARS-CoV-2 Nucleocapsid",
     ["covid","nucleocapsid","virus","RNA binding"],
     "SARS-CoV-2 nucleocapsid protein RNA binding domain"),
    ("5I08", "Zika Virus NS5",
     ["zika","virus","NS5","polymerase","flavivirus"],
     "Zika virus NS5 methyltransferase-polymerase"),
    ("6XRA", "Influenza Hemagglutinin",
     ["influenza","flu","hemagglutinin","virus"],
     "Influenza A hemagglutinin - viral surface protein"),

    # ── HIV ────────────────────────────────────────────────────────────────
    ("3J9M", "HIV Capsid",
     ["HIV","capsid","virus","AIDS","retrovirus"],
     "HIV-1 capsid protein hexamer lattice assembly"),
    ("1AID", "HIV Protease",
     ["HIV","protease","enzyme","AIDS","drug target"],
     "HIV-1 protease - primary antiviral drug target"),
    ("1RTD", "HIV Reverse Transcriptase",
     ["HIV","reverse transcriptase","replication","AIDS"],
     "HIV-1 reverse transcriptase enzyme structure"),

    # ── Blood & Oxygen Transport ───────────────────────────────────────────
    ("1HHO", "Oxyhemoglobin",
     ["hemoglobin","blood","oxygen","RBC","protein"],
     "Human oxyhemoglobin - oxygen carrying blood protein"),
    ("2HHB", "Deoxyhemoglobin",
     ["hemoglobin","blood","deoxy","heme","protein"],
     "Human deoxyhemoglobin adult structure T-state"),
    ("1MBN", "Myoglobin",
     ["myoglobin","muscle","oxygen","heme","protein"],
     "Sperm whale myoglobin - first protein structure solved by X-ray"),
    ("1HRC", "Cytochrome C",
     ["cytochrome","electron transport","mitochondria","heme"],
     "Horse heart cytochrome c - mitochondrial electron carrier"),

    # ── Brain & Neuroscience ───────────────────────────────────────────────
    ("3PBL", "Dopamine D3 Receptor",
     ["dopamine","receptor","brain","GPCR","neuroscience"],
     "Human dopamine D3 receptor - drug target for Parkinson's"),
    ("4UZI", "GABA-A Receptor",
     ["GABA","receptor","brain","inhibitory","neurotransmitter"],
     "GABA-A receptor - main inhibitory receptor in the brain"),
    ("1U19", "Rhodopsin",
     ["rhodopsin","eye","vision","GPCR","light receptor"],
     "Bovine rhodopsin - photoreceptor protein in the eye"),
    ("4LDO", "Serotonin Receptor",
     ["serotonin","receptor","brain","5-HT","GPCR"],
     "Human serotonin 5-HT2B receptor structure"),
    ("3EML", "Acetylcholine Receptor",
     ["acetylcholine","receptor","muscle","neuromuscular","synapse"],
     "Nicotinic acetylcholine receptor - neuromuscular junction"),

    # ── Immune System ──────────────────────────────────────────────────────
    ("1IGT", "IgG Antibody",
     ["antibody","immune","IgG","immunoglobulin","B-cell"],
     "Complete IgG antibody - adaptive immune system"),
    ("1DQJ", "Antibody-Antigen Complex",
     ["antibody","antigen","immune","complex","recognition"],
     "Antibody bound to lysozyme antigen - immune recognition"),
    ("2BBK", "MHC Class I",
     ["MHC","immune","T-cell","antigen presentation","HLA"],
     "MHC class I molecule presenting peptide to T-cells"),

    # ── DNA / Genetics / Gene Editing ──────────────────────────────────────
    ("1BNA", "B-form DNA Double Helix",
     ["DNA","double helix","genetics","Watson-Crick","B-form"],
     "Canonical B-form DNA double helix - Watson-Crick base pairs"),
    ("3BSX", "Nucleosome",
     ["nucleosome","DNA","histone","chromatin","epigenetics"],
     "Nucleosome core - DNA wrapped around histone proteins"),
    ("4OGJ", "CRISPR Cas9",
     ["CRISPR","Cas9","gene editing","DNA","genome engineering"],
     "CRISPR-Cas9 gene editing complex - revolutionary biotechnology"),
    ("1RNA", "Transfer RNA",
     ["tRNA","RNA","translation","ribosome","genetics"],
     "Yeast phenylalanine tRNA - adapter molecule in protein synthesis"),

    # ── Molecular Machines ─────────────────────────────────────────────────
    ("3J3Y", "80S Ribosome",
     ["ribosome","protein synthesis","RNA","molecular machine","translation"],
     "Complete 80S eukaryotic ribosome - the cell's protein factory"),
    ("1FNT", "ATP Synthase F1",
     ["ATP synthase","energy","mitochondria","motor protein","rotary"],
     "F1 ATP synthase - rotary molecular motor making ATP"),
    ("1AON", "GroEL Chaperonin",
     ["chaperone","protein folding","GroEL","HSP60","molecular machine"],
     "GroEL chaperonin - molecular machine assisting protein folding"),
    ("1TUB", "Tubulin Dimer",
     ["tubulin","cytoskeleton","microtubule","cell division","mitosis"],
     "Alpha-beta tubulin dimer - microtubule building block"),

    # ── Hormones & Signaling ───────────────────────────────────────────────
    ("2ZJQ", "Insulin",
     ["insulin","hormone","diabetes","pancreas","blood sugar"],
     "Human insulin - blood glucose regulation hormone"),
    ("4INS", "Insulin Hexamer",
     ["insulin","hexamer","zinc","diabetes","storage form"],
     "Insulin hexamer with zinc - storage form in pancreas"),
    ("1GZM", "Human Growth Hormone",
     ["growth hormone","HGH","pituitary","development","signaling"],
     "Human growth hormone - pituitary gland peptide hormone"),
    ("1EFU", "Adrenaline Receptor",
     ["adrenaline","epinephrine","receptor","GPCR","fight or flight"],
     "Beta-2 adrenergic receptor - adrenaline fight-or-flight response"),

    # ── Classic / Educational Proteins ─────────────────────────────────────
    ("1LYZ", "Lysozyme",
     ["lysozyme","enzyme","antibacterial","tears","egg white"],
     "Hen egg-white lysozyme - classic enzyme structure, antibacterial"),
    ("1UBQ", "Ubiquitin",
     ["ubiquitin","protein degradation","proteasome","cell","tag"],
     "Human ubiquitin - protein tagging for degradation"),
    ("1CRN", "Crambin",
     ["crambin","plant protein","small protein","hydrophobic"],
     "Crambin - one of the smallest known protein structures"),
    ("1ATP", "Protein Kinase A",
     ["kinase","phosphorylation","signaling","enzyme","PKA"],
     "cAMP-dependent protein kinase A - cell signaling enzyme"),
    ("1GFL", "Green Fluorescent Protein GFP",
     ["GFP","fluorescent","imaging","reporter","bioluminescence"],
     "Green fluorescent protein - revolutionary biological imaging tool"),
    ("1YCR", "p53 Tumor Suppressor",
     ["p53","cancer","tumor suppressor","DNA repair","apoptosis"],
     "p53 tumor suppressor protein - guardian of the genome"),
    ("2SRC", "Src Kinase",
     ["src","kinase","cancer","signaling","oncogene"],
     "Src tyrosine kinase - proto-oncogene involved in cancer"),
    ("1A3N", "Collagen Triple Helix",
     ["collagen","extracellular matrix","connective tissue","triple helix"],
     "Collagen triple helix - most abundant protein in the human body"),
]

# ═══════════════════════════════════════════════════════════════════════════
# PART B — ON-DEMAND FETCHER  (your backend uses this at query time)
# This function is what your Flask/FastAPI backend calls when a user
# searches for a protein and FAISS returns a PDB ID.
# ═══════════════════════════════════════════════════════════════════════════

def fetch_on_demand(pdb_id, fmt="pdb"):
    """
    Fetch any protein structure on-demand from RCSB.
    Call this from your backend when a user query matches a protein.

    Supports:  fmt = 'pdb' | 'cif' | 'mmtf'
    Returns:   file content as bytes, or None on failure.

    Example usage in your Flask backend:
        content = fetch_on_demand("6VXX")   # SARS-CoV-2 spike
        # send content to frontend viewer
    """
    urls = {
        "pdb":  f"https://files.rcsb.org/download/{pdb_id}.pdb",
        "cif":  f"https://files.rcsb.org/download/{pdb_id}.cif",
        "mmtf": f"https://mmtf.rcsb.org/v1.0/full/{pdb_id}",
    }
    url = urls.get(fmt, urls["pdb"])
    r = requests.get(url, timeout=15)
    if r.status_code == 200:
        return r.content
    return None

def fetch_pdb_info(pdb_id):
    """Get full metadata for any PDB entry on demand."""
    r = requests.get(f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}",
                     headers=HEADERS, timeout=10)
    if r.status_code == 200:
        return r.json()
    return {}

# ═══════════════════════════════════════════════════════════════════════════
# BUILD: Download curated proteins + save metadata JSON
# ═══════════════════════════════════════════════════════════════════════════

def download_pdb(pdb_id, name):
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    safe = re.sub(r'[^\w]', '_', name)[:40]
    filepath = os.path.join(MODELS_DIR, f"{pdb_id}_{safe}.pdb")
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        print(f"    ↩  {pdb_id} already cached")
        return f"datasets/rcsb/{os.path.basename(filepath)}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200 and len(r.content) > 1000:
            with open(filepath, "wb") as f:
                f.write(r.content)
            print(f"    ✓  {pdb_id}  ({len(r.content)//1024} KB)  {name}")
            return f"datasets/rcsb/{os.path.basename(filepath)}"
        else:
            print(f"    ✗  HTTP {r.status_code}: {pdb_id}")
    except Exception as e:
        print(f"    ✗  {pdb_id}: {e}")
    return ""

print("=" * 60)
print("ConceptCraft AI  —  RCSB Protein Data Bank")
print("=" * 60)
print(f"\n  Indexing {len(PROTEINS)} curated proteins")
print("  + RCSB has 200,000+ proteins accessible on-demand via API\n")

print("[1/2] Downloading PDB files locally (optional cache)...")
metadata = []
for i, (pdb_id, name, tags, desc) in enumerate(PROTEINS):
    local = download_pdb(pdb_id, name)
    metadata.append({
        "id":             i,
        "pdb_id":         pdb_id,
        "name":           name,
        "dataset":        "RCSB PDB",
        "model_page_url": f"https://www.rcsb.org/structure/{pdb_id}",
        "download_url":   f"https://files.rcsb.org/download/{pdb_id}.pdb",
        "local_path":     local,
        "file_format":    "PDB",
        "description":    desc,
        "domain":         "biology",
        "category":       "protein",
        "tags":           tags,
        "license":        "CC0 Public Domain",
        "source_type":    "api",
        # Key field: backend calls fetch_on_demand(pdb_id) at query time
        "on_demand":      True,
        "embedding_status": "pending"
    })
    time.sleep(0.15)

downloaded = sum(1 for m in metadata if m["local_path"])

with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2, ensure_ascii=False)

print(f"\n[2/2] Saved metadata JSON")
print(f"\n{'='*60}")
print(f"✅  DONE")
print(f"   JSON        →  {OUT_FILE}")
print(f"   Entries     →  {len(metadata)}")
print(f"   Cached PDBs →  {downloaded} files in datasets/rcsb/")
print(f"   On-demand   →  ALL 200,000+ RCSB proteins accessible via API")
print(f"{'='*60}")
print("""
HOW ON-DEMAND ACCESS WORKS IN YOUR BACKEND:
─────────────────────────────────────────────
  User query: "dopamine receptor"
       ↓
  FAISS returns pdb_id = "3PBL"
       ↓
  Backend calls:
    content = fetch_on_demand("3PBL")
       ↓
  Sends .pdb bytes to Three.js viewer
  (no pre-download needed)
─────────────────────────────────────────────
""")
print("First 5 entries:")
for m in metadata[:5]:
    print(f"  [{m['id']}] {m['pdb_id']}  {m['name']}")
    print(f"       tags   : {m['tags'][:3]}")
    print(f"       local  : {m['local_path'] or '(on-demand only)'}")
    print(f"       url    : {m['download_url']}")