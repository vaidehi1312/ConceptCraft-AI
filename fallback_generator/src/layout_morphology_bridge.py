"""
Layout Morphology Bridge
------------------------
RESPONSIBILITY: 
Translates high-level Morphology Families (e.g., "nested_membrane") into 
specific low-level layout engine parameters and patterns.

STAGES HANDLED:
- Intermediate Stage (Pre-Layout)
"""
import math
import copy
from pipeline_contract import (
    SIZE_HINT_SCALE, IMPORTANCE_SCALE, 
    VALID_MORPHOLOGY_FAMILIES, validate_incoming
)

def apply_morphology_to_layout(blueprint: dict, layout_params: dict) -> dict:
    validate_incoming(blueprint, "LayoutMorphologyBridge", ["morphology_family", "geometric_components"])

    # Safely get morphology parameters
    m_family = blueprint.get("morphology_family", "unknown")
    m_params = blueprint.get("morphology_params", {})
    
    # Initialize updated layout parameters
    updated_params = copy.deepcopy(layout_params)
    if not isinstance(updated_params, dict):
        updated_params = {}

    components = blueprint.get("geometric_components", [])
    comp_count = sum(c.get("count", 1) for c in components)

    # 1. Modify param configuration based on specific defined overrides
    if m_family == "nested_membrane":
        updated_params["forced_pattern"] = "central_peripheral"
        updated_params["z_layering"] = True
        
        # Determine inner radius from density heuristic
        density = m_params.get("interior_density", "sparse")
        r_map = {"sparse": 0.3, "clustered": 0.5, "packed": 0.7}
        updated_params["inner_radius_factor"] = r_map.get(density, 0.4)
        
    elif m_family == "branching_tree":
        updated_params["forced_pattern"] = "hierarchical"
        updated_params["branch_splay"] = True
        contrast = m_params.get("scale_contrast", "graduated")
        updated_params["vertical_spread"] = 2.0 if contrast == "dramatic" else 1.0

    elif m_family == "flow_channel":
        updated_params["forced_pattern"] = "linear" if comp_count < 10 else "network"
        updated_params["taper_along_flow"] = True
        # Extract generalized flow direction signal
        updated_params["flow_direction"] = [1.0, 0.0, 0.0]

    elif m_family == "crystalline_lattice":
        updated_params["forced_pattern"] = "field"
        updated_params["grid_spacing"] = "uniform"
        updated_params["jitter"] = False
        
    elif m_family == "field_gradient":
        updated_params["forced_pattern"] = "field"
        updated_params["density_falloff"] = True
        updated_params["gradient_axis"] = [1.0, 0.0, 0.0]

    elif m_family == "hub_spoke_web":
        updated_params["forced_pattern"] = "radial"
        updated_params["hub_center"] = [0.0, 0.0, 0.0]
        if comp_count > 8:
            updated_params["secondary_ring"] = True
            
    elif m_family == "stacked_layers":
        updated_params["forced_pattern"] = "hierarchical"
        updated_params["horizontal_spread"] = False
        updated_params["layer_gap"] = 1.5
        updated_params["layer_labels"] = True
        
    elif m_family == "dense_aggregate":
        updated_params["forced_pattern"] = "field"
        updated_params["random_jitter"] = True
        updated_params["strict_grid"] = False
        density = m_params.get("interior_density", "clustered")
        j_map = {"sparse": 0.5, "clustered": 1.5, "packed": 0.2}
        updated_params["jitter_range"] = j_map.get(density, 1.0)
        
    elif m_family == "helical_chain":
        updated_params["forced_pattern"] = "helical" # Override any traditional engines
        updated_params["helix_radius"] = 3.0
        updated_params["helix_pitch"] = 1.5
        updated_params["helix_turns"] = max(1, comp_count / 10.0)
        
    elif m_family == "modular_grid":
        updated_params["forced_pattern"] = "field"
        updated_params["strict_grid"] = True
        dim = math.ceil(math.sqrt(max(1, comp_count)))
        updated_params["grid_dimensions"] = [dim, dim]
        updated_params["cell_borders"] = True
    
    elif m_family == "architectural_assembly":
        updated_params["forced_pattern"] = "central_peripheral"
        updated_params["vertical_stacking"] = True
        updated_params["corner_placement"] = True
        updated_params["base_grounded"] = True
        updated_params["height_from_role"] = True
    
    elif m_family == "process_sequence":
        updated_params["forced_pattern"] = "linear"
        updated_params["axis"] = "x"
        updated_params["equal_spacing"] = True
        updated_params["vertical_stacking"] = False
    
    elif m_family == "symbolic_abstract":
        updated_params["forced_pattern"] = "radial"
        updated_params["z_variance"] = True
        updated_params["pulsing_scale"] = True
        
    return updated_params


