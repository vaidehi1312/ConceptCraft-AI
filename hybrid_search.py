"""
hybrid_search.py — ConceptCraftAI
Extends search.py with live Sketchfab API search running in parallel with FAISS.

HOW IT FITS IN:
  Stage 0: Query expansion          (unchanged from search.py)
  Stage 1a: FAISS all domains       (unchanged from search.py)
  Stage 1b: Sketchfab API           (NEW — runs in parallel with Stage 1a)
  Stage 1c: Merge + deduplicate     (NEW)
  Stage 2: CrossEncoder rerank      (unchanged — works on merged candidates)
  Stage 3: Structural score         (unchanged)
  Stage 4: Confidence tier          (unchanged)

USAGE:
  # Drop-in replacement for search_with_confidence()
  from hybrid_search import hybrid_search

  result = hybrid_search("human heart anatomy", top_k=10)
  # Returns same dict shape as search_with_confidence()
  # Each result now has "_source": "faiss" | "sketchfab"

ENV:
  SKETCHFAB_API_TOKEN=your_token_here   (in .env file)
  SKETCHFAB_WEIGHT=0.4                  (optional, default 0.4)
"""


import os
import time
import requests
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Import everything from your existing search.py
from search import (
    expand_query,
    stage1_search_all_domains,
    stage2_cross_encoder_rerank,
    stage3_structural_score,
    get_confidence_tier,
    TOP_K,
    TOP_K_PER_DOMAIN,
    TOP_N_RESULTS,
    CONFIDENCE_THRESHOLD,
    CE_WEIGHT,
    STRUCTURAL_WEIGHT,
    indexes,
)

load_dotenv()

# ── Sketchfab Config ──────────────────────────────────────────────────────────
SKETCHFAB_TOKEN   = os.getenv("SKETCHFAB_API_TOKEN", "")
SKETCHFAB_API     = "https://api.sketchfab.com/v3/search"
SKETCHFAB_WEIGHT  = float(os.getenv("SKETCHFAB_WEIGHT", "0.4"))
FAISS_WEIGHT      = 1.0 - SKETCHFAB_WEIGHT   # 0.6 by default

# How many Sketchfab results to fetch (more = slower but richer merge)

SKETCHFAB_FETCH_K = 8   # fewer Sketchfab results
TOP_K_PER_DOMAIN  = 3

from functools import lru_cache
import hashlib

_cache = {}

def hybrid_search(query, domain="all", top_k=TOP_K, include_sketchfab=True):
    cache_key = hashlib.md5(query.lower().strip().encode()).hexdigest()
    if cache_key in _cache:
        print(f"  [HybridSearch] Cache hit for '{query}'")
        return _cache[cache_key]
    
    # ... rest of your existing function ...
    
    _cache[cache_key] = result   # store before returning
    return result

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1b — Sketchfab Live Search
# ══════════════════════════════════════════════════════════════════════════════

def _sketchfab_model_to_candidate(m: dict, rank: int, total: int) -> dict:
    """
    Convert a raw Sketchfab API result into the same candidate dict shape
    that stage1_faiss_search() returns so Stage 2/3/4 work unchanged.
    """
    # Position score: rank 0 = best → 1.0, last → ~0.1
    position_score = 1.0 - (rank / max(total, 1)) * 0.9

    # Build embed_text in the same format as your existing JSON entries
    tags = [t["name"] for t in m.get("tags", [])][:8]
    desc = (m.get("description") or "")[:200]
    embed_text = f"{m.get('name', '')}. {desc}. {' '.join(tags)}"

    # Thumbnail URL
    thumbnail_url = ""
    if m.get("thumbnails"):
        images = m["thumbnails"].get("images", [])
        if images:
            thumbnail_url = images[0].get("url", "")

    # License
    license_label = "CC Attribution"
    if m.get("license"):
        license_label = m["license"].get("label", "CC Attribution")

    # Category from Sketchfab categories
    category = "model"
    if m.get("categories"):
        category = m["categories"][0].get("name", "model")

    model_entry = {
        # Standard ConceptCraftAI fields
        "name":            m.get("name", "Unknown"),
        "uid":             m.get("uid", ""),
        "dataset":         "Sketchfab Live",
        "description":     desc,
        "tags":            tags,
        "category":        category,
        "domain":          "general",
        "license":         license_label,
        "source_type":     "embed",
        "embedding_status": "live",
        "embed_text":      embed_text,

        # URLs
        "embed_url":       f"https://sketchfab.com/models/{m.get('uid', '')}/embed",
        "model_page_url":  m.get("viewerUrl", f"https://sketchfab.com/3d-models/{m.get('uid','')}"),
        "thumbnail_url":   thumbnail_url,
        "download_url":    "",   # fetch on demand via Sketchfab API

        # Render hint for frontend
        "render_type":     "sketchfab_embed",

        # Rich Sketchfab metadata
        "view_count":      m.get("viewCount", 0),
        "like_count":      m.get("likeCount", 0),
        "is_downloadable": m.get("isDownloadable", False),
        "is_staff_picked": m.get("isStaffPicked", False),
        "animation_count": m.get("animationCount", 0),
    }

    return {
        "faiss_score":      position_score,   # position proxy
        "clip_score":       position_score,   # will be replaced by CE in Stage 2
        "structural_score": 0.0,
        "final_score":      position_score,
        "source_domain":    "sketchfab",
        "_source":          "sketchfab",
        "_rank":            rank,
        "model":            model_entry,
    }


