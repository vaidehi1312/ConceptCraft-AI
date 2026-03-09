"""
Example: Taj Mahal
------------------
This script is a pure mocked unit test. It serves as an example of what an 
ideal JSON Blueprint structure looks like for a complex physical object. 
It manually injects the JSON into the Layout engine to test the mathematical 
`corner_based` scaling logic directly logic without waiting for the LLM. 
"""
import sys
import os

# Add src to python path for easy importing
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from engine import LayoutEngine

# The Blueprint specified in the prompt
TAJ_MAHAL_BLUEPRINT = """
{
  "pattern": "central_peripheral",
  "components": [
    {
      "id": "base_platform",
      "shape": "box",
      "role": "central",
      "count": 1,
      "size_hint": "large",
      "vertical_relation": "none"
    },
    {
      "id": "central_dome",
      "shape": "hemisphere",
      "role": "central",
      "count": 1,
      "size_hint": "large",
      "vertical_relation": "above"
    },
    {
      "id": "minaret",
      "shape": "cylinder",
      "role": "peripheral",
      "count": 4,
      "size_hint": "medium",
      "vertical_relation": "above"
    }
  ],
  "structure": {
    "arrangement": "corner_based",
    "levels": [],
    "connections": []
  },
  "constraints": {
    "symmetry": "four_fold",
    "density": "medium"
  }
}
"""

def main():
    engine = LayoutEngine()
    
    print("=== Processing Taj Mahal Blueprint ===")
    try:
        result_json = engine.generate_layout(TAJ_MAHAL_BLUEPRINT, scenario_name="Taj Mahal")
        print("\n=== GENERATED COORDINATES (JSON) ===")
        print(result_json)
        print("====================================")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
