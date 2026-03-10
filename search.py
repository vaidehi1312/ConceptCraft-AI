"""
search.py — ConceptCraftAI
Stage 1: MiniLM (all-MiniLM-L6-v2) → FAISS → top 10 candidates
Stage 2: CrossEncoder (ms-marco-MiniLM-L-6-v2) → text relevance rerank → top 1
Stage 3: Structural comparison → weighted confidence score
Stage 4: Confidence check → accept (≥0.54) or fallback
"""

import json
import re
import numpy as np
import faiss
from pathlib import Path
from sentence_transformers import SentenceTransformer
from sentence_transformers.cross_encoder import CrossEncoder

# ── Config ────────────────────────────────────────────────────────────────────
INDEXES_DIR          = Path("indexes")
MINILM_MODEL         = "all-MiniLM-L6-v2"
CROSS_ENCODER_MODEL  = "cross-encoder/ms-marco-MiniLM-L-6-v2"
TOP_K                = 10
CONFIDENCE_THRESHOLD = 0.40
DOMAINS              = ["biological", "physical", "chemical", "astronomical"]

# ── Final score weights ───────────────────────────────────────────────────────
# Final score = cross_encoder_norm * 0.6 + structural * 0.4
CLIP_WEIGHT       = 0.6   # kept as CLIP_WEIGHT for API compatibility
STRUCTURAL_WEIGHT = 0.4

# Cross-encoder score normalization range (logits, empirically observed)
# Scores below CE_MIN are clamped to 0, above CE_MAX clamped to 1
CE_MIN = -10.0
CE_MAX =  10.0

def _normalize_ce_score(raw: float) -> float:
    """Normalize cross-encoder logit to 0.0–1.0 range."""
    return float(np.clip((raw - CE_MIN) / (CE_MAX - CE_MIN), 0.0, 1.0))

# ── Load MiniLM (always loaded at startup) ────────────────────────────────────
print(f"Loading MiniLM: {MINILM_MODEL}")
minilm = SentenceTransformer(MINILM_MODEL)
print(f"  MiniLM ready ✅")

# ── Load CrossEncoder ─────────────────────────────────────────────────────────
print(f"Loading CrossEncoder: {CROSS_ENCODER_MODEL}")
cross_encoder = CrossEncoder(CROSS_ENCODER_MODEL)
print(f"  CrossEncoder ready ✅")


# ── Load all 4 FAISS indexes + JSON catalogs ─────────────────────────────────
# Small domains (biological, physical, astronomical) load fully into RAM.
# Large domains (chemical, 38k+ entries) are parsed line-by-line to avoid
# MemoryError, storing only a lightweight offset map for on-demand access.

LARGE_DOMAIN_THRESHOLD = 10_000   # entries — above this, use offset map

indexes       = {}
catalogs      = {}   # domain → list[dict]  (small domains only)
catalog_paths = {}   # domain → Path        (large domains)
offset_maps   = {}   # domain → list[int]   (large domains)


def _parse_offset_map(json_path: Path) -> list[int]:
    """
    Build a byte-offset map by parsing the JSON array line by line.
    Works on indent=2 arrays written by json.dump — top-level entries
    are indented exactly 2 spaces, so we detect lines where indent==2
    and the content starts with '{'.
    """
    offsets = []
    with open(json_path, "rb") as f:
        pos = 0
        for raw_line in f:
            stripped = raw_line.lstrip()
            indent   = len(raw_line) - len(stripped)
            if indent == 2 and stripped.startswith(b"{"):
                offsets.append(pos)
            pos += len(raw_line)
    return offsets

def _fetch_entry(domain: str, idx: int) -> dict:
    """Read and parse a single entry from a large JSON file by offset index."""
    offset = offset_maps[domain][idx]
    with open(catalog_paths[domain], "rb") as f:
        f.seek(offset)
        depth = 0
        buf   = b""
        while True:
            byte = f.read(1)
            if not byte:
                break
            buf += byte
            if byte == b"{":
                depth += 1
            elif byte == b"}":
                depth -= 1
                if depth == 0:
                    break
    return json.loads(buf.decode("utf-8"))


for domain in DOMAINS:
    index_path = INDEXES_DIR / f"{domain}.index"
    json_path  = INDEXES_DIR / f"{domain}.json"

    if not index_path.exists() or not json_path.exists():
        print(f"  [WARN] Skipping '{domain}' — files not found")
        continue

    indexes[domain] = faiss.read_index(str(index_path))
    n_vectors       = indexes[domain].ntotal

    if n_vectors > LARGE_DOMAIN_THRESHOLD:
        # Large domain — build offset map, don't load into RAM
        catalog_paths[domain] = json_path
        print(f"  Building offset map for '{domain}' (large: {n_vectors} vectors)...")
        offset_maps[domain] = _parse_offset_map(json_path)
        n_entries = len(offset_maps[domain])
    else:
        # Small domain — load fully into RAM
        with open(json_path, encoding="utf-8") as f:
            catalogs[domain] = json.load(f)
        n_entries = len(catalogs[domain])

    print(f"  Loaded '{domain}': {n_vectors} vectors, {n_entries} entries, dim={indexes[domain].d}")

