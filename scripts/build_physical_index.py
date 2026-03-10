import json, os, faiss, numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')  # 384-dim, fast, great semantic matching
print(f"✅ Loaded MiniLM model")

PHYSICAL_FILES = [
    "metadata/openheritage_metadata.json",
    "metadata/culture3d_metadata.json",
    "metadata/highfidelity_metadata.json",
    "metadata/agirculrture_metadata.json",
    "metadata/env_models.json",
]

all_models = []

for filepath in PHYSICAL_FILES:
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
                keywords = m.get("keywords", "")
                country  = m.get("country", "")
                category = m.get("category", "") or m.get("type", "")

                embed_text = f"{name}. {desc}. {tags} {keywords} {country} {category}".strip()[:300]
                if not embed_text:
                    embed_text = "unknown physical object"

                m["embed_text"]     = embed_text
                m["source_file"]    = filepath
                m["original_index"] = i
                all_models.append(m)

            print(f"✅ Loaded {len(models)} models from {filepath}")
        except Exception as e:
            print(f"❌ Error in {filepath}: {e}")

# Objaverse physical
with open("metadata/objaverse_phy.jsonl", "r", encoding="utf-8") as f:
    count = 0
    for i, line in enumerate(f):
        try:
            m = json.loads(line.strip())
            name = m.get("name", "") or m.get("title", "")
            desc = m.get("description", "")
            tags = " ".join(m.get("tags", []) if isinstance(m.get("tags"), list) else [])
            embed_text = f"{name}. {desc}. {tags}".strip()[:300]
            if not embed_text:
                embed_text = "unknown physical object"
            m["embed_text"]     = embed_text
            m["source_file"]    = "objaverse_phy"
            m["original_index"] = i
            all_models.append(m)
            count += 1
        except: continue
print(f"✅ Loaded {count} entries from objaverse_phy.jsonl")

print(f"\n📦 Total physical models: {len(all_models)}")

texts = [m["embed_text"] for m in all_models]
print("🔄 Generating MiniLM embeddings...")
embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True, batch_size=128)
embeddings = np.array(embeddings).astype(np.float32)

norms = np.linalg.norm(embeddings, axis=1)
print(f"✅ Norm check — mean: {norms.mean():.4f}, min: {norms.min():.4f}, max: {norms.max():.4f}")

dimension = embeddings.shape[1]  # 384
print(f"📐 Embedding dimension: {dimension}")
index = faiss.IndexFlatIP(dimension)
index.add(embeddings)

os.makedirs("indexes", exist_ok=True)
faiss.write_index(index, "indexes/physical.index")
with open("indexes/physical.json", "w", encoding="utf-8") as f:
    json.dump(all_models, f, indent=2, ensure_ascii=False)

print(f"\n✅ Saved:")
print(f"   indexes/physical.index  ({index.ntotal} vectors, dim={dimension})")
print(f"   indexes/physical.json   ({len(all_models)} models)")