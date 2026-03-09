"""
Spatial post-processing passes for layout engines.
Runs AFTER main layout positions are computed, BEFORE connector resolution.

Contains:
  1. apply_importance_scale — deterministic scale from importance × size_hint
  2. apply_containment_pass — moves children inside container bounds
  3. apply_vertical_stacking_pass — stacks components vertically based on relations
"""
"""
Spatial Passes Module
---------------------
RESPONSIBILITY: 
Executes rule-based spatial adjustments on the raw layout output. 
Handles component scaling, containment, and vertical stacking.

STAGES HANDLED:
- Final Spatial Pass (Post-Layout)
"""
import math
import random
from typing import List, Dict


# ============================================================================
# SCALE TABLES
# ============================================================================

IMPORTANCE_SCALE = {
    "high": 1.8,
    "medium": 1.0,
    "low": 0.6
}

SIZE_HINT_SCALE = {
    "largest": 3.0,
    "extra_large": 2.8,
    "large": 2.2,
    "medium": 1.0,
    "small": 0.6,
    "tiny": 0.35,
    "fills_space": 4.0
}


# ============================================================================
# FIX 3: Deterministic Scale from Importance × Size Hint
# ============================================================================

def apply_importance_scale(components: list) -> list:
    """
    Apply deterministic scale to OutputComponents based on their original
    blueprint importance and size_hint fields.
    Modifies components in-place and returns them.
    """
    for oc in components:
        # Get importance and size_hint from the original component data
        importance = "medium"
        size_hint = "medium"
        
        # OutputComponent has metadata dict and original fields
        if hasattr(oc, 'metadata'):
            importance = oc.metadata.get("importance", "medium")
            size_hint = oc.metadata.get("size_hint", "medium")
        
        imp_factor = IMPORTANCE_SCALE.get(importance, 1.0)
        size_factor = SIZE_HINT_SCALE.get(size_hint, 1.0)
        final_scale = size_factor * imp_factor
        
        oc.scale.x = final_scale
        oc.scale.y = final_scale
        oc.scale.z = final_scale
    
    return components


# ============================================================================
# FIX 1: Containment Pass
# ============================================================================

def apply_containment_pass(components: list, relations: list) -> list:
    """
    For each 'contains' or 'part_of' relation, ensures the child component
    is positioned INSIDE the container's bounds.
    
    components: list of OutputComponent objects
    relations: list of RelationInput objects (from blueprint)
    """
    # Build lookup maps
    comp_map = {oc.original_id: oc for oc in components}
    
    # Containment relation types
    CONTAINMENT_TYPES = {"contains", "part_of", "surrounds"}
    
    for rel in relations:
        rtype = rel.relation_type if hasattr(rel, 'relation_type') else rel.get("relation_type", "")
        if rtype not in CONTAINMENT_TYPES:
            continue
        
        container_id = rel.from_id if hasattr(rel, 'from_id') else rel.get("from_id", "")
        child_id = rel.to_id if hasattr(rel, 'to_id') else rel.get("to_id", "")
        
        container = comp_map.get(container_id)
        child = comp_map.get(child_id)
        
        if not container or not child:
            continue
        
        # Container bounds = container_position ± (container_scale * 0.4)
        container_radius = max(container.scale.x, container.scale.y, container.scale.z) * 0.4
        
        # Distance from child to container center
        dx = child.position.x - container.position.x
        dy = child.position.y - container.position.y
        dz = child.position.z - container.position.z
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        
        if dist > container_radius:
            # Reposition child inside container bounds
            max_offset = container_radius * 0.8
            child.position.x = container.position.x + random.uniform(-max_offset, max_offset)
            child.position.y = container.position.y + random.uniform(-max_offset, max_offset)
            child.position.z = container.position.z + random.uniform(-max_offset, max_offset)
    
    return components


# ============================================================================
# FIX 2: Vertical Stacking Pass
# ============================================================================

def apply_vertical_stacking_pass(components: list, relations: list) -> list:
    """
    For each 'stacked_above' or 'supports' relation, vertically stacks components.
    Also applies vertical_relation hints for above/below/inside.
    
    components: list of OutputComponent objects
    relations: list of RelationInput objects
    """
    comp_map = {oc.original_id: oc for oc in components}
    
    for rel in relations:
        rtype = rel.relation_type if hasattr(rel, 'relation_type') else rel.get("relation_type", "")
        from_id = rel.from_id if hasattr(rel, 'from_id') else rel.get("from_id", "")
        to_id = rel.to_id if hasattr(rel, 'to_id') else rel.get("to_id", "")
        
        lower = comp_map.get(from_id)
        upper = comp_map.get(to_id)
        
        if not lower or not upper:
            continue
        
        if rtype == "stacked_above":
            # "from" has something on top → "to" goes on top of "from"
            upper.position.x = lower.position.x
            upper.position.y = lower.position.y + lower.scale.y * 0.5 + upper.scale.y * 0.5
            upper.position.z = lower.position.z
            
        elif rtype == "supports":
            # "from" supports "to" → "to" goes on top of "from"
            # Keep X/Z from layout engine, only adjust Y
            upper.position.y = lower.position.y + lower.scale.y * 0.5 + upper.scale.y * 0.5
    
    return components


def apply_vertical_relation_hints(components: list, blueprint_components: list) -> list:
    """
    Apply vertical_relation field hints from blueprint to output positions.
    
    components: list of OutputComponent objects
    blueprint_components: list of ComponentInput objects (original blueprint)
    """
    comp_map = {oc.original_id: oc for oc in components}
    
    # Compute scene center Y
    if components:
        center_y = sum(oc.position.y for oc in components) / len(components)
    else:
        center_y = 0.0
    
    for bp_comp in blueprint_components:
        cid = bp_comp.id if hasattr(bp_comp, 'id') else bp_comp.get("id", "")
        vrel = bp_comp.vertical_relation if hasattr(bp_comp, 'vertical_relation') else bp_comp.get("vertical_relation", "none")
        
        oc = comp_map.get(cid)
        if not oc:
            continue
        
        if vrel == "above" and oc.position.y <= center_y:
            oc.position.y = center_y + oc.scale.y * 1.5
        elif vrel == "below" and oc.position.y >= center_y:
            oc.position.y = center_y - oc.scale.y * 1.5
        elif vrel == "container":
            # Container stays at its position, no adjustment needed
            pass
        elif vrel == "inside":
            # Already handled by containment pass — but ensure Y is near parent center
            pass
    
    return components
