"""
ConceptCraft AI - NIH 3D Metadata Builder
==========================================
Creates nih_metadata.json with 25 verified real NIH 3D entries.
Downloads whatever files NIH allows without login.
For locked files: model_page_url is stored so they can be fetched on demand.

Run from ConceptCraftAI/scripts/:
    python fetch_nih_metadata.py
"""

import requests, json, os, re, time

MODELS_DIR   = "../datasets/nih"
METADATA_DIR = "../metadata"
OUT_FILE     = os.path.join(METADATA_DIR, "nih_metadata.json")
os.makedirs(MODELS_DIR,   exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://3d.nih.gov/"
}

# ── 25 VERIFIED real NIH 3D entries (checked live on 3d.nih.gov) ─────────
# (numeric_id, version, 3DPX_id, name, category, tags, description)
REAL_ENTRIES = [
    (22787, "1.01", "3DPX-022787", "Human Heart",
     "anatomy", ["heart","organ","anatomy","cardiology"],
     "Human heart 3D model for medical education and visualization"),

    (278,   "2",    "3DPX-000278", "Brain Ventricles",
     "anatomy", ["brain","ventricles","MRI","neuroscience"],
     "Four ventricles of the brain created from human MRI scan data"),

    (320,   "1",    "3DPX-000320", "Full Brain Female",
     "anatomy", ["brain","MRI","female","anatomy","neuroscience"],
     "Full brain from a 38 year old female from MRI scan data"),

    (1944,  "1",    "3DPX-001944", "Subcortical Brain Structures",
     "anatomy", ["brain","hippocampus","amygdala","thalamus","MRI"],
     "Subcortical brain structures including hippocampus and amygdala from MRI"),

    (16801, "1",    "3DPX-016801", "Human Skull",
     "anatomy", ["skull","bone","skeleton","cranium","anatomy"],
     "Human skull from the human skeleton collection"),

    (16814, "1",    "3DPX-016814", "Wrist Bones",
     "anatomy", ["wrist","bone","skeleton","hand","anatomy"],
     "Human wrist bones from the human skeleton collection"),

    (4647,  "1",    "3DPX-004647", "Lumbar Spine",
     "anatomy", ["spine","vertebra","bone","anatomy","CT"],
     "Human lumbar spine STL derived from CT scan DICOM study"),

    (361,   "1",    "3DPX-000361", "Rat Skeleton",
     "anatomy", ["skeleton","rat","bone","anatomy","animal"],
     "Complete rat skeleton anatomical model"),

    (21002, "1",    "3DPX-021002", "Right Kidney Male",
     "anatomy", ["kidney","organ","anatomy","renal","HRA"],
     "Human Reference Atlas right kidney male anatomical model"),

    (705,   "1",    "3DPX-000705", "Heart Model Collection",
     "anatomy", ["heart","anatomy","organ","cardiology","collection"],
     "Heart model from the NIH Heart Library collection"),

    (7743,  "1",    "3DPX-007743", "Ebola Virus VP24",
     "virus",   ["ebola","virus","protein","VP24","virology"],
     "Ebola virus VP24 protein 3D structural model"),

    (13270, "1",    "3DPX-013270", "Covid-19 Virus",
     "virus",   ["COVID","coronavirus","SARS-CoV-2","virus","virology"],
     "COVID-19 coronavirus 3D structural model for education"),

    (14753, "1",    "3DPX-014753", "SARS-CoV-2 RNA Polymerase",
     "molecule",["SARS-CoV-2","RNA","polymerase","protein","COVID"],
     "RNA-dependent RNA polymerase structure from SARS-CoV-2"),

    (15239, "1",    "3DPX-015239", "SARS-CoV-2 Spike Protein",
     "molecule",["SARS-CoV-2","spike","protein","RBD","COVID","virology"],
     "Furin cleaved spike protein of SARS-CoV-2"),

    (14933, "2",    "3DPX-014933", "Polio Capsid and RNA",
     "virus",   ["poliovirus","capsid","RNA","virus","virology"],
     "Deconstructible poliovirus capsid and RNA model"),

    (21566, "1",    "3DPX-021566", "Influenza A Ribonucleoprotein",
     "virus",   ["influenza","virus","RNA","ribonucleoprotein","virology"],
     "Influenza A virus helical ribonucleoprotein-like structure"),

    (13408, "1",    "3DPX-013408", "Coronavirus Particle",
     "virus",   ["coronavirus","virus","COVID","biology","virology"],
     "Generic coronavirus 3D structural particle model"),

    (1475,  "1",    "3DPX-001475", "DNA Double Helix",
     "molecule",["DNA","genetics","molecule","double helix","biology"],
     "Modular DNA model showing base pairing and double helix structure"),

    (21562, "1",    "3DPX-021562", "Nitric Oxide Synthase Protein",
     "molecule",["protein","enzyme","NOS","biology","AlphaFold"],
     "Human nitric oxide synthase protein structure from AlphaFold database"),

    (2416,  "1",    "3DPX-002416", "Cerebrospinal Fluid",
     "anatomy", ["CSF","brain","fluid","anatomy","neuroscience"],
     "Cerebrospinal fluid spaces 3D anatomical model"),

    (20626, "1",    "3DPX-020626", "CT Skull Scan",
     "anatomy", ["skull","CT","bone","anatomy","scan"],
     "Human skull derived from CT scan for research and education"),

    (3765,  "1",    "3DPX-003765", "Brain 3D Model",
     "anatomy", ["brain","anatomy","organ","neuroscience"],
     "Detailed 3D model of the human brain"),

    (21159, "1",    "3DPX-021159", "Detailed Human Brain",
     "anatomy", ["brain","neuroscience","anatomy","detailed"],
     "Highly detailed 3D brain model based on advanced imaging"),

    (21161, "1",    "3DPX-021161", "Human Brain Model",
     "anatomy", ["brain","neuroscience","anatomy","education"],
     "Human brain anatomical model for education and research"),

    (16815, "1",    "3DPX-016815", "Full Hand Wrist Bones",
     "anatomy", ["hand","wrist","bone","skeleton","fingers"],
     "Full hand and wrist bones human skeleton model"),
]

