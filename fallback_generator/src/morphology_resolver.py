"""
Morphology Resolver Module
--------------------------
RESPONSIBILITY: 
Determines the physical "style" or "family" of the object based on semantic signals. 
Maps a generic blueprint to concepts like "nested_membrane" or "architectural_assembly".

STAGES HANDLED:
- Stage 6: Morphology Resolution
"""
import copy
from pipeline_contract import (
    VALID_MORPHOLOGY_FAMILIES, VALID_PATTERNS, 
    VALID_CATEGORIES, validate_incoming
)

# ============================================================================
# 1. MORPHOLOGY FAMILIES
# ============================================================================
MORPHOLOGY_FAMILIES = {
    "nested_membrane": {
        "family": "nested_membrane",
        "shell_style": "soft_sphere",
        "interior_density": "sparse",
        "surface_treatment": "smooth",
        "motion_hint": "orbiting",
        "scale_contrast": "dramatic",
        "shape_vocab": {
            "container": "icosphere",
            "central": "sphere",
            "node": "oblate_sphere",
            "source": "torus",
            "sink": "tetrahedron",
            "stage": "capsule",
            "anchor": "box",
            "actor": "oblate_sphere",
            "boundary": "icosphere",
            "default": "sphere"
        }
    },
    "branching_tree": {
        "family": "branching_tree",
        "shell_style": "open",
        "interior_density": "sparse",
        "surface_treatment": "segment",
        "motion_hint": "branching",
        "scale_contrast": "graduated",
        "shape_vocab": {
            "root": "box",
            "node": "capsule",
            "leaf": "tetrahedron",
            "central": "cylinder",
            "source": "box",
            "sink": "sphere",
            "default": "capsule"
        }
    },
    "flow_channel": {
        "family": "flow_channel",
        "shell_style": "porous",
        "interior_density": "void",
        "surface_treatment": "smooth",
        "motion_hint": "flowing",
        "scale_contrast": "uniform",
        "shape_vocab": {
            "node": "cylinder",
            "source": "torus",
            "sink": "box",
            "stage": "capsule",
            "flow_node": "cylinder",
            "valve": "octahedron",
            "default": "cylinder"
        }
    },
    "crystalline_lattice": {
        "family": "crystalline_lattice",
        "shell_style": "rigid_box",
        "interior_density": "packed",
        "surface_treatment": "segmented",
        "motion_hint": "static",
        "scale_contrast": "uniform",
        "shape_vocab": {
            "node": "box",
            "central": "octahedron",
            "anchor": "box",
            "actor": "box",
            "element": "box",
            "default": "box"
        }
    },
    "field_gradient": {
        "family": "field_gradient",
        "shell_style": "soft_sphere",
        "interior_density": "sparse",
        "surface_treatment": "smooth",
        "motion_hint": "pulsing",
        "scale_contrast": "graduated",
        "shape_vocab": {
            "source": "sphere",
            "node": "tetrahedron",
            "force": "octahedron",
            "field_point": "sphere",
            "sink": "torus",
            "default": "sphere"
        }
    },
    "hub_spoke_web": {
        "family": "hub_spoke_web",
        "shell_style": "open",
        "interior_density": "sparse",
        "surface_treatment": "segmented",
        "motion_hint": "static",
        "scale_contrast": "dramatic",
        "shape_vocab": {
            "central": "icosphere",
            "node": "sphere",
            "anchor": "box",
            "peripheral": "tetrahedron",
            "actor": "sphere",
            "default": "sphere"
        }
    },
    "stacked_layers": {
        "family": "stacked_layers",
        "shell_style": "layered",
        "interior_density": "packed",
        "surface_treatment": "smooth",
        "motion_hint": "static",
        "scale_contrast": "uniform",
        "shape_vocab": {
            "layer": "plane",
            "stage": "box",
            "node": "box",
            "anchor": "box",
            "level": "plane",
            "default": "box"
        }
    },
    "dense_aggregate": {
        "family": "dense_aggregate",
        "shell_style": "porous",
        "interior_density": "clustered",
        "surface_treatment": "textured",
        "motion_hint": "flowing",
        "scale_contrast": "graduated",
        "shape_vocab": {
            "node": "sphere",
            "entity": "capsule",
            "cluster": "icosphere",
            "agent": "capsule",
            "default": "sphere"
        }
    },
    "helical_chain": {
        "family": "helical_chain",
        "shell_style": "open",
        "interior_density": "void",
        "surface_treatment": "segmented",
        "motion_hint": "orbiting",
        "scale_contrast": "uniform",
        "shape_vocab": {
            "node": "cylinder",
            "base": "box",
            "link": "capsule",
            "stage": "cylinder",
            "default": "cylinder"
        }
    },
    "modular_grid": {
        "family": "modular_grid",
        "shell_style": "rigid_box",
        "interior_density": "packed",
        "surface_treatment": "smooth",
        "motion_hint": "static",
        "scale_contrast": "graduated",
        "shape_vocab": {
            "node": "box",
            "module": "box",
            "unit": "box",
            "component": "box",
            "default": "box"
        }
    },
    "architectural_assembly": {
        "family": "architectural_assembly",
        "description": "Physical constructed objects with clear structural hierarchy",
        "shell_style": "rigid_box",
        "interior_density": "sparse",
        "surface_treatment": "segmented",
        "motion_hint": "static",
        "scale_contrast": "dramatic",
        "shape_vocab": {
            "central": "box",
            "cap": "icosphere",
            "dome": "icosphere",
            "tower": "cylinder",
            "peripheral": "cylinder",
            "anchor": "box",
            "base": "box",
            "platform": "box",
            "wall": "box",
            "arch": "torus_section",
            "spire": "cone",
            "node": "box",
            "default": "box"
        }
    },
    "process_sequence": {
        "family": "process_sequence",
        "description": "Ordered steps or stages in a process, pipeline, or workflow",
        "shell_style": "open",
        "interior_density": "sparse",
        "surface_treatment": "segmented",
        "motion_hint": "flowing",
        "scale_contrast": "graduated",
        "shape_vocab": {
            "source": "sphere",
            "step": "box",
            "node": "cylinder",
            "sink": "sphere",
            "process": "box",
            "input": "cone",
            "output": "cone",
            "stage": "box",
            "gate": "box",
            "default": "box"
        }
    },
    "symbolic_abstract": {
        "family": "symbolic_abstract",
        "description": "Abstract concepts, forces, ideas, or systems with no physical form",
        "shell_style": "porous",
        "interior_density": "clustered",
        "surface_treatment": "smooth",
        "motion_hint": "pulsing",
        "scale_contrast": "uniform",
        "shape_vocab": {
            "concept": "icosphere",
            "force": "tetrahedron",
            "node": "sphere",
            "relation": "torus",
            "central": "icosphere",
            "peripheral": "tetrahedron",
            "anchor": "octahedron",
            "default": "sphere"
        }
    }
}

