"""
Relational Geometry Module
--------------------------
RESPONSIBILITY: 
Applies visual styles to relations (connectors, size ratios, color hints). 
Translates abstract relations like "inhibits" into concrete visual rules.

STAGES HANDLED:
- Stage 7: Relational Geometry Pass
"""
import copy
from pipeline_contract import validate_incoming

# ============================================================================
# 1. RELATION VISUAL RULES
# ============================================================================
RELATION_RULES = {
    "contains": {
        "size_ratio": 3.5, 
        "enclosure": True, 
        "connector": "none", 
        "color_hint": "parent_dominant"
    },
    "flows_to": {
        "connector": "tapered_arrow", 
        "color_hint": "gradient_source_to_target", 
        "motion_hint": "directional", 
        "taper_ratio": 0.7
    },
    "inhibits": {
        "connector": "angular_bar", 
        "color_hint": "warning_red", 
        "scale_effect": 0.8
    },
    "activates": {
        "connector": "burst_arrow", 
        "color_hint": "accent_bright", 
        "scale_effect": 1.2
    },
    "supports": {
        "connector": "bracket_base", 
        "color_hint": "neutral_secondary"
    },
    "competes_with": {
        "layout_hint": "opposing_sides", 
        "connector": "double_arrow_opposing", 
        "color_hint": "contrast_pair"
    },
    "identical_to": {
        "layout_hint": "mirror_pair", 
        "connector": "dashed_equal", 
        "scale_effect": "equalize"
    },
    "transforms_into": {
        "connector": "morphing_arrow", 
        "color_hint": "transition_blend"
    },
    "part_of": {
        "size_ratio": 0.5, # parent * 2.0 vs child (inverted here, handled in logic)
        "connector": "thin_line", 
        "color_hint": "parent_subdued"
    },
    "regulates": {
        "connector": "curved_bidirectional", 
        "color_hint": "regulatory_amber"
    },
    "stacked_above": {
        "layout_hint": "stacked_above",
        "connector": "bracket_base",
        "color_hint": "neutral_secondary"
    },
    "stacked_below": {
        "layout_hint": "stacked_below",
        "connector": "bracket_base",
        "color_hint": "neutral_secondary"
    },
    "surrounds": {
        "size_ratio": 3.0,
        "enclosure": True,
        "connector": "none",
        "color_hint": "parent_dominant"
    }
}

# ============================================================================
# 2. CONNECTOR GEOMETRY SPECS
# ============================================================================
CONNECTOR_SPECS = {
    "none": None,
    "tapered_arrow": {
        "shape": "cone", 
        "segments": 16, 
        "taper": True, 
        "taper_ratio": 0.7, 
        "width": "medium", 
        "style": "solid"
    },
    "angular_bar": {
        "shape": "box", 
        "segments": 1, 
        "taper": False, 
        "taper_ratio": 1.0, 
        "width": "thick", 
        "style": "solid"
    },
    "burst_arrow": {
        "shape": "cone", 
        "segments": 8, 
        "taper": True, 
        "taper_ratio": 0.5, 
        "width": "thick", 
        "style": "solid"
    },
    "bracket_base": {
        "shape": "box", 
        "segments": 3, 
        "taper": False, 
        "taper_ratio": 1.0, 
        "width": "medium", 
        "style": "solid"
    },
    "double_arrow_opposing": {
        "shape": "cone", 
        "segments": 16, 
        "taper": True, 
        "taper_ratio": 0.8, 
        "width": "medium", 
        "style": "solid"
    },
    "dashed_equal": {
        "shape": "cylinder", 
        "segments": 8, 
        "taper": False, 
        "taper_ratio": 1.0, 
        "width": "thin", 
        "style": "dashed"
    },
    "morphing_arrow": {
        "shape": "torus_section", 
        "segments": 32, 
        "taper": True, 
        "taper_ratio": 0.3, 
        "width": "medium", 
        "style": "dotted"
    },
    "thin_line": {
        "shape": "cylinder", 
        "segments": 4, 
        "taper": False, 
        "taper_ratio": 1.0, 
        "width": "thin", 
        "style": "solid"
    },
    "curved_bidirectional": {
        "shape": "torus_section", 
        "segments": 16, 
        "taper": False, 
        "taper_ratio": 1.0, 
        "width": "medium", 
        "style": "dashed"
    }
}

