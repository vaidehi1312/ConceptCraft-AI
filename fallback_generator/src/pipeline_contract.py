"""
Pipeline Data Contract
----------------------
RESPONSIBILITY: 
The single source of truth for all data passed between pipeline stages. 
Defines valid categories, shapes, patterns, and roles. Every stage uses 
this contract to validate its input and guarantee its output.
"""

STAGE_CONTRACTS = {

    "semantic_decomposition": {
        "produces": {
            "category": "str — one of VALID_CATEGORIES",
            "dominant_pattern": "str — one of VALID_PATTERNS", 
            "hybrid_needed": "bool",
            "entities": "list of {id:str, count:int, priority:str}",
            "relations": "list of {source:str, target:str, type:str, primary:bool}"
        }
    },

    "blueprint_compilation": {
        "consumes": "semantic_decomposition output",
        "produces": {
            "pattern": "str",
            "geometric_components": """list of {
                id: str,
                semantic_type: str,
                label: str,
                shape: one of VALID_SHAPES,
                role: one of VALID_ROLES,
                count: int,
                size_hint: one of VALID_SIZE_HINTS,
                vertical_relation: one of VALID_VERTICAL_RELATIONS,
                importance: one of [high, medium, low]
            }""",
            "semantic_relations": "list of {source:str, target:str, type:str}",
            "groups": "list",
            "structure": "dict",
            "constraints": "dict"
        }
    },

    "morphology_resolution": {
        "consumes": "blueprint_compilation output + semantic_decomposition output",
        "produces": {
            "morphology_family": "str — one of VALID_MORPHOLOGY_FAMILIES",
            "morphology_params": "dict — full family definition"
        },
        "adds_to_components": {
            "resolved_shape": "str — shape from family shape_vocab",
            "scale_hint": "tuple (sx, sy, sz)"
        }
    },

    "relational_geometry": {
        "consumes": "blueprint after morphology resolution",
        "produces": {
            "connectors": "list of {id, from_id, to_id, type, shape, width, color_hint, taper_ratio}"
        },
        "modifies_components": {
            "color_hint": "str",
            "layout_hint": "str — one of VALID_LAYOUT_HINTS",
            "scale_modifier": "float — multiplier applied on top of scale_hint"
        }
    },

    "layout": {
        "consumes": "blueprint after relational geometry",
        "produces": {
            "components": """list of {
                id: str,
                position: [x, y, z],
                rotation: [rx, ry, rz],
                scale: [sx, sy, sz],
                resolved_shape: str,
                color_hint: str,
                label: str,
                morphology_family: str
            }""",
            "connectors": "list with 3D positions resolved",
            "scene_bounds": "[x, y, z]",
            "morphology_family": "str"
        }
    }
}

# ============================================================
# VALID VALUE ENUMS — imported by all gates and stages
# ============================================================

VALID_CATEGORIES = [
    "biological_structure", "physical_object", "abstract_system",
    "process", "abstract_concept", "social_system", "chemical_structure",
    "information_system", "ecological_system", "astronomical_object","physical_phenomenon"
]

VALID_PATTERNS = [
    "central_peripheral", "hierarchical", "network", "radial",
    "linear", "field", "hybrid"
]

VALID_SHAPES = [
    "sphere", "box", "cylinder", "cone", "torus", "icosphere",
    "capsule", "plane", "tetrahedron", "octahedron", "hemisphere",
    "torus_section", "tapered_cylinder"
]

VALID_ROLES = [
    "central", "peripheral", "anchor", "node", "hub", "spoke",
    "source", "sink", "stage", "cap", "dome", "tower", "base",
    "platform", "layer", "channel", "container", "connector"
]

VALID_SIZE_HINTS = [
    "tiny", "small", "medium", "large", "extra_large", "fills_space"
]

VALID_VERTICAL_RELATIONS = [
    "none", "above", "below", "inside", "contains_vertically", "grounded"
]

VALID_RELATION_TYPES = [
    "contains", "part_of", "supports", "stacked_above", "stacked_below",
    "flows_to", "activates", "inhibits", "regulates", "competes_with",
    "identical_to", "transforms_into", "surrounds"
]

VALID_MORPHOLOGY_FAMILIES = [
    "nested_membrane", "branching_tree", "flow_channel", "crystalline_lattice",
    "field_gradient", "hub_spoke_web", "stacked_layers", "dense_aggregate",
    "helical_chain", "modular_grid", "architectural_assembly",
    "process_sequence", "symbolic_abstract"
]

VALID_LAYOUT_HINTS = [
    "opposing_sides", "mirror_pair", "enclosure", "corner_placement",
    "grounded", "stacked"
]

SIZE_HINT_SCALE = {
    "tiny": 0.35,
    "small": 0.6,
    "medium": 1.0,
    "large": 2.2,
    "extra_large": 3.0,
    "fills_space": 4.0
}

IMPORTANCE_SCALE = {
    "high": 1.8,
    "medium": 1.0,
    "low": 0.6
}

# ============================================================
# VALIDATION HELPER — call this at start of each stage
# ============================================================

def validate_incoming(data: dict, stage_name: str, required_fields: list):
    """
    Call at the start of each stage to verify expected fields are present.
    Logs a warning for each missing field but does not crash.
    """
    if not isinstance(data, dict):
        if hasattr(data, "__dict__"):
            data = data.__dict__
        else:
            return True # Can't validate
            
    missing = [f for f in required_fields if f not in data]
    if missing:
        print(f"      [CONTRACT WARNING] {stage_name} received data missing fields: {missing}")
    return len(missing) == 0