# ============================================================================
# 2. SCORING TABLES
# ============================================================================

# Weight 3 — Pattern is the strongest signal
PATTERN_SCORES = {
    "central_peripheral": {"nested_membrane": 3},
    "network": {"hub_spoke_web": 3},
    "hierarchical": {"branching_tree": 3, "stacked_layers": 3},
    "radial": {"hub_spoke_web": 3},
    "field": {"field_gradient": 3, "dense_aggregate": 3},
    "linear": {"flow_channel": 3, "helical_chain": 3},
    "grid": {"crystalline_lattice": 3, "modular_grid": 3}
}

# Weight 2 — Category+Pattern combo refines the choice
CATEGORY_PATTERN_SCORES = {
    ("biological_structure", "central_peripheral"): {"nested_membrane": 2},
    ("biological_structure", "hierarchical"): {"branching_tree": 2},
    ("biological_structure", "linear"): {"flow_channel": 2},
    ("biological_structure", "network"): {"hub_spoke_web": 2},
    ("abstract_system", "network"): {"hub_spoke_web": 2},
    ("abstract_system", "hierarchical"): {"stacked_layers": 2},
    ("process", "network"): {"hub_spoke_web": 2},
    ("process", "linear"): {"flow_channel": 2, "process_sequence": 2},
    ("chemical_structure", "field"): {"crystalline_lattice": 2},
    ("chemical_structure", "linear"): {"helical_chain": 2},
    ("physical_phenomenon", "field"): {"field_gradient": 2},
    ("physical_object", "hierarchical"): {"stacked_layers": 2, "architectural_assembly": 2},
    ("physical_object", "central_peripheral"): {"architectural_assembly": 2},
}