def stage1b_sketchfab_search(query: str, top_k: int = SKETCHFAB_FETCH_K) -> list[dict]:
    """
    Live Sketchfab search. Returns candidates in the same shape as FAISS candidates.
    Returns empty list if no token or API fails — graceful degradation.
    """
    if not SKETCHFAB_TOKEN:
        return []

    headers = {"Authorization": f"Token {SKETCHFAB_TOKEN}"}
    params  = {
        "type":        "models",
        "q":           query,
        "downloadable": True,
        "count":       top_k,
        "sort_by":     "-relevance",
    }

    try:
        r = requests.get(SKETCHFAB_API, headers=headers, params=params, timeout=3)
        if r.status_code != 200:
            print(f"  [Sketchfab] API {r.status_code} for '{query}'")
            return []

        results = r.json().get("results", [])
        total   = len(results)

        return [
            _sketchfab_model_to_candidate(m, rank, total)
            for rank, m in enumerate(results)
        ]

    except requests.exceptions.Timeout:
        print(f"  [Sketchfab] Timeout for '{query}' — skipping")
        return []
    except Exception as e:
        print(f"  [Sketchfab] Error: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1c — Merge FAISS + Sketchfab candidates
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_scores(candidates: list[dict], score_key: str = "faiss_score") -> list[dict]:
    """Normalize scores within a list to 0-1 range."""
    if not candidates:
        return candidates
    scores  = [c[score_key] for c in candidates]
    min_s   = min(scores)
    max_s   = max(scores)
    rng     = max_s - min_s or 1.0
    for c in candidates:
        c[f"_{score_key}_normalized"] = (c[score_key] - min_s) / rng
    return candidates


def stage1c_merge(
    faiss_candidates:     list[dict],
    sketchfab_candidates: list[dict],
    top_k:                int = TOP_K,
) -> list[dict]:
    """
    Merge FAISS and Sketchfab candidates.

    - Normalize scores within each source separately
    - Apply source weights
    - Deduplicate by name (case-insensitive, first 40 chars)
    - Return top_k merged candidates for Stage 2
    """
    # Tag sources
    for c in faiss_candidates:
        c["_source"] = c.get("_source", "faiss")
    for c in sketchfab_candidates:
        c["_source"] = "sketchfab"

    # Normalize within each group
    faiss_candidates     = _normalize_scores(faiss_candidates,     "faiss_score")
    sketchfab_candidates = _normalize_scores(sketchfab_candidates, "faiss_score")

    # Apply weights to get weighted score
    for c in faiss_candidates:
        c["_weighted_score"] = c["_faiss_score_normalized"] * FAISS_WEIGHT
    for c in sketchfab_candidates:
        c["_weighted_score"] = c["_faiss_score_normalized"] * SKETCHFAB_WEIGHT

    # Merge and sort
    merged = faiss_candidates + sketchfab_candidates
    merged.sort(key=lambda x: x["_weighted_score"], reverse=True)

    # Deduplicate by name
    seen  = set()
    dedup = []
    for c in merged:
        name_key = c["model"].get("name", "").lower().strip()[:40]
        if name_key and name_key not in seen:
            seen.add(name_key)
            dedup.append(c)

    return dedup[:top_k]


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — Hybrid Search (drop-in replacement for search_with_confidence)
# ══════════════════════════════════════════════════════════════════════════════

def hybrid_search(
    query:              str,
    domain:             str  = "all",
    top_k:              int  = TOP_K,
    include_sketchfab:  bool = True,
) -> dict:
    """
    Full hybrid pipeline:
      Stage 0  → Query expansion (local)
      Stage 1a → FAISS all domains (parallel)
      Stage 1b → Sketchfab API (parallel with 1a, graceful on failure)
      Stage 1c → Merge + deduplicate
      Stage 2  → CrossEncoder rerank (original query)
      Stage 3  → Structural score
      Stage 4  → Confidence tier

    Returns same dict shape as search_with_confidence().
    Each model in results has "_source": "faiss" | "sketchfab".

    Args:
        query:             User's natural language query
        domain:            Hint domain (ignored in hybrid — searches all)
        top_k:             Number of results to consider
        include_sketchfab: Set False for offline mode or testing
    """
    t0 = time.time()

    # ── Stage 0: Query expansion ──────────────────────────────────────────────
    expanded_query = expand_query(query)

    # ── Stage 1a + 1b: Parallel FAISS + Sketchfab ────────────────────────────
    faiss_candidates     = []
    sketchfab_candidates = []

    use_sketchfab = include_sketchfab and bool(SKETCHFAB_TOKEN)

    if use_sketchfab:
        with ThreadPoolExecutor(max_workers=2) as pool:
            faiss_future     = pool.submit(stage1_search_all_domains, expanded_query, TOP_K_PER_DOMAIN)
            sketchfab_future = pool.submit(stage1b_sketchfab_search,  query, SKETCHFAB_FETCH_K)
            faiss_candidates     = faiss_future.result()
            sketchfab_candidates = sketchfab_future.result()
    else:
        faiss_candidates = stage1_search_all_domains(expanded_query, TOP_K_PER_DOMAIN)

    n_faiss     = len(faiss_candidates)
    n_sketchfab = len(sketchfab_candidates)

    # ── Stage 1c: Merge ───────────────────────────────────────────────────────
    if sketchfab_candidates:
        candidates = stage1c_merge(faiss_candidates, sketchfab_candidates, top_k)
    else:
        candidates = faiss_candidates[:top_k]
        for c in candidates:
            c["_source"] = c.get("_source", "faiss")

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
            "_sources":          {"faiss": 0, "sketchfab": 0},
            "_latency_ms":       round((time.time() - t0) * 1000),
        }

    # ── Stage 2: CrossEncoder rerank (original query) ─────────────────────────
    reranked = stage2_cross_encoder_rerank(query, candidates)
    
    filtered = [c for c in reranked if c.get("clip_score", 0) >= 0.15]
    if not filtered:
        reranked = candidates[:3]  # Fallback to top 3 semantic matches
    else:
        reranked = filtered

    # ── Stage 3: Structural score ─────────────────────────────────────────────
    for candidate in reranked:
        structural_score              = stage3_structural_score(query, candidate["model"])
        candidate["structural_score"] = structural_score
        candidate["final_score"]      = round(
            candidate["clip_score"] * CE_WEIGHT + structural_score * STRUCTURAL_WEIGHT, 4
        )

    reranked.sort(key=lambda x: x["final_score"], reverse=True)

    # ── Stage 4: Confidence tier ──────────────────────────────────────────────
    best = reranked[0]
    tier = get_confidence_tier(best["final_score"])

    top_matches = [
        c for c in reranked
        if get_confidence_tier(c["final_score"]) != "fallback"
    ][:TOP_N_RESULTS]

    elapsed_ms = round((time.time() - t0) * 1000)

    sources_breakdown = {
        "faiss":     sum(1 for c in reranked if c.get("_source") != "sketchfab"),
        "sketchfab": sum(1 for c in reranked if c.get("_source") == "sketchfab"),
    }

    print(
        f"  [HybridSearch] '{query}' → "
        f"{n_faiss} FAISS + {n_sketchfab} Sketchfab → "
        f"{len(reranked)} merged → "
        f"tier={tier} score={best['final_score']:.3f} "
        f"({elapsed_ms}ms)"
    )

    return {
        # Same shape as search_with_confidence()
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

        # Extra hybrid metadata
        "_source":           best.get("_source", "faiss"),
        "_sources":          sources_breakdown,
        "_latency_ms":       elapsed_ms,
        "_sketchfab_active": use_sketchfab,
    }


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_cases = [
        ("human heart anatomy",  "biological"),
        ("mars rover",           "astronomical"),
        ("DNA double helix",     "biological"),
        ("crystal structure",    "chemical"),
        ("mechanical gear",      "physical"),
    ]

    for query, hint in test_cases:
        print(f"\n{'='*60}")
        print(f"Query: '{query}'  (hint: {hint})")
        print(f"{'='*60}")
        r = hybrid_search(query)

        print(f"  Tier     : {r['confidence_tier']}")
        print(f"  Score    : {r['best_score']:.4f}")
        print(f"  Source   : {r['_source']}")
        print(f"  Sources  : {r['_sources']}")
        print(f"  Latency  : {r['_latency_ms']}ms")
        if r["best_match"]:
            m = r["best_match"]
            print(f"  Match    : {m.get('name','?')}")
            print(f"  Render   : {m.get('render_type','glb')}")
            print(f"  Embed    : {m.get('embed_url','')[:60]}")
        if len(r["top_matches"]) > 1:
            alts = [m.get("name","?") for m in r["top_matches"][1:]]
            print(f"  Alts     : {alts}")