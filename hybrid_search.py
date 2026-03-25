"""
hybrid_search.py — ConceptCraftAI
Extends search.py with live Sketchfab API search running in parallel with FAISS.

ARCHITECTURE (v5 — dual-track):
  Sketchfab and FAISS results travel through SEPARATE pipelines and only
  merge at the very end. This guarantees Sketchfab results always survive
  to the final output.

  Track A (Sketchfab):
    Stage 1b: Sketchfab API search (expanded query)
    Stage 2a: CrossEncoder rerank (original query)
    Stage 3a: Name-match boost
    → Best Sketchfab result(s) guaranteed in output

  Track B (FAISS):
    Stage 1a: FAISS all domains (expanded query)
    Stage 2b: CrossEncoder rerank (original query)
    Stage 3b: Structural score + Name-match boost
    → Best FAISS results follow after Sketchfab

  Final merge:
    1. Best Sketchfab embeddable results (at least 1)
    2. FAISS results that can render inline (GLB, embed)
    3. External-link-only results (bottom)
"""

import os
import time
import hashlib
import requests
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

from search import (
    expand_query,
    stage1_search_all_domains,
    stage2_cross_encoder_rerank,
    stage3_structural_score,
    get_confidence_tier,
    _compute_name_boost,
    _extract_core_query,
    TOP_K,
    TOP_K_PER_DOMAIN,
    TOP_N_RESULTS,
    CONFIDENCE_THRESHOLD,
    CE_WEIGHT,
    STRUCTURAL_WEIGHT,
    NAME_BOOST_WEIGHT,
    indexes,
)

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
SKETCHFAB_TOKEN   = os.getenv("SKETCHFAB_API_TOKEN", "")
SKETCHFAB_API     = "https://api.sketchfab.com/v3/search"
SKETCHFAB_FETCH_K = 8

_cache = {}


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1b — Sketchfab Live Search
# ══════════════════════════════════════════════════════════════════════════════

def _sketchfab_model_to_candidate(m: dict, rank: int, total: int) -> dict:
    position_score = 1.0 - (rank / max(total, 1)) * 0.9

    tags = [t["name"] for t in m.get("tags", [])][:8]
    desc = (m.get("description") or "")[:200]
    embed_text = f"{m.get('name', '')}. {desc}. {' '.join(tags)}"

    thumbnail_url = ""
    if m.get("thumbnails"):
        images = m["thumbnails"].get("images", [])
        if images:
            thumbnail_url = images[0].get("url", "")

    license_label = "CC Attribution"
    if m.get("license"):
        license_label = m["license"].get("label", "CC Attribution")

    category = "model"
    if m.get("categories"):
        category = m["categories"][0].get("name", "model")

    uid = m.get("uid", "")

    model_entry = {
        "name":             m.get("name", "Unknown"),
        "uid":              uid,
        "dataset":          "Sketchfab Live",
        "description":      desc,
        "tags":             tags,
        "category":         category,
        "domain":           "general",
        "license":          license_label,
        "source_type":      "embed",
        "embedding_status": "live",
        "embed_text":       embed_text,
        "embed_url":        f"https://sketchfab.com/models/{uid}/embed",
        "model_page_url":   m.get("viewerUrl", f"https://sketchfab.com/3d-models/{uid}"),
        "thumbnail_url":    thumbnail_url,
        "download_url":     "",
        "render_type":      "sketchfab_embed",
        "view_count":       m.get("viewCount", 0),
        "like_count":       m.get("likeCount", 0),
        "is_downloadable":  m.get("isDownloadable", False),
        "is_staff_picked":  m.get("isStaffPicked", False),
        "animation_count":  m.get("animationCount", 0),
    }

    return {
        "faiss_score":      position_score,
        "clip_score":       position_score,
        "structural_score": 0.0,
        "final_score":      position_score,
        "source_domain":    "sketchfab",
        "_source":          "sketchfab",
        "_rank":            rank,
        "model":            model_entry,
    }


