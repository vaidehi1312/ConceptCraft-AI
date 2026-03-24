"""
Flask Server
------------
Hybrid pipeline:

Primary:
    LLM blueprint → morphology → layout engine

Fallback:
    External model retrieval (optional MCP / web models)

The Kaggle server now only handles LLM reasoning,
not GPU mesh generation.
"""
import sys, os, json, dataclasses, base64
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

# ── Set your keys via environment variables, never hardcode ──
# Run Flask as: set GOOGLE_API_KEY=your_key && set KAGGLE_LLM_URL=https://xxx.ngrok-free.app && python server.py
KAGGLE_LLM_URL = os.getenv("KAGGLE_LLM_URL", "").rstrip("/")
if KAGGLE_LLM_URL:
    os.environ["KAGGLE_LLM_URL"] = KAGGLE_LLM_URL

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests as http_requests

from generator import BlueprintGenerator
from validators.semantic_gate import SemanticGate
from validators.blueprint_gate import BlueprintGate
from validators.visual_gate import VisualGate
from engine import LayoutEngine
from morphology_resolver import resolve_morphology
from relational_geometry import apply_relational_geometry

app = Flask(__name__, static_folder="public")
CORS(app)

generator = BlueprintGenerator()
engine = LayoutEngine()

# ── Categories that use Shap-E mesh generation ────────────────────────────────
SHAP_E_CATEGORIES = {"physical_object", "physical_phenomenon"}

# ── Categories that use the LLM blueprint pipeline ───────────────────────────
LLM_CATEGORIES = {"biological_structure", "chemical_structure", "process",
                  "abstract_system", "sequential"}