# Category-level bonuses and penalties (applied independently of pattern)
CATEGORY_SCORES = {
    "physical_object": {
        "architectural_assembly": 4,
        "nested_membrane": -3,
        "flow_channel": -2,
        "dense_aggregate": -1,
        "symbolic_abstract": -3,
    },
    "biological_structure": {
        "nested_membrane": 3,
        "flow_channel": 2,
        "branching_tree": 1,
        "architectural_assembly": -3,
        "symbolic_abstract": -3,
    },
    "process": {
        "process_sequence": 4,
        "flow_channel": 2,
        "stacked_layers": 1,
    },
    "abstract_system": {
        "symbolic_abstract": 4,
        "hub_spoke_web": 2,
        "field_gradient": 1,
    },
    "chemical_structure": {
        "crystalline_lattice": 3,
        "helical_chain": 2,
        "architectural_assembly": -3,
    },
    "physical_phenomenon": {
        "field_gradient": 3,
        "symbolic_abstract": 2,
    },
}

# Weight 1-2 each — Scan entity IDs for keywords
ENTITY_KEYWORD_SCORES = {
    "nested_membrane": ["membrane", "cell", "nucleus", "organelle", "cytoplasm", "vesicle", "atom", "shell", "kernel"],
    "flow_channel": ["tubule", "duct", "vessel", "canal", "loop", "flow", "artery", "vein", "capillary", "nephron", "henle"],
    "hub_spoke_web": ["producer", "consumer", "predator", "prey", "decomposer", "trophic", "web", "network", "hub", "server", "client", "router"],
    "stacked_layers": ["layer", "stratum", "tier", "level", "stack", "crust", "mantle", "core", "epidermis", "dermis"],
    "branching_tree": ["branch", "root", "leaf", "trunk", "fork", "hierarchy", "parent", "child", "evolution", "phylo"],
    "helical_chain": ["helix", "chain", "strand", "sequence", "dna", "rna", "amino", "polymer", "coil", "spiral"],
    "crystalline_lattice": ["crystal", "lattice", "bond", "ion", "molecule", "salt", "diamond", "unit_cell"],
    "dense_aggregate": ["cluster", "aggregate", "colony", "swarm", "crowd", "granule", "sediment", "soil"],
    "field_gradient": ["field", "gradient", "wave", "potential", "charge", "magnetic", "electric"],
    "modular_grid": ["module", "grid", "chip", "circuit", "processor", "block", "tile", "panel", "board"],
}

# Weight 2 per match — Architecture/Process/Abstract keyword scanning
ARCHITECTURAL_KEYWORDS = [
    "dome", "mausoleum", "tower", "minaret", "pillar", "column", "arch",
    "facade", "spire", "nave", "vault", "buttress", "portico", "platform",
    "base", "foundation", "wall", "roof", "floor", "ceiling", "gate", "portal",
    "temple", "cathedral", "pyramid", "bridge", "monument", "chamber"
]
PROCESS_KEYWORDS = [
    "step", "stage", "phase", "process", "pipeline", "workflow",
    "input", "output", "transform", "convert", "produce", "digest",
    "absorb", "react", "synthesize", "assemble", "filter"
]
ABSTRACT_KEYWORDS = [
    "concept", "idea", "force", "power", "system", "theory",
    "principle", "law", "value", "belief", "norm", "justice",
    "freedom", "equality", "democracy", "entropy", "consciousness"
]