# ============================================================================
# 3. HELPER FUNCTIONS
# ============================================================================
def parse_strength(strength_str: str) -> float:
    if not isinstance(strength_str, str): return 0.5
    s = strength_str.lower()
    if "weak" in s or "low" in s: return 0.3
    if "strong" in s or "high" in s: return 1.0
    try:
        val = float(s)
        return max(0.0, min(1.0, val))
    except:
        return 0.6 # default medium

def apply_strength_scaling(spec: dict, strength: float) -> dict:
    if not spec: return None
    s = copy.deepcopy(spec)
    
    # Scale width
    if strength < 0.4:
        s["width"] = "thin"
    elif strength > 0.8:
        s["width"] = "thick"
        
    return s

def apply_scale_effect(scale_hint: tuple, effect: float, strength: float) -> tuple:
    # Amplify or halve effect based on strength
    mod = effect
    if strength < 0.4:
        # Distance from 1.0 is halved
        mod = 1.0 + ((effect - 1.0) * 0.5)
    elif strength > 0.8:
        # Distance from 1.0 amplified
        mod = 1.0 + ((effect - 1.0) * 1.3)
        
    return (scale_hint[0] * mod, scale_hint[1] * mod, scale_hint[2] * mod)

# ============================================================================
# 4. MAIN RESOLUTION FUNCTION
# ============================================================================
def apply_relational_geometry(blueprint: dict) -> dict:
    validate_incoming(blueprint, "RelationalGeometry", ["geometric_components", "semantic_relations"])
    
    out_bp = copy.deepcopy(blueprint)
    out_bp["connectors"] = []
    
    components = out_bp.get("geometric_components", [])
    comp_map = {c["id"]: c for c in components}
    
    # Tracking accumulators for conflict resolution
    scale_mods = {c["id"]: [] for c in components}
    layout_hints = {c["id"]: [] for c in components}
    color_hints = {c["id"]: None for c in components}
    
    relations = out_bp.get("semantic_relations", [])
    
    for rel in relations:
        r_type = rel.get("relation_type")
        r_strength = parse_strength(rel.get("strength", "medium"))
        
        rule = RELATION_RULES.get(r_type)
        if not rule: continue
        
        from_id, to_id = rel.get("from_id"), rel.get("to_id")
        
        # 1. Handle Connectors
        connector_type = rule.get("connector", "none")
        base_spec = CONNECTOR_SPECS.get(connector_type)
        if base_spec:
            scaled_spec = apply_strength_scaling(base_spec, r_strength)
            out_bp["connectors"].append({
                "from_id": from_id,
                "to_id": to_id,
                "geometry": scaled_spec
            })
            
        # 2. Handle Color Hints
        if rule.get("color_hint"):
            if from_id in color_hints: color_hints[from_id] = rule["color_hint"]
            if to_id in color_hints: color_hints[to_id] = rule["color_hint"]
            
        # 3. Handle Layout Hints
        if rule.get("layout_hint"):
            if from_id in layout_hints: layout_hints[from_id].append(rule["layout_hint"])
            if to_id in layout_hints: layout_hints[to_id].append(rule["layout_hint"])
            
        # Special logic for "enclosure" (contains)
        if rule.get("enclosure"):
            if from_id in layout_hints: layout_hints[from_id].append("contains")
            if to_id in layout_hints: layout_hints[to_id].append("contained_within")
            
        # 4. Handle Scale Effects / Size Ratios
        if "size_ratio" in rule:
            ratio = rule["size_ratio"]
            if r_type == "contains":
                # Outer is ratio times bigger than inner
                if from_id in scale_mods: scale_mods[from_id].append(ratio)
                if to_id in scale_mods: scale_mods[to_id].append(1.0)
            elif r_type == "part_of":
                # Child (from) is smaller, Parent (to) is larger
                # Rule says 0.5 (parent * 2.0 vs child)
                if from_id in scale_mods: scale_mods[from_id].append(ratio)
                if to_id in scale_mods: scale_mods[to_id].append(1.0 / ratio)
                
        if "scale_effect" in rule:
            effect = rule["scale_effect"]
            if effect == "equalize":
                if from_id in scale_mods: scale_mods[from_id].append(1.0)
                if to_id in scale_mods: scale_mods[to_id].append(1.0)
            else:
                # effect hits target (e.g. activates = target grows by 1.2)
                if to_id in scale_mods:
                    # Modify effect by strength
                    mod = effect
                    if r_strength < 0.4: mod = 1.0 + ((effect - 1.0) * 0.5)
                    elif r_strength > 0.8: mod = 1.0 + ((effect - 1.0) * 1.3)
                    scale_mods[to_id].append(mod)

    # 5. Commit tracked accumulators and resolve conflicts
    for c in components:
        cid = c["id"]
        
        # Color Hint
        if color_hints[cid]:
            c["color_hint"] = color_hints[cid]
            
        # Layout Hint Conflict Resolution
        lh = layout_hints[cid]
        if lh:
            if "contains" in lh: c["layout_hint"] = "contains"
            elif "contained_within" in lh: c["layout_hint"] = "contained_within"
            else: c["layout_hint"] = lh[0] # Just take first if no severe conflicts
            
        # Scale Modifiers Averaging
        sm = scale_mods[cid]
        if sm:
            # Average all scale modifiers acting on this component
            avg_mod = sum(sm) / len(sm)
            current_scale = c.get("scale_hint", (1.0, 1.0, 1.0))
            if isinstance(current_scale, (list, tuple)) and len(current_scale) == 3:
                c["scale_hint"] = (current_scale[0] * avg_mod, current_scale[1] * avg_mod, current_scale[2] * avg_mod)

    return out_bp

