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
from fastapi.concurrency import run_in_threadpool

from hybrid_search import hybrid_search, indexes, CONFIDENCE_THRESHOLD
from fallback_service import generate_from_concept, get_static_glb_url

app = FastAPI(
    title="ConceptCraftAI API",
    description="Type anything — we find the 3D model.",
    version="4.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # allow everything — fine for local dev
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
    model_page_url:   Optional[str] = None
    source:           Optional[str] = None
    api_source:       Optional[str] = None
    metadata:         dict

class QueryResponse(BaseModel):
    mode: str               # "retrieved" | "fallback"
    confidence_tier: str    # "high" | "medium" | "low" | "fallback"
    best_score: float
    model_url: Optional[str] = None
    embed_url: Optional[str] = None
    render_type: str        # "glb" | "sketchfab_embed" | "shape_recipe"
    name: str
    explanation: str
    all_results: list[ModelResult] = []
    latency_ms: int = 0

import os
import urllib.parse
import re

def get_render_info(model: dict) -> tuple[str, str, str]:
    """
    Returns (render_type, normalized_embed_url, model_url)
    Strict rules:
    1. Sketchfab: if embed_url contains 'sketchfab.com/models'
    2. 3Dmol: if embed_url contains '3dmol.csb.pitt.edu'
    3. Local GLB: if model_url is not None
    """
    raw_url = model.get("embed_url") or model.get("model_url") or model.get("url") or ""
    model_url = model.get("download_url") or None
    
    # 1. Sketchfab ID extraction
    sf_match = re.search(r'([a-f0-9]{32})', raw_url)
    if sf_match and "sketchfab.com" in raw_url:
        return "sketchfab_embed", f"https://sketchfab.com/models/{sf_match.group(1)}/embed", model_url
        
    # 2. 3Dmol / PDB
    if model.get("fetch_url_pdb") or ("3dmol.csb.pitt.edu" in raw_url) or raw_url.endswith(".pdb"):
        pdb_url = model.get("fetch_url_pdb") or raw_url
        # If it's a raw PDB URL, wrap it in 3dmol viewer
        if "3dmol.csb.pitt.edu" not in pdb_url:
            pdb_url = f"https://3dmol.csb.pitt.edu/viewer.html?url={urllib.parse.quote(pdb_url)}&style=stick"
        return "molecule_viewer", pdb_url, model_url
        
    # 3. Local GLB / Direct GLTFLoader (Only if model_url or local_path exists)
    local_path = model.get("local_path", "") or ""
    if (local_path and os.path.exists(local_path)) or model_url:
        return "glb", raw_url, model_url
        
    return "info_card", raw_url, model_url

def find_best_renderable(all_results: list) -> dict:
    for result in all_results:
        rtype, _, _ = get_render_info(result.get("model", {}))
        if rtype != "info_card":
            return result
    return all_results[0] if all_results else None

# ── Helper ────────────────────────────────────────────────────────────────────
def format_result(r: dict) -> ModelResult:
    m = r["model"]
    # Extract best page URL
    page_url = m.get("model_page_url") or m.get("mp_page") or m.get("url") or m.get("embed_url")
    if page_url and not page_url.startswith("http"):
        page_url = None # safety
        
    return ModelResult(
        faiss_score      = round(r.get("faiss_score", 0),      4),
        clip_score       = round(r.get("clip_score", 0),       4),
        structural_score = round(r.get("structural_score", 0.0), 4),
        final_score      = round(r.get("final_score",   r.get("clip_score", 0)), 4),
        name             = m.get("name") or m.get("title") or m.get("formula") or "Untitled",
        description      = str(m.get("description") or m.get("summary") or "")[:300],
        thumbnail        = m.get("thumbnail_url") or m.get("thumbnail") or m.get("image_url"),
        embed_url        = m.get("embed_url") or m.get("model_url") or m.get("url"),
        model_page_url   = page_url,
        source           = m.get("source") or m.get("hf_dataset") or m.get("source_file"),
        api_source       = r.get("_source") or "faiss",
        metadata         = m
    )


# ── Free MiniLM-based domain classifier (no API cost) ───────────────────────
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
    """
    Classify query into one of 4 domains using MiniLM cosine similarity.
    Free, instant, no API calls — MiniLM already loaded at startup.
    """
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


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status":         "ok",
        "domains_loaded": list(indexes.keys()),
        "model_counts":   {d: indexes[d].ntotal for d in indexes},
        "faiss_model":    "all-MiniLM-L6-v2 (384-dim)",
        "reranker":       "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "threshold":      CONFIDENCE_THRESHOLD
    }


@app.get("/domains")
def get_domains():
    return {
        "domains": [
            {"name": d, "model_count": indexes[d].ntotal}
            for d in indexes
        ]
    }


async def build_response(query: str, result: dict) -> QueryResponse:
    tier = result.get("confidence_tier", "medium")
    best_score = result["best_score"]
    all_results = [format_result(r) for r in result.get("all_results", [])]

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
                all_results=all_results,
                latency_ms=result.get("_latency_ms", 0)
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
                all_results=all_results,
                latency_ms=result.get("_latency_ms", 0)
            )
    else:
        best_candidate = find_best_renderable(result.get("all_results", []))
        best_match = best_candidate["model"] if best_candidate else None
        
        embed_url = None
        model_url = None
        render_type = "info_card"
        name = "Unknown"
        
        if best_match:
            name = best_match.get("name") or best_match.get("title") or best_match.get("formula") or "Untitled"
            render_type, embed_url, model_url = get_render_info(best_match)

        return QueryResponse(
            mode="retrieved",
            confidence_tier=tier,
            best_score=best_score,
            model_url=model_url,
            embed_url=embed_url,
            render_type=render_type,
            name=name,
            explanation="Retrieved from vector database.",
            all_results=all_results,
            latency_ms=result.get("_latency_ms", 0)
        )

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