RELATION_SCORES = {
    "contains": {"nested_membrane": 1, "dense_aggregate": 1},
    "flows_to": {"flow_channel": 1, "helical_chain": 1},
    "influences": {"field_gradient": 1, "hub_spoke_web": 1},
    "attached_to": {"crystalline_lattice": 1, "modular_grid": 1},
    "depends_on": {"stacked_layers": 1, "branching_tree": 1},
    "supports": {"stacked_layers": 1, "branching_tree": 1},
    "regulates": {"hub_spoke_web": 1}
}

CONTRAST_TIEBREAKER = {
    "dramatic": 4,
    "graduated": 3,
    "uniform": 2,
    "inverted": 1
}

# ============================================================================
# 3. RESOLVER FUNCTION
# ============================================================================
def get_scale_hint(size_hint: str, contrast: str) -> tuple:
    """Calculates a base tuple scale multiplier based on contrast rules."""
    base_map = {"small": 0.5, "medium": 1.0, "large": 2.0, "extra_large": 4.0}
    val = base_map.get(size_hint, 1.0)
    
    if contrast == "dramatic":
        if size_hint == "large": val *= 1.5
        if size_hint == "small": val *= 0.5
    elif contrast == "uniform":
        val = 1.0
    elif contrast == "inverted":
        val = 1.0 / val
        
    return (val, val, val)

def resolve_morphology(blueprint: dict, semantic_json: dict) -> dict:
    """
    Pure function to resolve morphology identity based on semantic cues.
    Uses a weighted scoring system: pattern (3) > category+pattern (2) > entity keywords (1).
    """
    validate_incoming(blueprint, "MorphologyResolver (blueprint)", ["pattern", "geometric_components", "semantic_relations"])
    validate_incoming(semantic_json, "MorphologyResolver (semantic)", ["category", "dominant_pattern"])
    
    out_bp = copy.deepcopy(blueprint)
    
    # 1. Extract Signals
    pattern = blueprint.get("pattern", semantic_json.get("pattern", "unknown"))
    category = semantic_json.get("category", "unknown")
    
    entity_ids = [c.get("id", "") for c in blueprint.get("geometric_components", [])]
    relations = [r.get("relation_type", r.get("type", "unknown")) for r in blueprint.get("semantic_relations", [])]
    
    # 2. Score Families
    scores = {f: 0 for f in MORPHOLOGY_FAMILIES.keys()}
    
    # Weight 3: Pattern signal
    for f, score in PATTERN_SCORES.get(pattern, {}).items():
        scores[f] += score
    
    # Weight 2: Category + Pattern combo signal
    for f, score in CATEGORY_PATTERN_SCORES.get((category, pattern), {}).items():
        scores[f] += score
    
    # Category-level bonuses and penalties (independent of pattern)
    for f, score in CATEGORY_SCORES.get(category, {}).items():
        if f in scores:
            scores[f] += score
        
    # Weight 1: Entity ID keyword scanning
    all_ids_str = " ".join(entity_ids).lower()
    for family, keywords in ENTITY_KEYWORD_SCORES.items():
        for kw in keywords:
            if kw in all_ids_str:
                scores[family] += 1
    
    # Weight 2: Architectural keyword scanning
    for kw in ARCHITECTURAL_KEYWORDS:
        if kw in all_ids_str:
            scores["architectural_assembly"] += 2
    
    # Weight 2: Process keyword scanning
    for kw in PROCESS_KEYWORDS:
        if kw in all_ids_str:
            scores["process_sequence"] += 2
    
    # Weight 2: Abstract keyword scanning
    for kw in ABSTRACT_KEYWORDS:
        if kw in all_ids_str:
            scores["symbolic_abstract"] += 2
            
    # Weight 1: Relation type signal
    for rel in relations:
        for f, score in RELATION_SCORES.get(rel, {}).items():
            scores[f] += score
            
    # 3. Print top-3 scored families for debugging
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top3 = sorted_scores[:3]
    print(f"      [MORPHOLOGY TOP-3]: {', '.join(f'{name}={score}' for name, score in top3)}")
    
    # 4. Find Best Match (with Tie-Breaker)
    best_family = "modular_grid"  # Ultimate fallback
    best_score = -1
    
    for family, score in scores.items():
        if score > best_score:
            best_family = family
            best_score = score
        elif score == best_score and score > 0:
            # Tie breaker: Higher diversity contrast wins
            c_current = CONTRAST_TIEBREAKER[MORPHOLOGY_FAMILIES[best_family]["scale_contrast"]]
            c_candidate = CONTRAST_TIEBREAKER[MORPHOLOGY_FAMILIES[family]["scale_contrast"]]
            if c_candidate > c_current:
                best_family = family

    # 5. Apply Morphology to Blueprint
    family_params = MORPHOLOGY_FAMILIES[best_family]
    out_bp["morphology_family"] = best_family
    out_bp["morphology_params"] = family_params
    
    vocab = family_params["shape_vocab"]
    contrast = family_params["scale_contrast"]
    
    for comp in out_bp.get("geometric_components", []):
        role = comp.get("role", "node")
        comp["resolved_shape"] = vocab.get(role, vocab.get("default", "box"))
        
        # Calculate scale hint
        size_hint = comp.get("size_hint", "medium")
        comp["scale_hint"] = get_scale_hint(size_hint, contrast)
        
    return out_bp