def call_shap_e(concept: str) -> dict:
    """Call Kaggle /mesh endpoint. Returns {obj: base64_string, format: 'obj'} or raises."""
    kaggle_url = os.environ.get("KAGGLE_LLM_URL", "").rstrip("/")
    if not kaggle_url:
        raise ValueError("KAGGLE_LLM_URL not set — cannot call Shap-E")

    print(f"[shap-e] Requesting mesh for: {concept}")
    resp = http_requests.post(
        f"{kaggle_url}/mesh",
        json={"concept": concept},
        timeout=300  # mesh generation takes ~2 min on T4
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise ValueError(f"Shap-E error: {data['error']}")
    return data


def run_llm_pipeline(concept: str, cleaned_semantic: dict, category: str) -> dict:
    """Existing LLM → blueprint → layout pipeline."""
    # Stage 3: Blueprint Compilation
    raw_blueprint = generator.generate_stage_2(json.dumps(cleaned_semantic))

    # Stage 4: Blueprint Gate
    bp_result = BlueprintGate.execute(raw_blueprint, cleaned_semantic)
    if bp_result["status"] == "reject":
        raise ValueError(f"Blueprint validation failed: {bp_result['issues']}")
    bp_model = bp_result["data"]

    # Stage 5: Visual Gate
    visual_result = VisualGate.execute(bp_model, category)
    if visual_result["status"] == "reject":
        raise ValueError(f"Visual validation failed: {visual_result['issues']}")
    final_bp_model = visual_result["data"]

    # Stage 6: Morphology Resolution
    resolved_blueprint_dict = resolve_morphology(dataclasses.asdict(final_bp_model), cleaned_semantic)

    # Stage 7: Relational Geometry
    relational_dict = apply_relational_geometry(resolved_blueprint_dict)

    # Stage 8-9: Layout Engine
    updated_components = list(final_bp_model.geometric_components)
    relational_lookup = {
        rc["id"]: rc for rc in relational_dict.get("geometric_components", [])
    }
    for c in updated_components:
        match = relational_lookup.get(c.id)
        if match:
            c.resolved_shape = match.get("resolved_shape") or c.shape
            c.scale_hint     = match.get("scale_hint", (1.0, 1.0, 1.0))
            c.color_hint     = match.get("color_hint", "neutral")
            c.layout_hint    = match.get("layout_hint", "none")

    temp_model = dataclasses.replace(
        final_bp_model,
        geometric_components=updated_components,
        morphology_family=relational_dict.get("morphology_family"),
        morphology_params=relational_dict.get("morphology_params"),
        connectors=relational_dict.get("connectors", [])
    )

    result_json_str = engine.generate_layout(
        json.dumps(dataclasses.asdict(temp_model)),
        scenario_name=concept,
        category=category
    )
    result_dict = json.loads(result_json_str)

    # Merge resolved_shape back
    for comp in result_dict.get("components", []):
        comp_id = comp.get("original_id") or comp.get("id", "")
        if not comp.get("resolved_shape") and comp_id in relational_lookup:
            comp["resolved_shape"] = relational_lookup[comp_id].get("resolved_shape") or "sphere"

    # Merge explanations
    result_explanations = result_dict.get("explanations", {}) or {}
    if isinstance(result_explanations, dict):
        if not result_dict.get("intro"):
            result_dict["intro"] = result_explanations.get("intro", "")
        if not result_dict.get("layout_logic"):
            result_dict["layout_logic"] = result_explanations.get("layout_logic", "")

    if not result_dict.get("intro") or not result_dict.get("layout_logic"):
        explanations = getattr(final_bp_model, "explanations", None) or {}
        if isinstance(explanations, dict):
            if not result_dict.get("intro"):
                result_dict["intro"] = explanations.get("intro", "")
            if not result_dict.get("layout_logic"):
                result_dict["layout_logic"] = explanations.get("layout_logic", "")

    # Morphology scoring
    morph_score = VisualGate.score_morphological_recognizability(result_dict)
    if morph_score["repairs"]:
        print(f"[~] Morphology repairs: {morph_score['repairs']}")

    result_dict["render_mode"] = "blueprint"
    return result_dict


@app.route("/")
def index():
    return send_from_directory("public", "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory("public", filename)

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    concept = data.get("concept", "").strip()
    print(f"[SERVER] Received concept: {concept}")
    if not concept:
        return jsonify({"error": "No concept provided"}), 400

    try:
        # Stage 1: Semantic Decomposition (always runs — determines routing)
        raw_semantic_json = generator.generate_stage_1(concept)

        # Stage 2: Semantic Gate
        semantic_result = SemanticGate.execute(raw_semantic_json)
        if semantic_result["status"] == "reject":
            return jsonify({"error": f"Semantic validation failed: {semantic_result['issues']}"}), 400
        cleaned_semantic = semantic_result["data"]
        category = cleaned_semantic.get("category", "abstract_system")

        print(f"[SERVER] Category: {category}")

        # ── ROUTING DECISION ──────────────────────────────────────────────────
        use_shap_e = category in SHAP_E_CATEGORIES

        if use_shap_e:
            print(f"[SERVER] Routing to Shap-E mesh pipeline")
            try:
                mesh_data = call_shap_e(concept)
                result_dict = {
                    "render_mode": "mesh",
                    "scenario": concept,
                    "category": category,
                    "obj": mesh_data["obj"],   # base64 encoded OBJ file
                    "format": "obj",
                    "intro": cleaned_semantic.get("concept_description", ""),
                    "layout_logic": cleaned_semantic.get("spatial_logic", ""),
                    "pattern": "mesh",
                    "components": [],
                    "connectors": []
                }
            except Exception as mesh_err:
                print(f"[SERVER] Shap-E failed: {mesh_err} — falling back to LLM pipeline")
                result_dict = run_llm_pipeline(concept, cleaned_semantic, category)
        else:
            print(f"[SERVER] Routing to LLM blueprint pipeline")
            result_dict = run_llm_pipeline(concept, cleaned_semantic, category)

        # Write output.json for Three.js
        out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public", "output.json")
        with open(out_file, "w") as f:
            json.dump(result_dict, f, indent=2)

        return jsonify({"status": "success", "data": result_dict})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("\n🚀 ConceptCraftAI Server running at http://localhost:5000\n")
    print(f"   Shap-E categories: {SHAP_E_CATEGORIES}")
    print(f"   LLM categories:    {LLM_CATEGORIES}\n")
    app.run(debug=True, port=5000)