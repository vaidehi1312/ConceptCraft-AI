import json, os, faiss, numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
print(f"✅ Loaded MiniLM model")

ASTRO_FILES = [
    "metadata/nasa_metadata.json",
    "metadata/nasa_science_metadata.json",
    "metadata/sketchfab_planets_metadata.json",
    "metadata/solarsystemscope_metadata.json",
]

all_models = []

for filepath in ASTRO_FILES:
    if not os.path.exists(filepath):
        print(f"⚠️  Skipping (not found): {filepath}")
        continue
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if isinstance(data, list):
                models = data
            else:
                models = data.get("models") or data.get("objects") or data.get("items") or []

            for i, m in enumerate(models):
                name     = m.get("name", "") or m.get("title", "")
                desc     = m.get("description", "")
                tags     = " ".join(m.get("tags", []) if isinstance(m.get("tags"), list) else [])
                category = m.get("category", "") or m.get("type", "")

                embed_text = f"{name}. {desc}. {tags} {category}".strip()[:300]
                if not embed_text:
                    embed_text = "unknown astronomical object"

                m["embed_text"]     = embed_text
                m["source_file"]    = filepath
                m["original_index"] = i
                all_models.append(m)

            print(f"✅ Loaded {len(models)} models from {filepath}")
        except Exception as e:
            print(f"❌ Error in {filepath}: {e}")

# Objaverse astro
with open("metadata/objaverse_astro.jsonl", "r", encoding="utf-8") as f:
    count = 0
    for i, line in enumerate(f):
        try:
            m = json.loads(line.strip())
            name = m.get("name", "") or m.get("title", "")
            desc = m.get("description", "")
            tags = " ".join(m.get("tags", []) if isinstance(m.get("tags"), list) else [])
            embed_text = f"{name}. {desc}. {tags}".strip()[:300]
            if not embed_text:
                embed_text = "unknown astronomical object"
            m["embed_text"]     = embed_text
            m["source_file"]    = "objaverse_astro"
            m["original_index"] = i
            all_models.append(m)
            count += 1
        except: continue
print(f"✅ Loaded {count} entries from objaverse_astro.jsonl")

print(f"\n📦 Total astronomical models: {len(all_models)}")

texts = [m["embed_text"] for m in all_models]
print("🔄 Generating MiniLM embeddings...")
embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True, batch_size=128)
embeddings = np.array(embeddings).astype(np.float32)

norms = np.linalg.norm(embeddings, axis=1)
print(f"✅ Norm check — mean: {norms.mean():.4f}, min: {norms.min():.4f}, max: {norms.max():.4f}")

dimension = embeddings.shape[1]
print(f"📐 Embedding dimension: {dimension}")
index = faiss.IndexFlatIP(dimension)
index.add(embeddings)

os.makedirs("indexes", exist_ok=True)
faiss.write_index(index, "indexes/astronomical.index")
with open("indexes/astronomical.json", "w", encoding="utf-8") as f:
    json.dump(all_models, f, indent=2, ensure_ascii=False)

print(f"\n✅ Saved:")
print(f"   indexes/astronomical.index  ({index.ntotal} vectors, dim={dimension})")
print(f"   indexes/astronomical.json   ({len(all_models)} models)")