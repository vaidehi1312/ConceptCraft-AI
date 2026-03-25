"""
search.py — ConceptCraftAI
Stage 0: Query expansion (local, no API) → enriched query string
Stage 1: MiniLM (all-MiniLM-L6-v2) → FAISS ALL domains → top 10 candidates
Stage 2: CrossEncoder (ms-marco-MiniLM-L-6-v2) → text relevance rerank → top 1
Stage 3: Structural score → format/richness signal
Stage 3b: Name-match boost → rewards candidates whose name matches the query
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

  5. Name-match boost (Stage 3b) — short queries like "heart" or "saturn"
     often retrieve models where the query word appears in tags but not in
     the model name. This stage boosts candidates whose NAME contains the
     core query words, so "Human Heart" beats "ATP Synthase" when user
     types "heart".
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

CE_WEIGHT         = 0.55
STRUCTURAL_WEIGHT = 0.20
NAME_BOOST_WEIGHT = 0.25   # NEW: reward name matches

# ── CE normalization ──────────────────────────────────────────────────────────
def _normalize_ce_score(raw: float) -> float:
    return float(1.0 / (1.0 + np.exp(-raw / 3.0)))


# ── Confidence tier ───────────────────────────────────────────────────────────
def get_confidence_tier(score: float) -> str:
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
CONCEPT_EXPANSIONS = {
    # Biological
    "heart":         "human heart anatomy",
    "brain":         "human brain anatomy neuroscience cerebral",
    "cell":          "animal cell biology organelle",
    "dna":           "DNA double helix genetics molecular",
    "lung":          "human lung respiratory anatomy",
    "eye":           "human eye optical anatomy",
    "kidney":        "human kidney renal anatomy organ",
    "liver":         "human liver organ anatomy",
    "blood":         "blood cell biology anatomy",
    "bone":          "human bone skeleton anatomy",
    "muscle":        "human muscle tissue anatomy",
    "virus":         "virus biology structure pathogen",
    "bacteria":      "bacteria biology microorganism",
    "protein":       "protein molecule biology structure",
    "neuron":        "neuron brain cell nervous system",
    "mitochondria":  "mitochondria cell organelle biology",
    "ribosome":      "ribosome cell protein synthesis",
    "skull":         "human skull cranium anatomy",
    "spine":         "human spine vertebral column anatomy",
    "tooth":         "human tooth dental anatomy",
    "stomach":       "human stomach digestive anatomy organ",

    # Astronomical
    "earth":         "planet earth globe world",
    "moon":          "lunar moon satellite astronomy",
    "sun":           "solar sun star astronomy",
    "mars":          "planet mars red planet astronomy",
    "jupiter":       "planet jupiter gas giant astronomy",
    "saturn":        "planet saturn rings astronomy",
    "venus":         "planet venus astronomy",
    "mercury":       "planet mercury astronomy",
    "neptune":       "planet neptune astronomy",
    "uranus":        "planet uranus astronomy",
    "pluto":         "dwarf planet pluto astronomy",
    "galaxy":        "galaxy milky way cosmos space",
    "asteroid":      "asteroid space rock astronomy",
    "nebula":        "nebula gas cloud space astronomy",
    "black hole":    "black hole singularity astronomy",
    "solar system":  "solar system planets sun astronomy",
    "comet":         "comet space astronomy ice",
    "star":          "star astronomy stellar",
    "constellation": "constellation stars astronomy",

    # Chemical
    "water":         "water molecule H2O chemistry",
    "water cycle":   "water cycle earth science",
    "glucose":       "glucose sugar molecule chemistry",
    "salt":          "sodium chloride crystal NaCl chemistry",
    "diamond":       "diamond carbon crystal structure",
    "oxygen":        "oxygen molecule O2 chemistry",
    "caffeine":      "caffeine molecule chemistry",
    "aspirin":       "aspirin molecule chemistry",
    "ethanol":       "ethanol alcohol molecule chemistry",
    "co2":           "carbon dioxide CO2 molecule chemistry",
    "methane":       "methane CH4 molecule chemistry",

    # Physical
    "atom":          "atom nuclear structure electron proton",
    "gear":          "mechanical gear engineering cog",
    "engine":        "engine mechanical motor combustion",
    "crystal":       "crystal structure lattice solid",
    "circuit":       "electronic circuit physics",
    "pendulum":      "pendulum physics oscillation",
    "magnet":        "magnet magnetic field physics",
    "lens":          "lens optics physics refraction",
    "turbine":       "turbine engineering mechanical",
    "motor":         "electric motor engineering",

    # Structures
    "pyramid":       "pyramid ancient egypt monument giza",
    "castle":        "castle medieval architecture fortress",
    "temple":        "temple ancient monument architecture",
    "bridge":        "bridge engineering architecture structure",
    "tower":         "tower architecture building structure",
}

# Words to STRIP from the original query before expansion lookup
# (users type "planet earth" but the key is "earth")
STRIP_PREFIXES = [
    "human", "planet", "the", "a", "an", "show me", "find",
    "search for", "3d model of", "model of", "3d", "molecule",
]


def _extract_core_query(query: str) -> str:
    """
    Strip common prefixes so "planet saturn" → "saturn",
    "human heart" → "heart", "3d model of DNA" → "dna".
    """
    cleaned = query.lower().strip()
    for prefix in sorted(STRIP_PREFIXES, key=len, reverse=True):
        if cleaned.startswith(prefix + " "):
            cleaned = cleaned[len(prefix):].strip()
    return cleaned


def expand_query(query: str) -> str:
    """
    Expand short or ambiguous queries with domain context.
    
    Strategy:
    1. Try exact match on cleaned query
    2. Try exact match after stripping common prefixes
    3. Try partial match (key found inside query)
    4. Return original if no expansion found
    """
    cleaned = query.lower().strip()

    # 1. Direct lookup
    if cleaned in CONCEPT_EXPANSIONS:
        expanded = CONCEPT_EXPANSIONS[cleaned]
        print(f"  [QueryExpansion] '{query}' → '{expanded}' (direct)")
        return expanded

    # 2. Strip prefixes and try again
    core = _extract_core_query(query)
    if core != cleaned and core in CONCEPT_EXPANSIONS:
        expanded = CONCEPT_EXPANSIONS[core]
        print(f"  [QueryExpansion] '{query}' → core '{core}' → '{expanded}' (prefix-stripped)")
        return expanded

    # 3. Check if any key is a substring of the query (for 2-3 word queries)
    if len(cleaned.split()) <= 3:
        for key, expansion in CONCEPT_EXPANSIONS.items():
            if key in cleaned:
                # Merge: keep original + add expansion context
                expanded = f"{query} {expansion}"
                print(f"  [QueryExpansion] '{query}' → '{expanded}' (partial)")
                return expanded

    # 4. No expansion found — return as-is
    return query


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3b — Name-match boost (NEW)
# ══════════════════════════════════════════════════════════════════════════════

def _compute_name_boost(original_query: str, model: dict) -> float:
    """
    Compute a 0.0–1.0 score based on how well the model's NAME matches
    the user's ORIGINAL query (before expansion).

    This fixes the core problem: FAISS finds candidates via tags/embed_text,
    but a model named "ATP Synthase" tagged with "mitochondria" shouldn't
    beat a model named "Mitochondria" when the user searches "mitochondria".

    Scoring:
      - Exact name match (case-insensitive)        → 1.0
      - All query words appear in model name        → 0.85
      - Core query word appears in model name       → 0.6
      - Query word appears in tags but not name     → 0.2
      - No match at all                             → 0.0
    """
    query_lower = original_query.lower().strip()
    query_words = set(query_lower.split())
    core_word = _extract_core_query(original_query)

    model_name = (model.get("name") or "").lower().strip()
    model_tags = [t.lower() for t in (model.get("tags") or [])]
    model_desc = (model.get("description") or "").lower()

    # Exact name match
    if query_lower == model_name or core_word == model_name:
        return 1.0

    # Query is contained in name or name is contained in query
    if query_lower in model_name or core_word in model_name:
        return 0.9

    # All query words in name
    name_words = set(model_name.split())
    if query_words and query_words.issubset(name_words):
        return 0.85

    # Core word in name
    if core_word and core_word in model_name:
        return 0.7

    # Core word appears at start of name
    if core_word and model_name.startswith(core_word):
        return 0.75

    # Any query word in name
    overlap = query_words & name_words
    if overlap:
        return 0.4 + 0.2 * (len(overlap) / len(query_words))

    # Core word in description (first 200 chars, weighted lower)
    if core_word and core_word in model_desc[:200]:
        return 0.3

    # Core word in tags
    if core_word and any(core_word in tag for tag in model_tags):
        return 0.2

    # Any query word in tags
    if any(w in tag for w in query_words for tag in model_tags):
        return 0.1

    return 0.0


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
def stage2_cross_encoder_rerank(query: str, candidates: list[dict]) -> list[dict]:
    """
    Use the provided query for cross-encoder pairs.
    The caller decides whether to pass original or expanded query.
    """
    if not candidates:
        return candidates

    pairs = [
        (query, c["model"].get("embed_text") or c["model"].get("name") or "")
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
# STAGE 4 — Confidence check (full pipeline)
# ══════════════════════════════════════════════════════════════════════════════
def search_with_confidence(query: str, domain: str = "all", top_k: int = TOP_K) -> dict:
    """
    Full pipeline:
      Stage 0  → Query expansion          → enriched query for FAISS
      Stage 1  → FAISS across all domains  → top candidates merged
      Stage 2  → CrossEncoder rerank       → scored with ORIGINAL query
      Stage 3  → Structural score          → format/richness
      Stage 3b → Name-match boost          → rewards name relevance
      Stage 4  → Confidence tier           → high / medium / low / fallback
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

    # Stage 2 — cross-encoder with ORIGINAL query (not expanded!)
    # This is critical: expanded query helps FAISS recall, but CE should
    # judge relevance against what the user actually typed.
    reranked = stage2_cross_encoder_rerank(query, candidates)

    # Stage 3 + 3b — structural score + name-match boost
    for candidate in reranked:
        structural_score = stage3_structural_score(query, candidate["model"])
        name_boost       = _compute_name_boost(query, candidate["model"])

        candidate["structural_score"] = structural_score
        candidate["name_boost"]       = name_boost
        candidate["final_score"]      = round(
            candidate["clip_score"]  * CE_WEIGHT +
            structural_score         * STRUCTURAL_WEIGHT +
            name_boost               * NAME_BOOST_WEIGHT,
            4
        )

    # Re-sort by final_score
    reranked.sort(key=lambda x: x["final_score"], reverse=True)

    # Debug: show top 3 scoring breakdown
    for i, c in enumerate(reranked[:3]):
        m = c["model"]
        print(
            f"  [Rank {i+1}] {m.get('name','?')[:40]:40s} | "
            f"CE={c['clip_score']:.3f} Str={c['structural_score']:.3f} "
            f"Name={c.get('name_boost',0):.3f} → Final={c['final_score']:.3f}"
        )

    # Stage 4 — confidence tier on best result
    best = reranked[0]
    tier = get_confidence_tier(best["final_score"])

    top_matches = [
        c for c in reranked
        if get_confidence_tier(c["final_score"]) != "fallback"
    ][:TOP_N_RESULTS]

    return {
        "accepted":          tier != "fallback",
        "confidence_tier":   tier,
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
        ("DNA",               "biological"),
        ("mitochondria",      "biological"),
        ("black hole",        "astronomical"),
        ("Newton's cradle",   "physical"),
        ("glucose molecule",  "chemical"),
        ("glucose",           "chemical"),
        ("heart",             "biological"),
        ("earth",             "astronomical"),
        ("saturn",            "astronomical"),
        ("planet saturn",     "astronomical"),
        ("planet earth",      "astronomical"),
        ("mars",              "astronomical"),
    ]

    for query, domain in test_cases:
        print(f"\nQuery : '{query}' | Hint domain: {domain}")
        print("-" * 60)
        r = search_with_confidence(query, domain)
        print(f"  Final score      : {r['best_score']:.4f}")
        print(f"  Confidence tier  : {r['confidence_tier']}")
        print(f"  Source domain    : {r['source_domain']}")
        if r["best_match"]:
            m = r["best_match"]
            print(f"  Top match        : {m.get('name', 'N/A')}")
        if r["top_matches"]:
            print(f"  Alt matches      : {[m.get('name','?') for m in r['top_matches'][1:]]}")