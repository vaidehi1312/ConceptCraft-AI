"""
Main Entry Point
----------------
RESPONSIBILITY: 
Ties all pipeline modules together into an interactive CLI flow. 
Prompts for concepts, triggers LLMs, executes gates/engines, 
and exports final data to `public/output.json`.

STAGES HANDLED:
- Full Pipeline Orchestration (Stages 1-10)
"""
import sys
import os
import json
import dataclasses

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from generator import BlueprintGenerator
from validators.semantic_gate import SemanticGate
from validators.blueprint_gate import BlueprintGate
from validators.visual_gate import VisualGate
from engine import LayoutEngine

def main():
    print("\n=======================================================")
    print("🚀 CONCEPT CRAFT AI: 3D Visualization Pipeline Active")
    print("=======================================================\n")
    print("Type 'exit' or 'quit' to stop.\n")

    generator = BlueprintGenerator()
    engine = LayoutEngine()
    
    while True:
        try:
            concept = input(">> Enter a Concept to Visualize: ").strip()
            if not concept:
                continue
            if concept.lower() in ['exit', 'quit']:
                print("Goodbye!")
                break
                
            print(f"\n[1/6] Semantic Decomposition (Stage 1 LLM Request)...")
            raw_semantic_json = generator.generate_stage_1(concept)
            print(f"      [STAGE 1 RAW SEMANTIC JSON]:\n{raw_semantic_json}")
            
            print(f"\n[2/6] Semantic Gate...")
            semantic_result = SemanticGate.execute(raw_semantic_json)
            if semantic_result["status"] == "reject":
                print(f"      [!] ERROR: Semantic validation failed: {semantic_result['issues']}")
                continue
            elif semantic_result["status"] == "repair":
                print(f"      [~] Partially repaired semantic proposal: {semantic_result['issues']}")
            cleaned_semantic = semantic_result["data"]
            category = cleaned_semantic.get("category", "abstract_system")
            print(f"      [AFTER SEMANTIC REPAIR]:\n{json.dumps(cleaned_semantic, indent=2)}")
                
            print(f"\n[3/6] Blueprint Compilation (Stage 2 LLM Request)...")
            raw_blueprint = generator.generate_stage_2(json.dumps(cleaned_semantic))
            print(f"      [STAGE 2 RAW BLUEPRINT JSON]:\n{raw_blueprint}")
            
            print(f"\n[4/6] Blueprint Gate...")
            bp_result = BlueprintGate.execute(raw_blueprint, cleaned_semantic)
            if bp_result["status"] == "reject":
                print(f"      [!] ERROR: Blueprint structural validation failed: {bp_result['issues']}")
                continue
            elif bp_result["status"] == "repair":
                print(f"      [~] Rescued Blueprint structure: {bp_result['issues']}")
            bp_model = bp_result["data"]
            print(f"      [AFTER BLUEPRINT REPAIR (Summary)]:")
            print(f"        Pattern: {bp_model.pattern}")
            print(f"        Components count: {len(bp_model.geometric_components)}")
            print(f"        Relations count: {len(bp_model.semantic_relations)}")
            
            print(f"\n[5/10] Visual Gate (Topology Scoring)...")
            visual_result = VisualGate.execute(bp_model, category)
            print(f"      [BLUEPRINT SCORE]: {visual_result['score']}")
            if visual_result["status"] == "reject":
                print(f"      [!] ERROR: Blueprint visually rejected (Score: {visual_result['score']}): {visual_result['issues']}")
                continue
            elif visual_result["status"] == "repair":
                print(f"      [~] Visually repaired blueprint (Score: {visual_result['score']}): {visual_result['issues']}")
            elif visual_result["status"] == "accept":
                print(f"      [✓] Blueprint visually perfect (Score: {visual_result['score']}).")
            final_bp_model = visual_result["data"]
            
            print(f"\n[6/10] Morphology Resolution...")
            from morphology_resolver import resolve_morphology
            resolved_blueprint_dict = resolve_morphology(dataclasses.asdict(final_bp_model), cleaned_semantic)
            print(f"      [RESOLVED FAMILY]: {resolved_blueprint_dict.get('morphology_family')}")
            
            print(f"\n[7/10] Relational Geometry Pass...")
            from relational_geometry import apply_relational_geometry
            relational_dict = apply_relational_geometry(resolved_blueprint_dict)
            print(f"      [CONNECTORS GENERATED]: {len(relational_dict.get('connectors', []))}")
            
            
            print(f"\n[8/10] Layout Engine Selector & Resolution...")
            selected_eng, eng_name, effective_pattern, override_reason = engine.select_layout_engine(final_bp_model, category)
            
            print(f"      Blueprint Pattern (Provisional): {final_bp_model.pattern.upper()}")
            if override_reason:
                print(f"      [~] Stage B Override: {effective_pattern.upper()} ({override_reason})")
            print(f"      [CHOSEN LAYOUT ENGINE (Pre-Bridge)]: {eng_name}")
            
            print(f"\n      --- CONCEPT INTRO ---")
            print(f"      {final_bp_model.explanations.intro}")
            
            # Build a properly-populated Blueprint with morphology + relational geometry data.
            # Use dataclasses.replace so all fields survive asdict() serialization.
            updated_components = list(final_bp_model.geometric_components)
            for c in updated_components:
                match = next((rc for rc in relational_dict.get("geometric_components", []) if rc["id"] == c.id), None)
                if match:
                    c.resolved_shape = match.get("resolved_shape", c.shape)
                    c.scale_hint = match.get("scale_hint", (1.0, 1.0, 1.0))
                    c.color_hint = match.get("color_hint", "neutral")
                    c.layout_hint = match.get("layout_hint", "none")

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
            
            print(f"\n[9/10] Layout Morphology Bridge (Coordinates Generated)")
            result_dict = json.loads(result_json_str)
            print(f"      [GENERATED COMPONENTS]: {len(result_dict.get('components', []))}")
            print(f"      [GENERATED CONNECTORS]: {len(result_dict.get('connectors', []))}")
            
            print(f"\n[10/10] Visual Gate (Morphology Scoring)...")
            morph_score = VisualGate.score_morphological_recognizability(result_dict)
            print(f"      [MORPHOLOGY SCORE]: {morph_score['score']}")
            if morph_score["issues"]:
                print(f"      [~] Issues Detected: {morph_score['issues']}")
            if morph_score["repairs"]:
                print(f"      [~] Repairs Applied: {morph_score['repairs']}")
                
            if morph_score["score"] < 0.5:
                print(f"      [!] WARNING: LOW_RECOGNIZABILITY after repairs.")
                
            # Export to public folder for Three.js
            out_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "output.json")
            with open(out_file, "w") as f:
                json.dump(result_dict, f, indent=2)
                
            print(f"\n[✓] SUCCESS: Coordinates written! View them in the browser at http://localhost:8000")
            print("=======================================================\n")
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\n[!] Pipeline Error: {e}\n")

if __name__ == "__main__":
    main()
