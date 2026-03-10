"""
Morphology Resolver Module
--------------------------
RESPONSIBILITY: 
Determines the physical "style" or "family" of the object based on semantic signals. 
Maps a generic blueprint to concepts like "nested_membrane" or "architectural_assembly".

FIXES APPLIED:
  1. resolved_shape is NO LONGER unconditionally overwritten.
     If Gemini already set a valid resolved_shape, it is preserved.
     The vocab lookup is only used as a fallback.
  2. semantic_type-based shape override added BEFORE role-based vocab —
     so "vertex"→sphere, "edge/side"→box, "layer/zone"→sphere etc. always win.
  3. Explicit label-keyword override for astronomical/geometric concepts.

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

PATTERN_SCORES = {
    "central_peripheral": {"nested_membrane": 3},
    "network": {"hub_spoke_web": 3},
    "hierarchical": {"branching_tree": 3, "stacked_layers": 3},
    "radial": {"hub_spoke_web": 3},
    "field": {"field_gradient": 3, "dense_aggregate": 3},
    "linear": {"flow_channel": 3, "helical_chain": 3},
    "grid": {"crystalline_lattice": 3, "modular_grid": 3}
}

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
# 3. SEMANTIC-TYPE AND LABEL SHAPE OVERRIDES
# ============================================================================
# These override the vocab lookup when a component's semantic_type or label
# clearly implies a specific shape, regardless of morphology family.
# This prevents the resolver from assigning wrong shapes to well-known types.

# Checked against comp["semantic_type"]
# =====================================================================
# 3. SEMANTIC-TYPE AND LABEL SHAPE OVERRIDES (FIXED)
# =====================================================================

SEMANTIC_TYPE_SHAPE_OVERRIDE = {
    "vertex": "sphere",
    "corner": "sphere",
    "point": "sphere",

    "edge": "cylinder",
    "side": "box",
    "face": "box",

    "layer": "sphere",
    "zone": "sphere",

    "orbit": "torus",
    "ring": "torus",
    "belt": "torus"
}

LABEL_SHAPE_KEYWORDS = {
    "sphere": [
        "sun","star","planet","moon","earth","mars","venus","jupiter",
        "saturn","mercury","uranus","neptune","pluto","nucleus","atom",
        "core","layer","zone","corona","photosphere","radiative",
        "convective","chromosphere","mantle","crust","cell","organelle",
        "proton","neutron","electron","bubble","droplet","globe","orb"
    ],

    "torus": [
        "ring","orbit","orbital","belt","loop","torus",
        "asteroid belt","accretion","saturn ring"
    ],

    "cylinder": [
        "tube","pipe","channel","stem","trunk","column","pillar",
        "rod","axon","vessel","artery","vein","flagella","bond","link"
    ],

    "cone": [
        "cone","pyramid","tip","apex","spire","peak","funnel"
    ],

    "tetrahedron": [
        "triangular","triangle","triangular_face"
    ],

    "box": [
        "side","edge","wall","block","base","platform",
        "building","structure","crystal","lattice","chip","module"
    ]
}
# Valid resolved_shape values that Three.js createShape() accepts
VALID_SHAPES = {
    "sphere", "box", "cylinder", "cone", "torus", "hemisphere",
    "icosphere", "oblate_sphere", "tapered_cylinder", "capsule",
    "wireframe_cube", "branching_fork", "torus_section",
    "octahedron", "tetrahedron"
}


def _infer_shape_from_label(comp: dict) -> str | None:
    """
    Infer shape from component label/id using keyword matching.
    Returns a shape string or None if no match found.
    """
    text = (
        (comp.get("label") or "") + " " +
        (comp.get("id") or "") + " " +
        (comp.get("semantic_type") or "")
    ).lower()

    for shape, keywords in LABEL_SHAPE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return shape
    return None


def _resolve_component_shape(comp: dict, vocab: dict) -> str:
    """
    Determine the final resolved_shape for a component using this priority:

    1. Gemini-provided resolved_shape (if valid and non-empty) — PRESERVE IT
    2. semantic_type override (vertex→sphere, edge→box, layer→sphere etc.)
    3. Label/ID keyword inference (sun→sphere, ring→torus etc.)
    4. Role-based vocab lookup (morphology family shape vocabulary)
    5. Gemini-provided `shape` field (raw, may be correct)
    6. Hard fallback: "sphere"
    """
    def _resolve_component_shape(comp: dict, vocab: dict) -> str:

        existing = (comp.get("resolved_shape") or "").strip().lower()
        if existing and existing in VALID_SHAPES:
            return existing

        sem_type = (comp.get("semantic_type") or "").lower().strip()
        if sem_type in SEMANTIC_TYPE_SHAPE_OVERRIDE:
            return SEMANTIC_TYPE_SHAPE_OVERRIDE[sem_type]

        text = (
            (comp.get("label") or "") + " " +
            (comp.get("id") or "") + " " +
            (comp.get("semantic_type") or "")
            ).lower()

        for shape, keywords in LABEL_SHAPE_KEYWORDS.items():
            if any(k in text for k in keywords):
                return shape

        role = comp.get("role", "node")
        vocab_shape = vocab.get(role, vocab.get("default", "sphere"))
        if vocab_shape in VALID_SHAPES:
            return vocab_shape

        raw_shape = (comp.get("shape") or "").strip().lower()
        if raw_shape in VALID_SHAPES:
            return raw_shape

        return "sphere"


# ============================================================================
# 4. SCALE HINT
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


# ============================================================================
# 5. RESOLVER FUNCTION
# ============================================================================
def resolve_morphology(blueprint: dict, semantic_json: dict) -> dict:
    """
    Pure function to resolve morphology identity based on semantic cues.
    Uses a weighted scoring system: pattern (3) > category+pattern (2) > entity keywords (1).
    
    resolved_shape assignment priority (per component):
      1. Gemini-provided resolved_shape (preserved if valid)
      2. semantic_type override
      3. label/id keyword inference
      4. role-based morphology vocab
      5. raw shape field
      6. sphere fallback
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

    for f, score in PATTERN_SCORES.get(pattern, {}).items():
        scores[f] += score

    for f, score in CATEGORY_PATTERN_SCORES.get((category, pattern), {}).items():
        scores[f] += score

    for f, score in CATEGORY_SCORES.get(category, {}).items():
        if f in scores:
            scores[f] += score

    all_ids_str = " ".join(entity_ids).lower()
    for family, keywords in ENTITY_KEYWORD_SCORES.items():
        for kw in keywords:
            if kw in all_ids_str:
                scores[family] += 1

    for kw in ARCHITECTURAL_KEYWORDS:
        if kw in all_ids_str:
            scores["architectural_assembly"] += 2

    for kw in PROCESS_KEYWORDS:
        if kw in all_ids_str:
            scores["process_sequence"] += 2

    for kw in ABSTRACT_KEYWORDS:
        if kw in all_ids_str:
            scores["symbolic_abstract"] += 2

    for rel in relations:
        for f, score in RELATION_SCORES.get(rel, {}).items():
            scores[f] += score

    # 3. Print top-3 scored families for debugging
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top3 = sorted_scores[:3]
    print(f"      [MORPHOLOGY TOP-3]: {', '.join(f'{name}={score}' for name, score in top3)}")

    # 4. Find Best Match (with Tie-Breaker)
    best_family = "modular_grid"
    best_score = -1

    for family, score in scores.items():
        if score > best_score:
            best_family = family
            best_score = score
        elif score == best_score and score > 0:
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
        # ── FIX: use priority-based shape resolution instead of unconditional overwrite
        comp["resolved_shape"] = _resolve_component_shape(comp, vocab)

        # Calculate scale hint
        size_hint = comp.get("size_hint", "medium")
        comp["scale_hint"] = get_scale_hint(size_hint, contrast)

    return out_bp