# ============================================================================
# 5. TESTS
# ============================================================================
if __name__ == "__main__":
    def run_test(name, blueprint):
        res = apply_relational_geometry(blueprint)
        print(f"--- TEST: {name} ---")
        print(f"Connectors Created: {[(c['from_id'], c['to_id'], c['geometry']['shape'] if c['geometry'] else 'none') for c in res['connectors']]}")
        for comp in res["geometric_components"]:
            print(f"  Component: {comp['id']} -> scale_hint: {[round(x, 2) for x in comp['scale_hint']]}, layout: {comp.get('layout_hint', 'none')}, color: {comp.get('color_hint', 'none')}")
        print()

    # 1. Nucleus contains DNA
    run_test("Nucleus contains DNA", {
        "geometric_components": [
            {"id": "nucleus", "scale_hint": (1.0, 1.0, 1.0)},
            {"id": "dna", "scale_hint": (1.0, 1.0, 1.0)}
        ],
        "semantic_relations": [
            {"from_id": "nucleus", "to_id": "dna", "relation_type": "contains", "strength": "strong"}
        ]
    })
    
    # 2. Oxygen flows_to mitochondria
    run_test("Oxygen flows_to mitochondria", {
        "geometric_components": [
            {"id": "oxygen", "scale_hint": (0.5, 0.5, 0.5)},
            {"id": "mitochondria", "scale_hint": (1.0, 1.0, 1.0)}
        ],
        "semantic_relations": [
            {"from_id": "oxygen", "to_id": "mitochondria", "relation_type": "flows_to", "strength": "medium"}
        ]
    })
    
    # 3. Drug inhibits enzyme
    run_test("Drug inhibits enzyme", {
        "geometric_components": [
            {"id": "drug", "scale_hint": (1.0, 1.0, 1.0)},
            {"id": "enzyme", "scale_hint": (1.0, 1.0, 1.0)}
        ],
        "semantic_relations": [
            {"from_id": "drug", "to_id": "enzyme", "relation_type": "inhibits", "strength": "strong"}
        ]
    })
    
    # 4. Capitalism competes_with socialism
    run_test("Capitalism competes_with socialism", {
        "geometric_components": [
            {"id": "capitalism", "scale_hint": (1.0, 1.0, 1.0)},
            {"id": "socialism", "scale_hint": (1.0, 1.0, 1.0)}
        ],
        "semantic_relations": [
            {"from_id": "capitalism", "to_id": "socialism", "relation_type": "competes_with", "strength": "medium"}
        ]
    })