def generate_helix_positions(components: list, params: dict) -> list:
    """
    Returns list of generated 3D points directly simulating a helical chain path.
    """
    import random
    
    radius = params.get("helix_radius", 3.0)
    pitch = params.get("helix_pitch", 1.5)
    turns = params.get("helix_turns", 2.0)
    
    total_comps = sum(c.get("count", 1) for c in components)
    if total_comps == 0: return []
    
    out = []
    current_idx = 0
    
    # Calculate angular step necessary to complete the specified number of turns
    # Total angle to traverse is turns * 2*PI
    total_angle = turns * 2 * math.pi
    
    # The step per component ignoring pairing overlap for a moment
    angle_step = total_angle / max(1, total_comps - 1)
    
    # Simple pairing detection for twin helices (like DNA bases)
    paired_mode = any(c.get("count", 1) == 2 for c in components)

    for c in components:
        count = c.get("count", 1)
        for i in range(count):
            t = current_idx * angle_step
            
            # If paired, force the second item 180 degrees opposite the first at the same height curve
            if paired_mode and i % 2 == 1:
                t = (current_idx - 1) * angle_step + math.pi
                y = (current_idx - 1) * (pitch / (2*math.pi)) * angle_step
            else:
                y = current_idx * (pitch / (2*math.pi)) * angle_step
                
            x = radius * math.cos(t)
            z = radius * math.sin(t)
            
            # Mock generating simple tanget based rotations pointing outwards
            rx, ry, rz = 0.0, -t, 0.0
            
            out.append({
                "original_component": c,
                "position": [x, y, z],
                "rotation": [rx, ry, rz]
            })
            
            if not (paired_mode and i % 2 == 1):
                current_idx += 1
                
    return out


def resolve_connector_positions(blueprint: dict, calculated_components: list) -> list:
    """
    Computes hardline absolute 3D rendering points for relational_geometry generated connectors.
    """
    pos_map = {c["id"]: c["position"] for c in calculated_components}
    
    out_connectors = []
    b_connectors = blueprint.get("connectors") or []
    
    for c_spec in b_connectors:
        from_id = c_spec.get("from_id")
        to_id = c_spec.get("to_id")
        geom = c_spec.get("geometry")
        
        # If geometry is null, skip visualization of connector
        if not geom: continue
        
        p_start = pos_map.get(from_id)
        p_end = pos_map.get(to_id)
        
        if not p_start or not p_end: continue
        
        # Generate control point for curved arrows using simple arc over mid point
        mid_x = (p_start[0] + p_end[0]) / 2.0
        mid_y = (p_start[1] + p_end[1]) / 2.0
        mid_z = (p_start[2] + p_end[2]) / 2.0
        
        dist = math.sqrt((p_end[0]-p_start[0])**2 + (p_end[1]-p_start[1])**2 + (p_end[2]-p_start[2])**2)
        
        # Pop Y up proportionally to arc length
        control_points = [[mid_x, mid_y + (dist * 0.2), mid_z]]
        
        out_connectors.append({
            "id": f"conn_{from_id}_{to_id}",
            "type": geom.get("type", "relation_link"),
            "start": p_start,
            "end": p_end,
            "control_points": control_points,
            "shape": geom.get("shape", "cylinder"),
            "width": 0.1 if geom.get("width") == "thin" else (0.4 if geom.get("width") == "thick" else 0.2),
            "color_hint": "neutral_secondary", # Overrides later available if tracked
            "taper_ratio": geom.get("taper_ratio", 1.0)
        })
        
    return out_connectors


