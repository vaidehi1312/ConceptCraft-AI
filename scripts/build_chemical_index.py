import json, os, faiss, numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
print(f"✅ Loaded MiniLM model")

CHEMICAL_FILES = [
    "metadata/materialsproject_metadata.json",
    "metadata/pubchem_metadata.json",
    "metadata/openmaterial_dataset.json",
]

all_models = []

for filepath in CHEMICAL_FILES:
    if not os.path.exists(filepath):
        print(f"⚠️  Skipping (not found): {filepath}")
        continue
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if isinstance(data, list):
                models = data
            else:
                models = data.get("models") or data.get("materials") or data.get("compounds") or []

            for i, m in enumerate(models):
                name     = m.get("name", "") or m.get("title", "") or m.get("formula", "")
                desc     = m.get("description", "") or m.get("summary", "")
                tags     = " ".join(m.get("tags", []) if isinstance(m.get("tags"), list) else [])
                category = m.get("category", "") or m.get("type", "")

                embed_text = f"{name}. {desc}. {tags} {category}".strip()[:300]
                if not embed_text:
                    embed_text = "unknown chemical compound"

                m["embed_text"]     = embed_text
                m["source_file"]    = filepath
                m["original_index"] = i
                all_models.append(m)

            print(f"✅ Loaded {len(models)} models from {filepath}")
        except Exception as e:
            print(f"❌ Error in {filepath}: {e}")

print(f"\n📦 Total chemical models: {len(all_models)}")

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
faiss.write_index(index, "indexes/chemical.index")
with open("indexes/chemical.json", "w", encoding="utf-8") as f:
    json.dump(all_models, f, indent=2, ensure_ascii=False)

print(f"\n✅ Saved:")
print(f"   indexes/chemical.index  ({index.ntotal} vectors, dim={dimension})")
print(f"   indexes/chemical.json   ({len(all_models)} models)")