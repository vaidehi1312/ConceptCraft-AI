"""
Flask Server
------------
Exposes the full pipeline as a REST API so the browser frontend
can send a concept and receive 3D coordinates.
"""
import sys, os, json, dataclasses
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
os.environ["GOOGLE_API_KEY"] = "AIzaSyCz8oA06Yiev-eueP0jgRGZ0V5eHK0lY_s"

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

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
        # Stage 1: Semantic Decomposition
        raw_semantic_json = generator.generate_stage_1(concept)

        # Stage 2: Semantic Gate
        semantic_result = SemanticGate.execute(raw_semantic_json)
        if semantic_result["status"] == "reject":
            return jsonify({"error": f"Semantic validation failed: {semantic_result['issues']}"}), 400
        cleaned_semantic = semantic_result["data"]
        category = cleaned_semantic.get("category", "abstract_system")

        # Stage 3: Blueprint Compilation
        raw_blueprint = generator.generate_stage_2(json.dumps(cleaned_semantic))

        # Stage 4: Blueprint Gate
        bp_result = BlueprintGate.execute(raw_blueprint, cleaned_semantic)
        if bp_result["status"] == "reject":
            return jsonify({"error": f"Blueprint validation failed: {bp_result['issues']}"}), 400
        bp_model = bp_result["data"]

        # Stage 5: Visual Gate
        visual_result = VisualGate.execute(bp_model, category)
        if visual_result["status"] == "reject":
            return jsonify({"error": f"Visual validation failed: {visual_result['issues']}"}), 400
        final_bp_model = visual_result["data"]

        # Stage 6: Morphology Resolution
        resolved_blueprint_dict = resolve_morphology(dataclasses.asdict(final_bp_model), cleaned_semantic)

        # Stage 7: Relational Geometry
        relational_dict = apply_relational_geometry(resolved_blueprint_dict)

        # Stage 8-9: Layout Engine — carry resolved_shape + hints from relational_dict into components
        updated_components = list(final_bp_model.geometric_components)

        # Build a lookup so we can patch resolved_shape onto components before layout
        relational_lookup = {
            rc["id"]: rc
            for rc in relational_dict.get("geometric_components", [])
        }

        for c in updated_components:
            match = relational_lookup.get(c.id)
            if match:
                c.resolved_shape = match.get("resolved_shape") or c.shape
                c.scale_hint    = match.get("scale_hint", (1.0, 1.0, 1.0))
                c.color_hint    = match.get("color_hint", "neutral")
                c.layout_hint   = match.get("layout_hint", "none")

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

        # ── FIX 1: Merge resolved_shape back into result_dict components ──────
        # engine.generate_layout() rebuilds components from scratch; resolved_shape
        # is lost unless we stitch it back from relational_lookup.
        for comp in result_dict.get("components", []):
            comp_id = comp.get("original_id") or comp.get("id", "")
            if not comp.get("resolved_shape") and comp_id in relational_lookup:
                comp["resolved_shape"] = relational_lookup[comp_id].get("resolved_shape") or "sphere"

        # ── FIX 2: Merge explanations (intro + layout_logic) into result_dict ─
        # Source priority:
        #   1. result_dict["explanations"] — Gemini now returns this directly in blueprint
        #   2. result_dict["intro"] / result_dict["layout_logic"] — flat fields
        #   3. final_bp_model.explanations — dataclass field fallback

        # Pull from nested explanations dict if engine preserved it
        result_explanations = result_dict.get("explanations", {}) or {}
        if isinstance(result_explanations, dict):
            if not result_dict.get("intro"):
                result_dict["intro"] = result_explanations.get("intro", "")
            if not result_dict.get("layout_logic"):
                result_dict["layout_logic"] = result_explanations.get("layout_logic", "")

        # Final fallback: pull from blueprint model dataclass
        if not result_dict.get("intro") or not result_dict.get("layout_logic"):
            explanations = getattr(final_bp_model, "explanations", None) or {}
            if isinstance(explanations, dict):
                if not result_dict.get("intro"):
                    result_dict["intro"] = explanations.get("intro", "")
                if not result_dict.get("layout_logic"):
                    result_dict["layout_logic"] = explanations.get("layout_logic", "")

        print(f"[explanations] intro={repr(result_dict.get('intro', '')[:60])}")
        print(f"[explanations] layout_logic={repr(result_dict.get('layout_logic', '')[:60])}")

        # Stage 10: Morphology Scoring
        morph_score = VisualGate.score_morphological_recognizability(result_dict)
        if morph_score["repairs"]:
            print(f"[~] Morphology repairs: {morph_score['repairs']}")

        # Write output.json for Three.js
        out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public", "output.json")
        with open(out_file, "w") as f:
            json.dump(result_dict, f, indent=2)

        return jsonify({"status": "success", "data": result_dict})

    except Exception as e:
        import traceback
        traceback.print_exc()          # print full stack trace in terminal
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("\n🚀 ConceptCraftAI Server running at http://localhost:5000\n")
    app.run(debug=True, port=5000)