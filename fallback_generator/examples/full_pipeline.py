"""
Example: Full Pipeline
----------------------
This file is a standalone simulation script that acts as a test bench for the 
entire pipeline, completely bypassing the terminal inputs. It loops through a 
hardcoded set of theoretical concepts to ensure the Classifier and Generator 
can successfully process them without runtime crashes.
"""
import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from generator import BlueprintGenerator
from validator import BlueprintValidator
from engine import LayoutEngine

def run():
    print("Testing Semantic Pipeline")
    generator = BlueprintGenerator()
    engine = LayoutEngine()
    
    concept = "Theoretical Concept Graph"
    raw_blueprint = generator.generate(concept)
    
    is_valid, bp_model, error_msg = BlueprintValidator.validate_and_normalize(raw_blueprint)
    if not is_valid:
        print(f"FAILED: {error_msg}")
        return
        
    print(f"Valid Blueprint: {bp_model.pattern} with {len(bp_model.components)} nodes, {len(bp_model.relations)} edges.")
    
    result_json = engine.generate_layout(json.dumps(bp_model.__dict__, default=lambda o: o.__dict__), scenario_name=concept)
    
    out_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "output.json")
    with open(out_file, "w") as f:
        f.write(result_json)
        
    print("Coordinates successfully written to output.json")

if __name__ == "__main__":
    run()