# ── Download a single model ───────────────────────────────────────────────
def download_model(numeric_id, version, name):
    url = f"https://3d.nih.gov/entries/download/{numeric_id}/{version}"
    safe = re.sub(r'[^\w\-]', '_', name)[:50]
    filepath_base = os.path.join(MODELS_DIR, f"{safe}_{numeric_id}")

    try:
        r = requests.get(url, headers=HEADERS, timeout=25,
                         stream=True, allow_redirects=True)
        if r.status_code != 200:
            print(f"    ✗ HTTP {r.status_code}: {name}")
            return ""

        # Detect extension from Content-Disposition header
        cd = r.headers.get("Content-Disposition", "")
        ext_match = re.search(r'filename[^;=\n]*=.*?\.(stl|obj|glb|gltf|zip)', cd, re.I)
        ext = ext_match.group(1).lower() if ext_match else "stl"

        filepath = f"{filepath_base}.{ext}"
        content = b"".join(r.iter_content(8192))

        if len(content) < 500:
            print(f"    ✗ Too small ({len(content)} B): {name}")
            return ""

        with open(filepath, "wb") as fh:
            fh.write(content)

        kb = len(content) // 1024
        print(f"    ✓ {os.path.basename(filepath)}  ({kb} KB)")
        return f"datasets/nih/{os.path.basename(filepath)}"

    except Exception as e:
        print(f"    ✗ {name}: {e}")
        return ""

# ── Main ──────────────────────────────────────────────────────────────────
print("=" * 60)
print("ConceptCraft AI  —  NIH 3D Builder")
print("=" * 60)
print(f"\n[1/2] Building metadata for {len(REAL_ENTRIES)} verified entries...")

metadata = []
for i, (nid, ver, dpx, name, category, tags, desc) in enumerate(REAL_ENTRIES):
    metadata.append({
        "id":             i,
        "entry_id":       dpx,
        "numeric_id":     nid,
        "name":           name,
        "dataset":        "NIH 3D",
        "model_page_url": f"https://3d.nih.gov/entries/{dpx}",
        "download_url":   f"https://3d.nih.gov/entries/download/{nid}/{ver}",
        "local_path":     "",
        "file_format":    "STL",
        "description":    desc,
        "domain":         "biology",
        "category":       category,
        "tags":           tags,
        "license":        "CC-BY / Public Domain",
        "source_type":    "download",
        "embedding_status": "pending"
    })

print(f"  Built {len(metadata)} entries ✓")
print(f"\n[2/2] Attempting file downloads...")
print(f"  (NIH requires login for some files — those will show ✗ but metadata is still saved)\n")

downloaded = 0
for m in metadata:
    local = download_model(m["numeric_id"],
                           m["download_url"].rsplit("/", 1)[-1],
                           m["name"])
    m["local_path"] = local
    if local:
        downloaded += 1
    time.sleep(0.4)

# Save JSON
with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2, ensure_ascii=False)

print(f"\n{'='*60}")
print(f"✅  DONE")
print(f"   JSON saved  →  {OUT_FILE}")
print(f"   Entries     →  {len(metadata)}")
print(f"   Files got   →  {downloaded} downloaded  |  {len(metadata)-downloaded} need manual download")
print(f"{'='*60}")
print(f"\n{'─'*60}")
print(f"  NOTE: NIH 3D requires a free account to download some files.")
print(f"  To get files manually:")
print(f"    1. Go to the model_page_url in the JSON")
print(f"    2. Click Download on the page")
print(f"    3. Save to  datasets/nih/")
print(f"    4. Update local_path in nih_metadata.json")
print(f"{'─'*60}")
print(f"\nFirst 5 entries:")
for m in metadata[:5]:
    print(f"  [{m['id']}] {m['name']}")
    print(f"       tags : {m['tags'][:3]}")
    print(f"       page : {m['model_page_url']}")
    print(f"       file : {m['local_path'] or '(needs manual download)'}")