def stage1b_sketchfab_search(query: str, top_k: int = SKETCHFAB_FETCH_K) -> list[dict]:
    if not SKETCHFAB_TOKEN:
        return []

    headers = {"Authorization": f"Token {SKETCHFAB_TOKEN}"}
    params  = {
        "type":         "models",
        "q":            query,
        "downloadable": True,
        "count":        top_k,
        "sort_by":      "-relevance",
    }

    try:
        r = requests.get(SKETCHFAB_API, headers=headers, params=params, timeout=5)
        if r.status_code != 200:
            print(f"  [Sketchfab] API {r.status_code} for '{query}'")
            return []

        results = r.json().get("results", [])
        total   = len(results)
        candidates = [
            _sketchfab_model_to_candidate(m, rank, total)
            for rank, m in enumerate(results)
        ]
        print(f"  [Sketchfab] Got {len(candidates)} results for '{query}'")
        return candidates

    except requests.exceptions.Timeout:
        print(f"  [Sketchfab] Timeout for '{query}'")
        return []
    except Exception as e:
        print(f"  [Sketchfab] Error: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Display-tier classification
# ══════════════════════════════════════════════════════════════════════════════

def _can_render_inline(candidate: dict) -> bool:
    """Check if a result can render inline in the frontend."""
    model       = candidate.get("model", {})
    source      = candidate.get("_source", "faiss")
    render_type = model.get("render_type", "")
    embed_url   = model.get("embed_url") or model.get("url") or ""
    model_url   = model.get("model_url") or ""
    formats     = {str(f).upper() for f in (model.get("formats") or [])}

    if source == "sketchfab":
        return True
    if render_type in ("sketchfab_embed", "molecule_viewer") and embed_url:
        return True
    if model_url and model_url.endswith(".glb"):
        return True
    if render_type == "glb":
        return True
    if bool({"GLTF", "GLB", "OBJ", "FBX"} & formats):
        return True
    if embed_url and ("embed" in embed_url or "sketchfab" in embed_url):
        return True

    return False


# ══════════════════════════════════════════════════════════════════════════════
# Score a track of candidates (CE + structural + name boost)
# ══════════════════════════════════════════════════════════════════════════════

def _score_candidates(original_query: str, candidates: list[dict]) -> list[dict]:
    """
    Run CrossEncoder rerank, structural score, and name-boost on a list
    of candidates. Returns scored and sorted list. NO FILTERING.
    """
    if not candidates:
        return []

    # CrossEncoder with ORIGINAL query
    reranked = stage2_cross_encoder_rerank(original_query, candidates)

    # Score all — do NOT filter by CE score
    for c in reranked:
        structural = stage3_structural_score(original_query, c["model"])
        name_boost = _compute_name_boost(original_query, c["model"])

        c["structural_score"] = structural
        c["name_boost"]       = name_boost
        c["final_score"]      = round(
            c["clip_score"] * CE_WEIGHT +
            structural      * STRUCTURAL_WEIGHT +
            name_boost      * NAME_BOOST_WEIGHT,
            4
        )

    reranked.sort(key=lambda x: x["final_score"], reverse=True)
    return reranked


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — Hybrid Search (dual-track architecture)
# ══════════════════════════════════════════════════════════════════════════════

def hybrid_search(
    query:              str,
    domain:             str  = "all",
    top_k:              int  = TOP_K,
    include_sketchfab:  bool = True,
) -> dict:
    """
    Dual-track hybrid pipeline:

    Track A: Sketchfab results scored independently, NEVER filtered out
    Track B: FAISS results scored independently
    Final:   Sketchfab on top, then FAISS inline, then external-only

    This guarantees at least 1 Sketchfab result is always #1 when available.
    """
    t0 = time.time()

    # ── Cache ─────────────────────────────────────────────────────────────────
    cache_key = hashlib.md5(query.lower().strip().encode()).hexdigest()
    if cache_key in _cache:
        print(f"  [HybridSearch] Cache hit for '{query}'")
        return _cache[cache_key]

    # ── Stage 0: Query expansion ──────────────────────────────────────────────
    expanded_query = expand_query(query)
    print(f"  [HybridSearch] query='{query}' expanded='{expanded_query}'")

    # ── Stage 1: Parallel fetch ───────────────────────────────────────────────
    faiss_candidates     = []
    sketchfab_candidates = []
    use_sketchfab = include_sketchfab and bool(SKETCHFAB_TOKEN)

    if use_sketchfab:
        with ThreadPoolExecutor(max_workers=2) as pool:
            faiss_future     = pool.submit(stage1_search_all_domains, expanded_query, TOP_K_PER_DOMAIN)
            sketchfab_future = pool.submit(stage1b_sketchfab_search,  expanded_query, SKETCHFAB_FETCH_K)
            faiss_candidates     = faiss_future.result()
            sketchfab_candidates = sketchfab_future.result()
    else:
        faiss_candidates = stage1_search_all_domains(expanded_query, TOP_K_PER_DOMAIN)

    # Tag sources
    for c in faiss_candidates:
        c["_source"] = "faiss"
    for c in sketchfab_candidates:
        c["_source"] = "sketchfab"

    n_faiss     = len(faiss_candidates)
    n_sketchfab = len(sketchfab_candidates)
    print(f"  [HybridSearch] Fetched: {n_faiss} FAISS + {n_sketchfab} Sketchfab")

    # ── Handle empty results ──────────────────────────────────────────────────
    if not faiss_candidates and not sketchfab_candidates:
        elapsed_ms = round((time.time() - t0) * 1000)
        result = {
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
            "_source":           "none",
            "_sources":          {"faiss": 0, "sketchfab": 0},
            "_latency_ms":       elapsed_ms,
            "_sketchfab_active": use_sketchfab,
        }
        _cache[cache_key] = result
        return result

    # ══════════════════════════════════════════════════════════════════════════
    # DUAL-TRACK SCORING — each track scored independently, no cross-filtering
    # ══════════════════════════════════════════════════════════════════════════

    # Track A: Score Sketchfab results (NEVER filtered, NEVER dropped)
    scored_sketchfab = _score_candidates(query, sketchfab_candidates)

    # Track B: Score FAISS results
    scored_faiss = _score_candidates(query, faiss_candidates)

    # ══════════════════════════════════════════════════════════════════════════
    # FINAL MERGE — Sketchfab on top, then FAISS by renderability
    # ══════════════════════════════════════════════════════════════════════════

    # Deduplicate: if a Sketchfab result has the same name as a FAISS result,
    # keep the Sketchfab one (it renders better)
    sketchfab_names = set()
    for c in scored_sketchfab:
        sketchfab_names.add(c["model"].get("name", "").lower().strip()[:40])

    deduped_faiss = []
    for c in scored_faiss:
        name_key = c["model"].get("name", "").lower().strip()[:40]
        if name_key not in sketchfab_names:
            deduped_faiss.append(c)

    # Split FAISS into inline-renderable vs external-only
    faiss_inline   = [c for c in deduped_faiss if _can_render_inline(c)]
    faiss_external = [c for c in deduped_faiss if not _can_render_inline(c)]

    # Final order:
    #   1. Sketchfab results (best first) — guaranteed at least 1 on top
    #   2. FAISS results that render inline (best first)
    #   3. FAISS results that are external-only (best first, at bottom)
    final_results = scored_sketchfab + faiss_inline + faiss_external

    # Debug output
    print(f"  [FinalMerge] {len(scored_sketchfab)} Sketchfab (top) + "
          f"{len(faiss_inline)} FAISS-inline + {len(faiss_external)} external (bottom)")
    for i, c in enumerate(final_results[:5]):
        m = c["model"]
        print(
            f"    #{i+1} [{c.get('_source','?'):9s}] {m.get('name','?')[:40]:40s} "
            f"CE={c['clip_score']:.3f} Name={c.get('name_boost',0):.3f} "
            f"Final={c['final_score']:.3f}"
        )

    # ── Determine overall confidence from the best result ─────────────────────
    best = final_results[0]
    tier = get_confidence_tier(best["final_score"])

    # If the best Sketchfab result has very low relevance but FAISS has a good one,
    # use the higher score for the overall confidence
    if scored_sketchfab and scored_faiss:
        faiss_best_score = scored_faiss[0]["final_score"]
        sf_best_score    = scored_sketchfab[0]["final_score"]
        overall_score    = max(faiss_best_score, sf_best_score)
        tier             = get_confidence_tier(overall_score)
        best_score       = overall_score
    else:
        best_score = best["final_score"]

    top_matches = [
        c for c in final_results
        if get_confidence_tier(c["final_score"]) != "fallback"
    ][:TOP_N_RESULTS]

    elapsed_ms = round((time.time() - t0) * 1000)

    sources_breakdown = {
        "faiss":     len(deduped_faiss),
        "sketchfab": len(scored_sketchfab),
    }

    print(
        f"  [HybridSearch] '{query}' -> tier={tier} "
        f"best_score={best_score:.3f} top='{best['model'].get('name','?')}' "
        f"({elapsed_ms}ms)"
    )

    # Use overall fallback only if BOTH tracks produced nothing good
    is_fallback = (
        (not scored_sketchfab or scored_sketchfab[0]["final_score"] < 0.15) and
        (not scored_faiss or scored_faiss[0]["final_score"] < CONFIDENCE_THRESHOLD)
    )

    result = {
        "accepted":          not is_fallback,
        "confidence_tier":   "fallback" if is_fallback else tier,
        "best_match":        best["model"],
        "top_matches":       [m["model"] for m in top_matches],
        "best_score":        best_score,
        "clip_score":        best["clip_score"],
        "structural_score":  best["structural_score"],
        "faiss_score":       best["faiss_score"],
        "source_domain":     best.get("source_domain", "unknown"),
        "all_results":       final_results,
        "fallback":          is_fallback,
        "_source":           best.get("_source", "faiss"),
        "_sources":          sources_breakdown,
        "_latency_ms":       elapsed_ms,
        "_sketchfab_active": use_sketchfab,
    }

    _cache[cache_key] = result
    return result


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_cases = [
        "human heart anatomy",
        "heart",
        "heart anatomy",
        "water cycle",
        "earth",
        "planet earth",
        "saturn",
        "planet saturn",
        "mars",
        "DNA",
        "mitochondria",
        "glucose",
    ]

    for query in test_cases:
        print(f"\n{'='*65}")
        print(f"Query: '{query}'")
        print(f"{'='*65}")
        r = hybrid_search(query)

        print(f"  Tier     : {r['confidence_tier']}")
        print(f"  Score    : {r['best_score']:.4f}")
        print(f"  Fallback : {r['fallback']}")
        print(f"  Sources  : {r['_sources']}")
        print(f"  Latency  : {r['_latency_ms']}ms")
        if r["best_match"]:
            m = r["best_match"]
            print(f"  #1 Match : {m.get('name','?')}")
            print(f"  #1 Source: {r['_source']}")
            print(f"  #1 Render: {m.get('render_type','?')}")
        print(f"  Total results: {len(r['all_results'])}")
        for i, c in enumerate(r["all_results"][:3]):
            m = c["model"]
            print(f"    [{i+1}] {c.get('_source','?'):9s} | {m.get('name','?')[:45]}")