print(f"\nReady. Domains: {list(indexes.keys())}\n")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1 — MiniLM + FAISS
# ══════════════════════════════════════════════════════════════════════════════
def stage1_faiss_search(query: str, domain: str, top_k: int = TOP_K) -> list[dict]:
    """
    Embed query with MiniLM → search FAISS index → return top_k candidates.

    Returns list of:
        { faiss_score, clip_score, structural_score, final_score, model }
    """
    domain = domain.lower()
    if domain not in indexes:
        raise ValueError(f"Domain '{domain}' not loaded. Available: {list(indexes.keys())}")

    query_vec = minilm.encode([query], convert_to_numpy=True).astype(np.float32)
    faiss.normalize_L2(query_vec)

    scores, indices = indexes[domain].search(query_vec, top_k)

    results = []
    use_offset = domain in offset_maps
    max_idx    = (len(offset_maps[domain]) if use_offset else len(catalogs[domain])) - 1

    for score, idx in zip(scores[0], indices[0]):
        i = int(idx)
        if i == -1 or i > max_idx:
            continue
        model_entry = _fetch_entry(domain, i) if use_offset else catalogs[domain][i]
        results.append({
            "faiss_score":      float(score),
            "clip_score":       float(score),   # will be overwritten in stage 2
            "structural_score": 0.0,
            "final_score":      float(score),
            "model":            model_entry
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2 — CrossEncoder reranking (replaces CLIP)
# ══════════════════════════════════════════════════════════════════════════════
def stage2_cross_encoder_rerank(query: str, candidates: list[dict]) -> list[dict]:
    """
    CrossEncoder reranking: scores (query, embed_text) pairs directly.
    No images needed — pure text relevance matching.
    clip_score key is reused for API response compatibility.

    Returns candidates sorted by cross-encoder score descending.
    """
    if not candidates:
        return candidates

    # Build (query, document_text) pairs
    pairs = [
        (query, c["model"].get("embed_text") or c["model"].get("name") or "")
        for c in candidates
    ]

    # Get raw logit scores from cross-encoder
    raw_scores = cross_encoder.predict(pairs)

    # Normalize to 0.0–1.0 and store as clip_score for API compatibility
    for c, raw in zip(candidates, raw_scores):
        c["clip_score"] = _normalize_ce_score(float(raw))

    # Sort best first
    return sorted(candidates, key=lambda x: x["clip_score"], reverse=True)


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3 — Structural comparison (applied to top 1 candidate only)
# ══════════════════════════════════════════════════════════════════════════════

def _tokenize(text: str) -> set[str]:
    """Lowercase, strip punctuation, split into word tokens."""
    return set(re.findall(r'\b[a-z0-9]+\b', text.lower()))


def _tag_overlap(query_tokens: set[str], model: dict) -> float:
    """Fraction of query tokens found in model tags. Returns 0.0–1.0."""
    tags = model.get("tags") or []
    if not tags:
        return 0.0
    tag_tokens = set()
    for tag in tags:
        tag_tokens.update(_tokenize(str(tag)))
    if not query_tokens:
        return 0.0
    return min(len(query_tokens & tag_tokens) / len(query_tokens), 1.0)


def _category_match(query_tokens: set[str], model: dict) -> float:
    """Check if query tokens appear in category or domain fields. Returns 0.0 or 1.0."""
    combined = (
        _tokenize(str(model.get("category") or "")) |
        _tokenize(str(model.get("domain")   or ""))
    )
    return 1.0 if query_tokens & combined else 0.0


def _name_overlap(query_tokens: set[str], model: dict) -> float:
    """Token overlap between query and model name. Returns 0.0–1.0."""
    name_tokens = _tokenize(str(model.get("name") or ""))
    if not query_tokens or not name_tokens:
        return 0.0
    return min(len(query_tokens & name_tokens) / len(query_tokens), 1.0)


def _format_bonus(model: dict) -> float:
    """
    Bonus if model has viewable/embeddable formats.
    Returns 0.0, 0.25, or 0.5.
    """
    embed_url = model.get("embed_url") or model.get("url") or ""
    formats   = {str(f).upper() for f in (model.get("formats") or [])}
    has_embed = bool(embed_url)
    has_3d    = bool({"GLTF", "GLB", "OBJ", "FBX", "USDZ"} & formats)
    if has_embed and has_3d:
        return 0.5
    if has_embed or has_3d:
        return 0.25
    return 0.0


def _chemical_property_match(query_tokens: set[str], model: dict) -> float:
    """
    Chemical-domain specific: match query against formula, crystal system,
    elements, and material properties. Returns 0.0–1.0.
    """
    chem_tokens = set()
    for field in ["formula_pretty", "formula_anonymous", "chemsys",
                  "crystal_system", "spacegroup_symbol", "point_group",
                  "magnetic_ordering"]:
        val = model.get(field)
        if val:
            chem_tokens.update(_tokenize(str(val)))
    for el in (model.get("elements") or []):
        chem_tokens.update(_tokenize(str(el)))
    for prop in (model.get("has_props") or []):
        chem_tokens.update(_tokenize(str(prop)))

    if not chem_tokens or not query_tokens:
        return 0.0
    return min(len(query_tokens & chem_tokens) / len(query_tokens), 1.0)


def _embed_text_overlap(query_tokens: set[str], model: dict) -> float:
    """
    Overlap against embed_text — a pre-built concatenation of
    name + description + tags + category. Returns 0.0–1.0.
    """
    et_tokens = _tokenize(str(model.get("embed_text") or ""))
    if not query_tokens or not et_tokens:
        return 0.0
    return min(len(query_tokens & et_tokens) / len(query_tokens), 1.0)


def stage3_structural_score(query: str, model: dict) -> float:
    """
    Compute a structural similarity score (0.0–1.0) for the best candidate
    using metadata fields across all domain types.

    Weights:
        embed_text overlap  : 0.30  (richest signal — name + desc + tags + category)
        tag overlap         : 0.25
        name overlap        : 0.20
        category/domain     : 0.10
        format bonus        : 0.10  (rewards renderable models)
        chemical props      : 0.05  (meaningful for chemical domain only)
    """
    query_tokens = _tokenize(query)

    structural = (
        _embed_text_overlap(query_tokens, model)          * 0.30 +
        _tag_overlap(query_tokens, model)                 * 0.25 +
        _name_overlap(query_tokens, model)                * 0.20 +
        _category_match(query_tokens, model)              * 0.10 +
        _format_bonus(model)                              * 0.10 +
        _chemical_property_match(query_tokens, model)     * 0.05
    )

    return round(min(structural, 1.0), 4)


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 4 — Confidence check  (cross-encoder + structural → final score)
# ══════════════════════════════════════════════════════════════════════════════
def search_with_confidence(query: str, domain: str, top_k: int = TOP_K) -> dict:
    """
    Full pipeline:
      Stage 1 → FAISS (MiniLM)                → top 10
      Stage 2 → CrossEncoder rerank           → top 1
      Stage 3 → structural compare            → metadata score
      Stage 4 → weighted confidence           → accept or fallback

    Final score = clip_score (cross-encoder norm) * 0.6 + structural_score * 0.4

    Returns:
        {
            accepted:          bool,
            best_match:        dict,
            best_score:        float,   ← weighted final score
            clip_score:        float,   ← cross-encoder normalized score
            structural_score:  float,
            faiss_score:       float,
            all_results:       list,
            fallback:          bool
        }
    """
    # Stage 1
    candidates = stage1_faiss_search(query, domain, top_k)
    if not candidates:
        return {
            "accepted":         False,
            "best_match":       None,
            "best_score":       0.0,
            "clip_score":       0.0,
            "structural_score": 0.0,
            "faiss_score":      0.0,
            "all_results":      [],
            "fallback":         True
        }

    # Stage 2 — CrossEncoder rerank
    reranked = stage2_cross_encoder_rerank(query, candidates)

    # Stage 3 — structural score on best candidate only
    best             = reranked[0]
    structural_score = stage3_structural_score(query, best["model"])
    best["structural_score"] = structural_score

    # Stage 4 — weighted final score
    final_score = round(
        best["clip_score"] * CLIP_WEIGHT + structural_score * STRUCTURAL_WEIGHT,
        4
    )
    best["final_score"] = final_score
    accepted = final_score >= CONFIDENCE_THRESHOLD

    return {
        "accepted":         accepted,
        "best_match":       best["model"],
        "best_score":       final_score,
        "clip_score":       best["clip_score"],
        "structural_score": structural_score,
        "faiss_score":      best["faiss_score"],
        "all_results":      reranked,
        "fallback":         not accepted
    }


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_cases = [
        ("mitochondria",     "biological"),
        ("black hole",       "astronomical"),
        ("Newton's cradle",  "physical"),
        ("glucose molecule", "chemical"),
    ]

    for query, domain in test_cases:
        if domain not in indexes:
            print(f"[SKIP] '{domain}' not loaded\n")
            continue

        print(f"Query : '{query}' | Domain: {domain}")
        print("-" * 55)
        r = search_with_confidence(query, domain)
        print(f"FAISS score      : {r['faiss_score']:.4f}")
        print(f"CE score (norm)  : {r['clip_score']:.4f}")
        print(f"Structural score : {r['structural_score']:.4f}")
        print(f"Final score      : {r['best_score']:.4f}  (threshold={CONFIDENCE_THRESHOLD})")
        print(f"Accepted         : {r['accepted']}")
        print(f"Fallback         : {r['fallback']}")
        if r["best_match"]:
            m = r["best_match"]
            print(f"Top match        : {m.get('name', 'N/A')}")
            print(f"Description      : {str(m.get('description', ''))[:100]}")
        print()