# ============================================================================
# 4. TESTS
# ============================================================================
if __name__ == "__main__":
    def run_test(name, semantic, blueprint):
        res = resolve_morphology(blueprint, semantic)
        print(f"--- TEST: {name} ---")
        print(f"Resolved Family: {res['morphology_family']}")
        print(f"Shape Vocab: {res['morphology_params']['shape_vocab']}")
        print()

    # 1. Animal Cell
    run_test("Animal Cell", 
             {"category": "biological_structure", "pattern": "radial"},
             {"pattern": "radial", 
              "geometric_components": [{"semantic_type": "cell", "role": "container"}, {"semantic_type": "organ", "role": "central"}],
              "semantic_relations": [{"relation_type": "contains"}]}
    )
    
    # 2. Evolutionary Tree
    run_test("Evolutionary Tree",
             {"category": "organization", "pattern": "hierarchical"},
             {"pattern": "hierarchical",
              "geometric_components": [{"semantic_type": "institution", "role": "root"}, {"semantic_type": "actor", "role": "node"}],
              "semantic_relations": [{"relation_type": "depends_on"}]}
    )
    
    # 3. TCP/IP Stack
    run_test("TCP/IP Stack",
             {"category": "technology", "pattern": "linear"},
             {"pattern": "linear",
              "geometric_components": [{"semantic_type": "layer", "role": "level"}],
              "semantic_relations": [{"relation_type": "supports"}]}
    )
    
    # 4. Social Network
    run_test("Social Network",
             {"category": "technology", "pattern": "network"},
             {"pattern": "network",
              "geometric_components": [{"semantic_type": "actor", "role": "node"}],
              "semantic_relations": [{"relation_type": "influences"}]}
    )
    
    # 5. DNA Replication
    run_test("DNA Replication",
             {"category": "biological_structure", "pattern": "linear"},
             {"pattern": "linear",
              "geometric_components": [{"semantic_type": "chemical_unit", "role": "node"}],
              "semantic_relations": [{"relation_type": "flows_to"}]}
    )