def format_final_output(blueprint: dict, computed_comps: list, computed_connectors: list) -> dict:
    """
    Strictly conforms data payload to the requested schema layout.
    """
    out_components = []
    
    # Calculate strict bounds
    min_x, max_x = float('inf'), float('-inf')
    min_y, max_y = float('inf'), float('-inf')
    min_z, max_z = float('inf'), float('-inf')
    
    m_family = blueprint.get("morphology_family", "unknown")
    
    for c in computed_comps:
        pos = c.get("position", [0.0, 0.0, 0.0])
        min_x, max_x = min(min_x, pos[0]), max(max_x, pos[0])
        min_y, max_y = min(min_y, pos[1]), max(max_y, pos[1])
        min_z, max_z = min(min_z, pos[2]), max(max_z, pos[2])
        
        orig_comp = c.get("original_component", {})
        
        # Handle resolving layout hints on existing nodes like opposing_sides or mirror_pair
        h_hint = orig_comp.get("layout_hint")
        if h_hint == "opposing_sides":
            # Very naive mock of opposing sides positioning (handled generally by graph physics, but enforced here)
             pass 

        s_hint = orig_comp.get("scale_hint", (1.0, 1.0, 1.0))
        if isinstance(s_hint, (list, tuple)) and len(s_hint) == 3:
            scale = list(s_hint)
        else:
            scale = [1.0, 1.0, 1.0]
            
        out_components.append({
            "id": c.get("id", orig_comp.get("id", "unknown")),
            "position": pos,
            "rotation": c.get("rotation", [0.0, 0.0, 0.0]),
            "scale": scale,
            "resolved_shape": orig_comp.get("resolved_shape", orig_comp.get("shape", "box")),
            "color_hint": orig_comp.get("color_hint", "neutral"),
            "label": orig_comp.get("label", orig_comp.get("id", "unknown")),
            "morphology_family": m_family
        })

    # Catching default infinities for empty scopes
    if min_x == float('inf'): min_x, max_x = 0.0, 0.0
    if min_y == float('inf'): min_y, max_y = 0.0, 0.0
    if min_z == float('inf'): min_z, max_z = 0.0, 0.0
    
    bounds = [
        max_x - min_x,
        max_y - min_y,
        max_z - min_z
    ]

    return {
        "components": out_components,
        "connectors": computed_connectors,
        "scene_bounds": bounds,
        "morphology_family": m_family
    }


if __name__ == "__main__":
    def run_tests():
        print("Running layout morphology bridge tests...")
        
        test_bp = {
            "morphology_family": "helical_chain",
            "morphology_params": {},
            "geometric_components": [
                {"id": "base1", "count": 2, "resolved_shape": "box", "scale_hint": (0.5, 0.5, 0.5)},
                {"id": "base2", "count": 2, "resolved_shape": "box", "scale_hint": (0.5, 0.5, 0.5)},
                {"id": "base3", "count": 2, "resolved_shape": "box", "scale_hint": (0.5, 0.5, 0.5)},
                {"id": "base4", "count": 2, "resolved_shape": "box", "scale_hint": (0.5, 0.5, 0.5)}
            ],
            "connectors": [
                {
                    "from_id": "base1",
                    "to_id": "base2",
                    "geometry": {"shape": "cylinder", "width": "thin"}
                }
            ]
        }
        
        # 1. Parameter Override verification
        params = apply_morphology_to_layout(test_bp, {"default": "yes"})
        print(f"Helical Override Params: {params}")
        
        # 2. Helical Position Generation
        heli_comps = generate_helix_positions(test_bp["geometric_components"], params)
        print(f"\nGenerated Helical Pairs (First 4):")
        for h in heli_comps[:4]:
            print(f"  {h['original_component']['id']} @ [x:{h['position'][0]:.1f}, y:{h['position'][1]:.1f}, z:{h['position'][2]:.1f}]")
            
        # Give them IDs for the connector map
        for i, hc in enumerate(heli_comps):
            hc["id"] = hc["original_component"]["id"] if hc["original_component"]["count"] == 1 else f"{hc['original_component']['id']}_{i}"
            
        # Hack to ensure from_id maps exactly for the simplistic connector test
        heli_comps[0]["id"] = "base1"
        heli_comps[2]["id"] = "base2"

        # 3. Resolve Connectors
        conns = resolve_connector_positions(test_bp, heli_comps)
        print(f"\nResolved Visual Connectors: {len(conns)}")
        for c in conns:
            print(f"  {c['shape']} joining {c['start']} -> {c['end']}")
            
        # 4. Final Format Emission
        final_doc = format_final_output(test_bp, heli_comps, conns)
        print(f"\nFINAL DOC KEYS: {list(final_doc.keys())}")
        print(f"  Components Length: {len(final_doc['components'])}")
        print(f"  Connectors Length: {len(final_doc['connectors'])}")
        print(f"  Scene Bounds: {[round(x, 2) for x in final_doc['scene_bounds']]}")

    run_tests()
