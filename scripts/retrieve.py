import json, os, faiss, numpy as np
from sentence_transformers import SentenceTransformer
from transformers import CLIPProcessor, CLIPModel
import torch
import requests
from PIL import Image
from io import BytesIO

# ── Load Models ───────────────────────────────────────────
minilm = SentenceTransformer('all-MiniLM-L6-v2')

device = "cuda" if torch.cuda.is_available() else "cpu"
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
print(f"✅ Models loaded | device: {device}")

# ── Load FAISS Indexes + Metadata ─────────────────────────
DOMAINS = ["physical", "biological", "astronomical", "chemical"]

indexes  = {}
metadata = {}

for domain in DOMAINS:
    index_path = f"indexes/{domain}.index"
    json_path  = f"indexes/{domain}.json"
    if os.path.exists(index_path) and os.path.exists(json_path):
        indexes[domain]  = faiss.read_index(index_path)
        with open(json_path, "r", encoding="utf-8") as f:
            metadata[domain] = json.load(f)
        print(f"✅ Loaded {domain}: {indexes[domain].ntotal} vectors")
    else:
        print(f"⚠️  Skipping {domain} (files not found)")

# ── CLIP Image Embedding ──────────────────────────────────
def get_clip_image_embedding(url):
    try:
        response = requests.get(url, timeout=5)
        image = Image.open(BytesIO(response.content)).convert("RGB")
        inputs = clip_processor(images=image, return_tensors="pt").to(device)
        with torch.no_grad():
            emb = clip_model.get_image_features(**inputs)
            emb = emb / emb.norm(dim=-1, keepdim=True)
        return emb.cpu().numpy().astype(np.float32)
    except:
        return None

def get_clip_text_embedding(text):
    inputs = clip_processor(
        text=[text], return_tensors="pt",
        padding=True, truncation=True, max_length=77
    ).to(device)
    with torch.no_grad():
        emb = clip_model.get_text_features(**inputs)
        emb = emb / emb.norm(dim=-1, keepdim=True)
    return emb.cpu().numpy().astype(np.float32)

# ── Main Retrieve Function ────────────────────────────────
def retrieve(query, domain, top_k=10):
    domain = domain.lower()

    if domain not in indexes:
        print(f"❌ Domain '{domain}' not loaded")
        return []

    # Step 3: Embed query using MiniLM
    query_embedding = minilm.encode([query], normalize_embeddings=True)
    query_embedding = np.array(query_embedding).astype(np.float32)

    # Step 4: L2-normalize (already done by normalize_embeddings=True)
    norm = np.linalg.norm(query_embedding)
    print(f"🔍 Query norm: {norm:.4f} (should be ~1.0)")

    # Step 5: Search FAISS index
    scores, indices = indexes[domain].search(query_embedding, top_k)
    print(f"📊 Top {top_k} FAISS results from '{domain}' index")

    # Step 6: Fetch model metadata using returned indices
    candidates = []
    for rank, (idx, score) in enumerate(zip(indices[0], scores[0])):
        if idx == -1:
            continue
        model = metadata[domain][idx].copy()
        model["faiss_score"] = float(score)
        model["faiss_rank"]  = rank + 1
        candidates.append(model)

    # Step 7: CLIP reranking using thumbnails
    print(f"🖼️  Reranking with CLIP...")
    query_clip_emb = get_clip_text_embedding(query)

    for m in candidates:
        thumbnail = m.get("thumbnail") or m.get("thumbnail_url") or m.get("image_url") or ""
        if thumbnail:
            img_emb = get_clip_image_embedding(thumbnail)
            if img_emb is not None:
                clip_score = float(np.dot(query_clip_emb.flatten(), img_emb.flatten()))
                m["clip_score"] = clip_score
            else:
                m["clip_score"] = m["faiss_score"]  # fallback
        else:
            m["clip_score"] = m["faiss_score"]  # fallback

    # Final score: weighted combination
    for m in candidates:
        m["final_score"] = round(0.5 * m["faiss_score"] + 0.5 * m["clip_score"], 4)

    # Sort by final score
    candidates.sort(key=lambda x: x["final_score"], reverse=True)

    # Step 8: Return top results
    return candidates[:5]


# ── Pretty Print Results ──────────────────────────────────
def print_results(results):
    if not results:
        print("❌ No results found")
        return
    print(f"\n{'='*60}")
    for i, m in enumerate(results):
        print(f"\n🏆 Rank {i+1}")
        print(f"   Name        : {m.get('name') or m.get('title', 'N/A')}")
        print(f"   Description : {str(m.get('description', ''))[:100]}...")
        print(f"   URL         : {m.get('url') or m.get('model_url') or m.get('sketchfab_url', 'N/A')}")
        print(f"   Thumbnail   : {m.get('thumbnail') or m.get('thumbnail_url', 'N/A')}")
        print(f"   FAISS Score : {m.get('faiss_score', 0):.4f}")
        print(f"   CLIP Score  : {m.get('clip_score', 0):.4f}")
        print(f"   Final Score : {m.get('final_score', 0):.4f}")
    print(f"\n{'='*60}")


# ── Test Queries ──────────────────────────────────────────
if __name__ == "__main__":
    test_queries = [
        ("horse",           "biological"),
        ("pyramid egypt",   "physical"),
        ("wheat crop",      "physical"),
        ("mars planet",     "astronomical"),
        ("water molecule",  "chemical"),
    ]

    for query, domain in test_queries:
        print(f"\n🔎 Query: '{query}' | Domain: '{domain}'")
        results = retrieve(query, domain, top_k=10)
        print_results(results)