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
from pydantic import BaseModel
from typing import Optional

from search import search_with_confidence, indexes, CONFIDENCE_THRESHOLD

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ConceptCraftAI API",
    description="Type anything — we find the 3D model.",
    version="4.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    source:           Optional[str] = None
    metadata:         dict

class QueryResponse(BaseModel):
    query:            str
    domain:           str
    accepted:         bool
    fallback:         bool
    best_score:       float
    clip_score:       float
    structural_score: float
    faiss_score:      float
    confidence_tier:  str        # "high" | "medium" | "low" | "fallback"
    source_domain:    str        # which FAISS domain the best match came from
    results:          list[ModelResult]


# ── Helper ────────────────────────────────────────────────────────────────────
def format_result(r: dict) -> ModelResult:
    m = r["model"]
    return ModelResult(
        faiss_score      = round(r["faiss_score"],      4),
        clip_score       = round(r["clip_score"],       4),
        structural_score = round(r.get("structural_score", 0.0), 4),
        final_score      = round(r.get("final_score",   r["clip_score"]), 4),
        name             = m.get("name") or m.get("title") or m.get("formula") or "Untitled",
        description      = str(m.get("description") or m.get("summary") or "")[:300],
        thumbnail        = m.get("thumbnail_url") or m.get("thumbnail") or m.get("image_url"),
        embed_url        = m.get("embed_url") or m.get("model_url") or m.get("url"),
        source           = m.get("source") or m.get("hf_dataset") or m.get("source_file"),
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


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    """
    MAIN ENDPOINT — user just types anything.
    Domain is classified automatically, search happens silently.
    """
    domain = classify_domain(req.query)
    print(f"[query] '{req.query}' → domain: '{domain}'")

    result = search_with_confidence(req.query, domain, req.top_k)

    return QueryResponse(
        query            = req.query,
        domain           = domain,
        accepted         = result["accepted"],
        fallback         = result["fallback"],
        best_score       = result["best_score"],
        clip_score       = result["clip_score"],
        structural_score = result["structural_score"],
        faiss_score      = result["faiss_score"],
        confidence_tier  = result.get("confidence_tier", "medium"),
        source_domain    = result.get("source_domain", domain),
        results          = [format_result(r) for r in result["all_results"]]
    )


@app.post("/search", response_model=QueryResponse)
def debug_search(req: DebugSearchRequest):
    """
    DEBUG ONLY — manually override domain for testing.
    """
    domain = req.domain.lower()
    if domain not in indexes:
        raise HTTPException(
            status_code=400,
            detail=f"Domain '{domain}' not available. Choose from: {list(indexes.keys())}"
        )

    result = search_with_confidence(req.query, domain, req.top_k)

    return QueryResponse(
        query            = req.query,
        domain           = domain,
        accepted         = result["accepted"],
        fallback         = result["fallback"],
        best_score       = result["best_score"],
        clip_score       = result["clip_score"],
        structural_score = result["structural_score"],
        faiss_score      = result["faiss_score"],
        confidence_tier  = result.get("confidence_tier", "medium"),
        source_domain    = result.get("source_domain", domain),
        results          = [format_result(r) for r in result["all_results"]]
    )


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
