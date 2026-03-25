"""
app.py — ConceptCraftAI FastAPI backend
User just types anything — domain is classified automatically by LLM.

Endpoints:
  POST /query   — main endpoint: classify domain → search → return model
  GET  /health  — check loaded domains + model counts
  GET  /domains — list available domains
  POST /search  — (DEBUG ONLY) manual domain override for testing
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import os
import re
import urllib.parse
from fastapi.concurrency import run_in_threadpool

from hybrid_search import hybrid_search, indexes, CONFIDENCE_THRESHOLD
from fallback_service import generate_from_concept, get_static_glb_url

app = FastAPI(
    title="ConceptCraftAI API",
    description="Type anything — we find the 3D model.",
    version="4.4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("fallback_generator/generated", exist_ok=True)
app.mount("/generated", StaticFiles(directory="fallback_generator/generated"), name="generated")


# ── Schemas ───────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 10

class DebugSearchRequest(BaseModel):
    query:  str
    domain: str
    top_k:  Optional[int] = 10

class ModelResult(BaseModel):
    faiss_score:      float
    clip_score:       float
    structural_score: float
    final_score:      float
    name:             str
    description:      str
    thumbnail:        Optional[str] = None
    embed_url:        Optional[str] = None
    model_url:        Optional[str] = None
    model_page_url:   Optional[str] = None
    render_type:      Optional[str] = None
    source:           Optional[str] = None
    api_source:       Optional[str] = None
    metadata:         dict

class QueryResponse(BaseModel):
    mode: str
    confidence_tier: str
    best_score: float
    model_url: Optional[str] = None
    embed_url: Optional[str] = None
    model_page_url: Optional[str] = None
    render_type: str
    name: str
    explanation: str
    all_results: list[ModelResult] = []
    latency_ms: int = 0


# ── Render info extraction ────────────────────────────────────────────────────

def get_render_info(model: dict) -> tuple[str, str, str, str]:
    """
    Returns (render_type, embed_url, model_url, model_page_url)

    Priority:
    1. Sketchfab embed (iframe — always works, best quality)
    2. 3Dmol / PDB molecule viewer (iframe)
    3. GLB file (Three.js local render)
    4. info_card (fallback — external link only)
    """
    raw_url    = model.get("embed_url") or model.get("model_url") or model.get("url") or ""
    model_url  = model.get("download_url") or None
    page_url   = model.get("model_page_url") or model.get("mp_page") or model.get("url") or ""

    # Ensure page_url is valid
    if page_url and not page_url.startswith("http"):
        page_url = None

    # 1. Sketchfab
    sf_match = re.search(r'([a-f0-9]{32})', raw_url)
    if sf_match and "sketchfab" in raw_url.lower():
        uid = sf_match.group(1)
        embed = f"https://sketchfab.com/models/{uid}/embed"
        page  = page_url or f"https://sketchfab.com/3d-models/{uid}"
        return "sketchfab_embed", embed, model_url, page

    # Also check render_type field directly (set by hybrid_search for Sketchfab results)
    if model.get("render_type") == "sketchfab_embed":
        embed = model.get("embed_url") or raw_url
        uid_match = re.search(r'([a-f0-9]{32})', embed)
        if uid_match:
            uid = uid_match.group(1)
            embed = f"https://sketchfab.com/models/{uid}/embed"
            page  = page_url or f"https://sketchfab.com/3d-models/{uid}"
            return "sketchfab_embed", embed, model_url, page

    # 2. 3Dmol / PDB
    if model.get("fetch_url_pdb") or ("3dmol.csb.pitt.edu" in raw_url) or raw_url.endswith(".pdb"):
        pdb_url = model.get("fetch_url_pdb") or raw_url
        if "3dmol.csb.pitt.edu" not in pdb_url:
            pdb_url = f"https://3dmol.csb.pitt.edu/viewer.html?url={urllib.parse.quote(pdb_url)}&style=stick"
        return "molecule_viewer", pdb_url, model_url, page_url

    # 3. Local GLB
    local_path = model.get("local_path", "") or ""
    if (local_path and os.path.exists(local_path)) or model_url:
        return "glb", raw_url, model_url, page_url

    return "info_card", raw_url, model_url, page_url


# ── Format a single result for the frontend ──────────────────────────────────

def format_result(r: dict) -> ModelResult:
    """
    Flatten a hybrid_search candidate dict into the ModelResult shape
    that the frontend expects.

    Each item in the frontend's all_results array needs:
      name, description, thumbnail, embed_url, model_url, model_page_url,
      render_type, source, api_source, faiss_score, clip_score, etc.
    """
    m = r.get("model", {})

    # Extract render info for this specific result
    render_type, embed_url, model_url, page_url = get_render_info(m)

    return ModelResult(
        faiss_score      = round(r.get("faiss_score", 0), 4),
        clip_score       = round(r.get("clip_score", 0), 4),
        structural_score = round(r.get("structural_score", 0.0), 4),
        final_score      = round(r.get("final_score", r.get("clip_score", 0)), 4),
        name             = m.get("name") or m.get("title") or m.get("formula") or "Untitled",
        description      = str(m.get("description") or m.get("summary") or "")[:300],
        thumbnail        = m.get("thumbnail_url") or m.get("thumbnail") or m.get("image_url"),
        embed_url        = embed_url if embed_url else None,
        model_url        = model_url,
        model_page_url   = page_url,
        render_type      = render_type,
        source           = m.get("source") or m.get("dataset") or m.get("hf_dataset") or m.get("source_file"),
        api_source       = r.get("_source") or "faiss",
        metadata         = m,
    )


# ── Free MiniLM-based domain classifier ──────────────────────────────────────

from search import minilm as _minilm_ref
import numpy as _np_ref

_DOMAIN_DESCRIPTIONS = {
    "biological":    "biology cell organism protein DNA anatomy medicine ecology evolution genetics living tissue organ",
    "physical":      "physics mechanics force energy electronics circuit vehicle machine tool structure engineering building",
    "chemical":      "chemistry molecule compound element reaction material crystal formula substance acid metal polymer",
    "astronomical":  "astronomy space planet star galaxy orbit telescope universe comet asteroid nebula solar terrain weather",
}

_domain_vecs = {
    domain: _minilm_ref.encode([desc], convert_to_numpy=True).astype(_np_ref.float32)
    for domain, desc in _DOMAIN_DESCRIPTIONS.items()
}


def classify_domain(query: str) -> str:
    if not query.strip():
        return "biological"

    query_vec = _minilm_ref.encode([query], convert_to_numpy=True).astype(_np_ref.float32)

    best_domain = "biological"
    best_score  = -1.0

    for domain, dvec in _domain_vecs.items():
        if domain not in indexes:
            continue
        score = float(_np_ref.dot(query_vec.flatten(), dvec.flatten()))
        if score > best_score:
            best_score  = score
            best_domain = domain

    print(f"[classify] '{query}' → '{best_domain}' (score={best_score:.4f})")
    return best_domain


# ── Build the API response ────────────────────────────────────────────────────

async def build_response(query: str, result: dict) -> QueryResponse:
    """
    Convert hybrid_search output into the QueryResponse the frontend expects.

    KEY DESIGN: The top-level render_type, embed_url, model_url come from
    all_results[0] — which hybrid_search has already ordered with Sketchfab
    results on top. We do NOT re-scan or re-sort here.

    The frontend uses these top-level fields to decide what to render in
    the main viewer. all_results provides the list of alternatives.
    """
    tier       = result.get("confidence_tier", "medium")
    best_score = result["best_score"]

    # Format all results — preserving the order from hybrid_search
    # (Sketchfab first, then FAISS inline, then external-only)
    all_formatted = [format_result(r) for r in result.get("all_results", [])]

    # ── Fallback mode: generate via TripoSR ───────────────────────────────
    if result["fallback"]:
        fallback_res = await generate_from_concept(query)
        if fallback_res.get("success"):
            model_url = get_static_glb_url(fallback_res["glb_path"])
            return QueryResponse(
                mode="fallback",
                confidence_tier="fallback",
                best_score=0.0,
                model_url=model_url,
                embed_url=None,
                render_type="glb",
                name=query.title(),
                explanation="Model generated on-the-fly via TripoSR.",
                all_results=all_formatted,
                latency_ms=result.get("_latency_ms", 0),
            )
        else:
            return QueryResponse(
                mode="fallback",
                confidence_tier="fallback",
                best_score=0.0,
                model_url=None,
                embed_url=None,
                render_type="glb",
                name=query.title(),
                explanation=f"Generation failed: {fallback_res.get('error')}",
                all_results=all_formatted,
                latency_ms=result.get("_latency_ms", 0),
            )

    # ── Retrieved mode ────────────────────────────────────────────────────
    #
    # The top-level fields (render_type, embed_url, model_url, name) control
    # what the frontend shows in the main viewer. These MUST come from the
    # first result in all_results — which hybrid_search has already ordered
    # with the best Sketchfab embeddable result on top.
    #
    # Previously, find_best_renderable() re-scanned and could pick a
    # different result, overriding the Sketchfab-first ordering. REMOVED.

    if all_formatted:
        top_result = all_formatted[0]
        render_type = top_result.render_type or "info_card"
        embed_url   = top_result.embed_url
        model_url   = top_result.model_url
        page_url    = top_result.model_page_url
        name        = top_result.name
    else:
        render_type = "info_card"
        embed_url   = None
        model_url   = None
        page_url    = None
        name        = query.title()

    # Build explanation based on source
    if all_formatted and all_formatted[0].api_source == "sketchfab":
        explanation = f"Best match from Sketchfab — interactive 3D embed."
    else:
        explanation = "Retrieved from vector database."

    print(
        f"[response] '{query}' → render={render_type} "
        f"source={all_formatted[0].api_source if all_formatted else 'none'} "
        f"name='{name}'"
    )

    return QueryResponse(
        mode="retrieved",
        confidence_tier=tier,
        best_score=best_score,
        model_url=model_url,
        embed_url=embed_url,
        model_page_url=page_url,
        render_type=render_type,
        name=name,
        explanation=explanation,
        all_results=all_formatted,
        latency_ms=result.get("_latency_ms", 0),
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status":         "ok",
        "domains_loaded": list(indexes.keys()),
        "model_counts":   {d: indexes[d].ntotal for d in indexes},
        "faiss_model":    "all-MiniLM-L6-v2 (384-dim)",
        "reranker":       "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "threshold":      CONFIDENCE_THRESHOLD,
    }


@app.get("/domains")
def get_domains():
    return {
        "domains": [
            {"name": d, "model_count": indexes[d].ntotal}
            for d in indexes
        ]
    }


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """
    MAIN ENDPOINT — user just types anything.
    Domain is classified automatically, search happens silently.
    """
    domain = classify_domain(req.query)
    print(f"[query] '{req.query}' → domain: '{domain}'")

    result = await run_in_threadpool(hybrid_search, req.query, domain, req.top_k)
    return await build_response(req.query, result)


@app.post("/search", response_model=QueryResponse)
async def debug_search(req: DebugSearchRequest):
    """
    DEBUG ONLY — manually override domain for testing.
    """
    domain = req.domain.lower()
    if domain not in indexes:
        raise HTTPException(
            status_code=400,
            detail=f"Domain '{domain}' not available. Choose from: {list(indexes.keys())}"
        )

    result = await run_in_threadpool(hybrid_search, req.query, domain, req.top_k)
    return await build_response(req.query, result)


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)