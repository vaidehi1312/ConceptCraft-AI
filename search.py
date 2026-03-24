"""
search.py — ConceptCraftAI
Stage 0: Query expansion (local, no API) → enriched query string
Stage 1: MiniLM (all-MiniLM-L6-v2) → FAISS ALL domains → top 10 candidates
Stage 2: CrossEncoder (ms-marco-MiniLM-L-6-v2) → text relevance rerank → top 1
Stage 3: Structural score → format/richness signal
Stage 4: Confidence tier → high / medium / low / fallback

KEY DESIGN DECISIONS:
  1. Query expansion (Stage 0) — enriches short/vague queries before FAISS
     so "DNA" finds "DNA Double Helix", "heart" finds cardiac anatomy models.
     Fully local, zero API calls.

  2. Dataset tag problem — many models have e.g. "mitochondria" as a TAG
     but are actually about ATP Synthase, ribosomes, etc. FAISS finds them
     (tag is in embed_text), but CrossEncoder correctly scores them low
     because the model name/description doesn't match. This is correct
     behaviour — the CE is filtering tag noise out.

  3. Always return best match, never return nothing — threshold is now a
     confidence TIER, not a hard gate. We always return the best retrieval
     result. The tier tells the frontend how to present it:
       "high"     (≥0.65) → show confidently, no caveat
       "medium"   (≥0.45) → show with "closest match" label
       "low"      (≥0.30) → show with "nearest available" warning
       "fallback" (<0.30) → retrieval genuinely irrelevant, use generative fallback

  4. Top-N results returned — not just top 1, so frontend can show alternatives.
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
TOP_K                = 6
TOP_K_PER_DOMAIN     = 3
CONFIDENCE_THRESHOLD = 0.30      # only reject genuinely irrelevant matches
TOP_N_RESULTS        = 3         # return top 3 matches for frontend alternatives
DOMAINS              = ["biological", "physical", "chemical", "astronomical"]

CE_WEIGHT         = 0.7
STRUCTURAL_WEIGHT = 0.3

# ── CE normalization ──────────────────────────────────────────────────────────
def _normalize_ce_score(raw: float) -> float:
    return float(1.0 / (1.0 + np.exp(-raw / 3.0)))


# ── Confidence tier ───────────────────────────────────────────────────────────
def get_confidence_tier(score: float) -> str:
    """
    Translates a final score into a display tier for the frontend.

    "high"     ≥ 0.65  — strong match, show confidently
    "medium"   ≥ 0.45  — decent match, label as "closest match"
    "low"      ≥ 0.30  — weak match, label as "nearest available — may not be exact"
    "fallback" < 0.30  — retrieval is genuinely irrelevant, trigger generative fallback
    """
    if score >= 0.65:
        return "high"
    elif score >= 0.45:
        return "medium"
    elif score >= 0.30:
        return "low"
    else:
        return "fallback"


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 0 — Query Expansion (fully local, no API)
# ══════════════════════════════════════════════════════════════════════════════

# Alias map: common shorthand → richer descriptive query
# Add more as you discover gaps in your dataset coverage
CONCEPT_EXPANSIONS = {
    # Biological
    "heart": "human heart anatomy",
    "brain": "human brain anatomy neuroscience",
    "cell": "animal cell biology organelle",
    "dna": "DNA double helix genetics",
    "lung": "human lung respiratory anatomy",
    "eye": "human eye optical anatomy",
    "kidney": "human kidney renal anatomy",
    "liver": "human liver organ anatomy",
    "blood": "blood cell biology anatomy",
    "bone": "human bone skeleton anatomy",
    "muscle": "human muscle tissue anatomy",
    "virus": "virus biology structure",
    "bacteria": "bacteria biology microorganism",
    "protein": "protein molecule biology",
    "neuron": "neuron brain cell nervous system",

    # Astronomical
    "earth": "planet earth",
    "moon": "lunar moon satellite",
    "sun": "solar sun star",
    "mars": "planet mars astronomy",
    "jupiter": "planet jupiter",
    "saturn": "planet saturn",
    "galaxy": "galaxy milky way cosmos",
    "asteroid": "asteroid space rock",
    "nebula": "nebula gas cloud space",

    # Chemical
    "water": "water molecule H2O chemistry",
    "glucose": "glucose sugar molecule",
    "salt": "sodium chloride crystal",
    "diamond": "diamond carbon crystal",
    "oxygen": "oxygen molecule chemistry",

    # Physical
    "atom": "atom nuclear structure electron",
    "gear": "mechanical gear engineering",
    "engine": "engine mechanical motor",
    "crystal": "crystal structure lattice",
    "circuit": "electronic circuit physics",

    # Structures
    "pyramid": "pyramid ancient egypt monument",
    "castle": "castle medieval architecture",
    "temple": "temple ancient monument",
}

def expand_query(query: str) -> str:
    """
    Expand short or ambiguous queries with domain context.
    Uses lookup table first, then falls back to existing logic.
    """
    cleaned = query.lower().strip()
    
    # Direct lookup first
    if cleaned in CONCEPT_EXPANSIONS:
        expanded = CONCEPT_EXPANSIONS[cleaned]
        print(f"  [QueryExpansion] '{query}' → '{expanded}'")
        return expanded
    
    # Check if any key is contained in the query
    for key, expansion in CONCEPT_EXPANSIONS.items():
        if key in cleaned and len(cleaned.split()) <= 2:
            expanded = f"{query} {expansion}"
            print(f"  [QueryExpansion] '{query}' → '{expanded}'")
            return expanded
    
    # Fall back to existing expand_query logic
    return query


# ── Load models ───────────────────────────────────────────────────────────────
print(f"Loading MiniLM: {MINILM_MODEL}")
minilm = SentenceTransformer(MINILM_MODEL)
print(f"  MiniLM ready ✅")

print(f"Loading CrossEncoder: {CROSS_ENCODER_MODEL}")
cross_encoder = CrossEncoder(CROSS_ENCODER_MODEL)
print(f"  CrossEncoder ready ✅")


# ── Load FAISS indexes ────────────────────────────────────────────────────────
LARGE_DOMAIN_THRESHOLD = 10_000

indexes       = {}
catalogs      = {}
catalog_paths = {}
offset_maps   = {}


def _parse_offset_map(json_path: Path) -> list[int]:
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
        catalog_paths[domain] = json_path
        print(f"  Building offset map for '{domain}' (large: {n_vectors} vectors)...")
        offset_maps[domain] = _parse_offset_map(json_path)
        n_entries = len(offset_maps[domain])
    else:
        with open(json_path, encoding="utf-8") as f:
            catalogs[domain] = json.load(f)
        n_entries = len(catalogs[domain])

    print(f"  Loaded '{domain}': {n_vectors} vectors, {n_entries} entries, dim={indexes[domain].d}")

print(f"\nReady. Domains: {list(indexes.keys())}\n")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1 — MiniLM + FAISS (single domain)
# ══════════════════════════════════════════════════════════════════════════════
def stage1_faiss_search(query: str, domain: str, top_k: int = TOP_K) -> list[dict]:
    domain = domain.lower()
    if domain not in indexes:
        return []

    query_vec = minilm.encode([query], convert_to_numpy=True).astype(np.float32)
    faiss.normalize_L2(query_vec)

    scores, indices = indexes[domain].search(query_vec, top_k)

    results    = []
    use_offset = domain in offset_maps
    max_idx    = (len(offset_maps[domain]) if use_offset else len(catalogs[domain])) - 1

    for score, idx in zip(scores[0], indices[0]):
        i = int(idx)
        if i == -1 or i > max_idx:
            continue
        model_entry = _fetch_entry(domain, i) if use_offset else catalogs[domain][i]
        results.append({
            "faiss_score":      float(score),
            "clip_score":       float(score),
            "structural_score": 0.0,
            "final_score":      float(score),
            "source_domain":    domain,
            "model":            model_entry,
        })

    return results


def stage1_search_all_domains(expanded_query: str, top_k_per_domain: int = TOP_K_PER_DOMAIN) -> list[dict]:
    """Search ALL indexes with the expanded query, merge, return top TOP_K."""
    all_candidates = []

    for domain in indexes.keys():
        try:
            candidates = stage1_faiss_search(expanded_query, domain, top_k_per_domain)
            all_candidates.extend(candidates)
        except Exception as e:
            print(f"  [WARN] Domain '{domain}' failed: {e}")

    if not all_candidates:
        return []

    all_candidates.sort(key=lambda x: x["faiss_score"], reverse=True)
    return all_candidates[:TOP_K]


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2 — CrossEncoder reranking
# ══════════════════════════════════════════════════════════════════════════════
def stage2_cross_encoder_rerank(original_query: str, candidates: list[dict]) -> list[dict]:
    """
    Use ORIGINAL query (not expanded) for cross-encoder pairs.
    Expansion helps FAISS find candidates; cross-encoder judges them
    against what the user actually typed.
    """
    if not candidates:
        return candidates

    pairs = [
        (original_query, c["model"].get("embed_text") or c["model"].get("name") or "")
        for c in candidates
    ]

    raw_scores = cross_encoder.predict(pairs)

    for c, raw in zip(candidates, raw_scores):
        c["clip_score"] = _normalize_ce_score(float(raw))

    return sorted(candidates, key=lambda x: x["clip_score"], reverse=True)


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3 — Structural score
# ══════════════════════════════════════════════════════════════════════════════
def stage3_structural_score(query: str, model: dict) -> float:
    score = 0.0

    formats   = {str(f).upper() for f in (model.get("formats") or [])}
    embed_url = model.get("embed_url") or model.get("url") or ""
    has_embed = bool(embed_url)
    has_3d    = bool({"GLTF", "GLB", "OBJ", "FBX", "USDZ"} & formats)

    if has_embed and has_3d:
        score += 0.40
    elif has_embed or has_3d:
        score += 0.20

    tag_count  = len(model.get("tags") or [])
    score     += min(tag_count / 10.0, 1.0) * 0.30

    desc = str(model.get("description") or "")
    if len(desc) > 50:
        score += 0.20
    elif len(desc) > 10:
        score += 0.10

    has_structured = bool(
        model.get("formula_pretty") or
        model.get("elements")       or
        model.get("chemsys")        or
        model.get("has_props")
    )
    if has_structured:
        score += 0.10

    return round(min(score, 1.0), 4)


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 4 — Confidence check
# ══════════════════════════════════════════════════════════════════════════════
def search_with_confidence(query: str, domain: str = "all", top_k: int = TOP_K) -> dict:
    """
    Full pipeline:
      Stage 0 → Query expansion          → enriched query for FAISS
      Stage 1 → FAISS across all domains → top 10 merged
      Stage 2 → CrossEncoder rerank      → scored with ORIGINAL query
      Stage 3 → Structural score         → format/richness
      Stage 4 → Confidence tier          → high / medium / low / fallback

    ALWAYS returns the best retrieval result — never returns nothing.
    The confidence_tier field tells the frontend how to present it.
    Only tier=="fallback" should trigger the generative fallback pipeline.
    """
    # Stage 0 — expand query for FAISS only
    expanded_query = expand_query(query)

    # Stage 1 — multi-domain FAISS with expanded query
    candidates = stage1_search_all_domains(expanded_query, TOP_K_PER_DOMAIN)

    if not candidates:
        return {
            "accepted":          False,
            "confidence_tier":   "fallback",
            "best_match":        None,
            "top_matches":       [],
            "best_score":        0.0,
            "clip_score":        0.0,
            "structural_score":  0.0,
            "faiss_score":       0.0,
            "source_domain":     "none",
            "all_results":       [],
            "fallback":          True,
        }

    # Stage 2 — cross-encoder with EXPANDED query
    reranked = stage2_cross_encoder_rerank(expanded_query, candidates)

    # Stage 3 — score all candidates
    for candidate in reranked:
        structural_score              = stage3_structural_score(query, candidate["model"])
        candidate["structural_score"] = structural_score
        candidate["final_score"]      = round(
            candidate["clip_score"] * CE_WEIGHT + structural_score * STRUCTURAL_WEIGHT, 4
        )

    # Stage 4 — confidence tier on best result
    # Re-sort by final_score after structural scoring
    reranked.sort(key=lambda x: x["final_score"], reverse=True)

    # Stage 4 — confidence tier on best result
    best = reranked[0]
    tier = get_confidence_tier(best["final_score"])

    # Collect top N matches that are at least "low" tier (score ≥ 0.30)
    top_matches = [
        c for c in reranked
        if get_confidence_tier(c["final_score"]) != "fallback"
    ][:TOP_N_RESULTS]

    return {
        "accepted":          tier != "fallback",
        "confidence_tier":   tier,                              # "high"/"medium"/"low"/"fallback"
        "best_match":        best["model"],
        "top_matches":       [m["model"] for m in top_matches],
        "best_score":        best["final_score"],
        "clip_score":        best["clip_score"],
        "structural_score":  best["structural_score"],
        "faiss_score":       best["faiss_score"],
        "source_domain":     best.get("source_domain", "unknown"),
        "all_results":       reranked,
        "fallback":          tier == "fallback",
    }


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_cases = [
        ("DNA double helix",  "biological"),
        ("DNA",               "biological"),   # short form — should expand
        ("mitochondria",      "biological"),
        ("black hole",        "astronomical"),
        ("Newton's cradle",   "physical"),
        ("glucose molecule",  "chemical"),
        ("glucose",           "chemical"),     # short form — should expand
        ("heart",             "biological"),   # vague — should expand
    ]

    for query, domain in test_cases:
        print(f"Query : '{query}' | Hint domain: {domain}")
        print("-" * 55)
        r = search_with_confidence(query, domain)
        print(f"FAISS score      : {r['faiss_score']:.4f}")
        print(f"CE score (norm)  : {r['clip_score']:.4f}")
        print(f"Structural score : {r['structural_score']:.4f}")
        print(f"Final score      : {r['best_score']:.4f}  (threshold={CONFIDENCE_THRESHOLD})")
        print(f"Confidence tier  : {r['confidence_tier']}")
        print(f"Source domain    : {r['source_domain']}")
        print(f"Accepted         : {r['accepted']}")
        print(f"Fallback         : {r['fallback']}")
        if r["best_match"]:
            m = r["best_match"]
            print(f"Top match        : {m.get('name', 'N/A')}")
            print(f"Description      : {str(m.get('description', ''))[:100]}")
        if r["top_matches"]:
            print(f"Alt matches      : {[m.get('name','?') for m in r['top_matches'][1:]]}")
        print()