# ============================================================================
# 6. TESTS
# ============================================================================
if __name__ == "__main__":
    def run_test(name, semantic, blueprint):
        res = resolve_morphology(blueprint, semantic)
        print(f"--- TEST: {name} ---")
        print(f"Resolved Family: {res['morphology_family']}")
        for c in res["geometric_components"]:
            print(f"  {c.get('id','?'):20} role={c.get('role','?'):12} → resolved_shape={c.get('resolved_shape','?')}")
        print()

    run_test("Animal Cell",
             {"category": "biological_structure", "dominant_pattern": "radial", "pattern": "radial"},
             {"pattern": "radial",
              "geometric_components": [
                  {"id": "cell_membrane", "semantic_type": "container", "role": "container", "label": "Cell Membrane", "shape": "sphere"},
                  {"id": "nucleus", "semantic_type": "organ", "role": "central", "label": "Nucleus", "shape": "sphere"}
              ],
              "semantic_relations": [{"relation_type": "contains"}]})

    run_test("Square (Gemini resolved_shape already set)",
             {"category": "abstract_system", "dominant_pattern": "network", "pattern": "network"},
             {"pattern": "network",
              "geometric_components": [
                  {"id": "vertex", "semantic_type": "vertex", "role": "node", "label": "Vertex", "shape": "sphere", "resolved_shape": "sphere"},
                  {"id": "side", "semantic_type": "edge", "role": "peripheral", "label": "Side", "shape": "box", "resolved_shape": "box"}
              ],
              "semantic_relations": []})

    run_test("Solar System (no resolved_shape set — label inference)",
             {"category": "physical_object", "dominant_pattern": "central_peripheral", "pattern": "central_peripheral"},
             {"pattern": "central_peripheral",
              "geometric_components": [
                  {"id": "sun", "semantic_type": "star", "role": "central", "label": "Sun", "shape": ""},
                  {"id": "planet", "semantic_type": "planet", "role": "peripheral", "label": "Planet", "shape": ""}
              ],
              "semantic_relations": []})