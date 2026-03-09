"""
Layout Algorithms Module
------------------------
This file contains the core mathematical logic for positioning 3D geometry conceptually.
It defines several classes (CentralPeripheralLayout, HierarchicalLayout, RadialLayout, 
NetworkLayout, FieldLayout), each representing a different visual paradigm. 
These engines incorporate semantic variants based on component importance, 
counts, symmetry, and relations via dynamic heuristic formulas.
"""
"""
Layout Engine Implementations
-----------------------------
RESPONSIBILITY: 
Contains the mathematical implementations of various layout algorithms 
(Radial, Hierarchical, Network, etc.) used to generate 3D coordinates.
"""
import math
import random
from typing import List, Tuple, Any
from schema import ComponentInput, OutputComponent, Position, Scale, Blueprint

# Base scaling factors based on size_hint
SIZE_MAP = {
    "small": 0.5,
    "medium": 1.0,
    "large": 2.0,
    "extra_large": 4.0
}

def get_base_scale(component: ComponentInput) -> Scale:
    s = SIZE_MAP.get(component.size_hint, 1.0)
    # Give different base dimensions based on shape
    if component.shape == "cylinder":
        return Scale(x=s, y=s * 2, z=s)
    elif component.shape == "box":
        return Scale(x=s, y=s, z=s)
    elif component.shape == "hemisphere":
        return Scale(x=s, y=s * 0.5, z=s)
    return Scale(x=s, y=s, z=s)

def get_importance_weight(importance: str) -> float:
    weights = {"low": 0.5, "medium": 1.0, "high": 2.0}
    return weights.get(importance, 1.0)

def get_relation_strength(strength: str) -> float:
    strengths = {"weak": 0.5, "medium": 1.0, "strong": 2.0}
    return strengths.get(strength, 1.0)

def calculate_dynamic_spacing(components: List[ComponentInput], relations: List[Any], base_spacing: float) -> float:
    """Calculates a custom spacing heuristic based on element volume and coupling density."""
    count_factor = math.sqrt(len(components)) * 0.5
    # Clamp relation factor heavily so high-relation dense objects don't explode into a graph web
    relation_factor = min(2.0, len(relations) * 0.1)
    return base_spacing + count_factor + relation_factor

class BaseLayoutEngine:
    def process(self, blueprint: Blueprint) -> List[OutputComponent]:
        raise NotImplementedError()

class CentralPeripheralLayout(BaseLayoutEngine):
    def process(self, blueprint: Blueprint) -> List[OutputComponent]:
        out_comps = []
        central_comps = [c for c in blueprint.geometric_components if c.role in ["central", "source"] or c.id == "root"]
        if not central_comps:
            central_comps = [c for c in blueprint.geometric_components if any(kw in c.id.lower() for kw in ["central", "main", "core", "base"])]
        if not central_comps and blueprint.geometric_components:
            central_comps = [blueprint.geometric_components[0]]
            
        cap_comps = [c for c in blueprint.geometric_components if c.role == "cap"]
        central_comps = [c for c in central_comps if c not in cap_comps]
            
        peripheral_comps = [c for c in blueprint.geometric_components if c not in central_comps and c not in cap_comps]
        
        spacing_factor = calculate_dynamic_spacing(blueprint.geometric_components, blueprint.semantic_relations, base_spacing=2.0)
        
        # Central items stack in the middle
        y_offset = 0.0
        
        # Detect Architecture Mode
        symmetry = blueprint.constraints.symmetry
        arrangement = blueprint.structure.arrangement
        is_architecture_mode = (arrangement == "corner_based" and (symmetry == "four_fold" or symmetry == "bilateral"))
        
        # Find Anchor if Architecture Mode
        anchor_comp = None
        if is_architecture_mode:
            anchor_comp = next((c for c in central_comps if any(kw in c.id.lower() or kw in c.label.lower() for kw in ["platform", "base", "foundation"])), None)
            
            # If anchor exists, process it first at y=0 using a flattened footprint
            if anchor_comp:
                central_comps.remove(anchor_comp)
                max_central_x = max([get_base_scale(c).x for c in central_comps], default=1.0)
                max_central_z = max([get_base_scale(c).z for c in central_comps], default=1.0)
                max_central_y = max([get_base_scale(c).y for c in central_comps], default=1.0)
                
                scale = get_base_scale(anchor_comp)
                # Override scale for realistic footprint
                scale.x = max_central_x * 1.6
                scale.z = max_central_z * 1.6
                scale.y = max_central_y * 0.25
                
                out_comps.append(OutputComponent(
                    id=anchor_comp.id, original_id=anchor_comp.id, semantic_type=anchor_comp.semantic_type, label=anchor_comp.label, shape=anchor_comp.shape,
                    position=Position(x=0.0, y=scale.y / 2.0, z=0.0), scale=scale, metadata={"variant": "anchor"}
                ))
                y_offset = scale.y
        
        for c in central_comps:
            scale = get_base_scale(c)
            for j in range(c.count):
                comp_id = f"{c.id}_{j}" if c.count > 1 else c.id
                y_base = y_offset + (scale.y / 2.0)
                out_comps.append(OutputComponent(
                    id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                    position=Position(x=0.0, y=y_base, z=0.0), scale=scale, metadata={"variant": "core"}
                ))
                y_offset += scale.y + 0.1
                
        # Cap Stacking Logic
        for c in cap_comps:
            scale = get_base_scale(c)
            for j in range(c.count):
                comp_id = f"{c.id}_{j}" if c.count > 1 else c.id
                y_base = y_offset + (scale.y / 2.0)
                out_comps.append(OutputComponent(
                    id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                    position=Position(x=0.0, y=y_base, z=0.0), scale=scale, metadata={"variant": "cap"}
                ))
                y_offset += scale.y + 0.1
                
        total_p_instances = sum(c.count for c in peripheral_comps)
        if total_p_instances == 0: return out_comps

        # Architecture Mode Placement 
        if is_architecture_mode:
            # Reconstruct footprint from the calculated anchor scale if it existed
            if anchor_comp:
                anchor_scale_x = max([get_base_scale(c).x for c in central_comps], default=1.0) * 1.6
                anchor_scale_z = max([get_base_scale(c).z for c in central_comps], default=1.0) * 1.6
            else:
                anchor_scale_x = max(get_base_scale(cc).x for cc in central_comps) + 4.0
                anchor_scale_z = max(get_base_scale(cc).z for cc in central_comps) + 4.0
                
            footprint_x = anchor_scale_x
            footprint_z = anchor_scale_z
            
            for c in peripheral_comps:
                scale = get_base_scale(c)
                
                # Tower/Minaret Corner Snapping
                if c.shape == "cylinder" or c.semantic_type in ["tower", "minaret"] or c.count == 4:
                    corner_offsets = [
                        (footprint_x / 2.0, footprint_z / 2.0),
                        (-footprint_x / 2.0, footprint_z / 2.0),
                        (footprint_x / 2.0, -footprint_z / 2.0),
                        (-footprint_x / 2.0, -footprint_z / 2.0)
                    ]
                    for j in range(c.count):
                        comp_id = f"{c.id}_{j}" if c.count > 1 else c.id
                        cx, cz = corner_offsets[j % 4]
                        out_comps.append(OutputComponent(
                            id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                            position=Position(x=cx, y=scale.y / 2.0, z=cz), scale=scale, metadata={"variant": "corner_tower"}
                        ))
                else:
                    # Lateral Snapping (e.g. Mosque, Guest house)
                    lateral_offsets = [
                        (footprint_x / 1.5 + scale.x, 0.0),
                        (-(footprint_x / 1.5 + scale.x), 0.0),
                        (0.0, footprint_z / 1.5 + scale.z),
                        (0.0, -(footprint_z / 1.5 + scale.z))
                    ]
                    for j in range(c.count):
                        comp_id = f"{c.id}_{j}" if c.count > 1 else c.id
                        lx, lz = lateral_offsets[j % 4]
                        out_comps.append(OutputComponent(
                            id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                            position=Position(x=lx, y=scale.y / 2.0, z=lz), scale=scale, metadata={"variant": "lateral_building"}
                        ))
            return out_comps

        # Normal Graph Radial Variant Selection Logic (Non-Architecture Mode)
        if symmetry == "four_fold" or total_p_instances == 4:
            variant = "corner"
        elif symmetry == "bilateral":
            variant = "directional"
        elif any(c.vertical_relation == "above" for c in peripheral_comps):
            variant = "layered"
        else:
            variant = "radial"

        target_radius = 5.0 + spacing_factor + (total_p_instances * 0.5)

        current_idx = 0
        core_max_x = max([get_base_scale(cc).x for cc in central_comps] + [1.0]) if central_comps else 1.0
        core_max_y = max([get_base_scale(cc).y for cc in central_comps] + [1.0]) if central_comps else 1.0

        for c in peripheral_comps:
            scale = get_base_scale(c)
            importance = get_importance_weight(c.importance)
            
            # Relation-aware: closer to core if high importance
            radius = target_radius / importance
            
            # --- SNAPPING LOGIC ---
            is_snapped = False
            for rel in blueprint.semantic_relations:
                if rel.relation_type in ["attached_to", "supports", "contains"]:
                    if (rel.from_id == c.id and any(rel.to_id == cc.id for cc in central_comps)) or \
                       (rel.to_id == c.id and any(rel.from_id == cc.id for cc in central_comps)):
                        # Override radius to touch the surface
                        radius = (core_max_x / 2.0) + (scale.x / 2.0)
                        is_snapped = True
                        break
            
            for j in range(c.count):
                angle_step = (2 * math.pi) / total_p_instances
                
                if variant == "corner":
                    corner_idx = current_idx % 4
                    angle = (corner_idx * math.pi / 2) + (math.pi / 4)
                    if not is_snapped:
                        radius += (current_idx // 4) * 2.0 
                elif variant == "directional":
                    side = current_idx % 2
                    base_angle = 0 if side == 0 else math.pi
                    jitter = (current_idx // 2) * 0.2
                    angle = base_angle + jitter
                else: 
                    # Default radial or layered
                    angle = current_idx * angle_step

                x = radius * math.cos(angle)
                z = radius * math.sin(angle)
                
                y = scale.y / 2.0
                if variant == "layered" or c.vertical_relation == "above" or is_snapped:
                    if is_snapped:
                        y = core_max_y + (scale.y / 2.0) + (j * scale.y)
                        x, z = 0.0, 0.0 # Snap perfectly on top
                    else:
                        y += 3.0 * importance
                elif c.vertical_relation == "below":
                    y -= 3.0 * importance

                comp_id = f"{c.id}_{j}" if c.count > 1 else c.id
                out_comps.append(OutputComponent(
                    id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                    position=Position(x=x, y=y, z=z), scale=scale, metadata={"variant": variant}
                ))
                current_idx += 1
                
        return out_comps

class HierarchicalLayout(BaseLayoutEngine):
    def process(self, blueprint: Blueprint) -> List[OutputComponent]:
        out_comps = []
        levels = blueprint.structure.levels or [c.id for c in blueprint.geometric_components]
        
        has_lateral = any(r.relation_type in ["exchanges_with", "supports", "regulates"] for r in blueprint.semantic_relations)
        variant = "lateral_links" if has_lateral else "strict_tree"
        if len(levels) > 0 and len(blueprint.geometric_components) > 5 and not blueprint.structure.levels:
             variant = "branching_tree"
             
        y_depth_step = calculate_dynamic_spacing(blueprint.geometric_components, blueprint.semantic_relations, base_spacing=5.0)
        
        placed_components = set()
        prev_level_bottom_y = float(len(levels) * y_depth_step) + y_depth_step
        
        for lvl_name in levels:
            level_comps = [c for c in blueprint.geometric_components if c.id == lvl_name and c.id not in placed_components]
            if not level_comps:
                level_comps = [c for c in blueprint.geometric_components if c.id not in placed_components]
                if not level_comps: break
                level_comps = [level_comps[0]]
                
            # --- SNAPPING LOGIC ---
            is_snapped = False
            for c in level_comps:
                for rel in blueprint.semantic_relations:
                    if rel.relation_type in ["attached_to", "supports", "contains"]:
                        if (rel.from_id == c.id and rel.to_id in placed_components) or \
                           (rel.to_id == c.id and rel.from_id in placed_components):
                            is_snapped = True
                            break
                if is_snapped: break
            
            level_max_y_scale = max((get_base_scale(c).y for c in level_comps), default=1.0)
            
            if is_snapped and placed_components:
                y_current = prev_level_bottom_y - (level_max_y_scale / 2.0)
            else:
                y_current = prev_level_bottom_y - y_depth_step
                
            prev_level_bottom_y = y_current - (level_max_y_scale / 2.0)
            # ----------------------
                
            total_weight = sum(get_importance_weight(c.importance) * c.count for c in level_comps)
            x_spacing_base = calculate_dynamic_spacing(level_comps, [], base_spacing=3.0)
            
            start_x = -(total_weight * x_spacing_base) / 2.0
            
            current_x = start_x
            for c in level_comps:
                scale = get_base_scale(c)
                weight = get_importance_weight(c.importance)
                for j in range(c.count):
                    step = x_spacing_base * weight
                    current_x += step / 2.0
                    x = current_x
                    
                    y_jitter = 0.0
                    if variant == "lateral_links" and j % 2 == 1:
                        y_jitter = 1.5 
                    
                    comp_id = f"{c.id}_{j}" if c.count > 1 else c.id
                    out_comps.append(OutputComponent(
                        id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                        position=Position(x=x, y=y_current + y_jitter, z=0.0), scale=scale, metadata={"variant": variant}
                    ))
                    current_x += step / 2.0
                placed_components.add(c.id)
            
        return out_comps

class RadialLayout(BaseLayoutEngine):
    def process(self, blueprint: Blueprint) -> List[OutputComponent]:
        out_comps = []
        
        central = [c for c in blueprint.geometric_components if c.role in ["center", "source"]]
        ring = [c for c in blueprint.geometric_components if c not in central]
        
        is_sequence = any(r.relation_type in ["transforms_into", "flows_to"] for r in blueprint.semantic_relations)
        is_symmetric = blueprint.constraints.symmetry in ["radial", "four_fold", "bilateral"]
        
        variant = "pure_ring"
        if central:
            variant = "ring_center"
        if is_sequence and not is_symmetric:
            variant = "spiral"
        elif not is_symmetric and sum(c.count for c in ring) > 2:
            variant = "uneven_sector"

        for c in central:
            scale = get_base_scale(c)
            for j in range(c.count):
                comp_id = f"{c.id}_{j}" if c.count > 1 else c.id
                out_comps.append(OutputComponent(
                    id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                    position=Position(x=0.0, y=scale.y/2.0, z=0.0), scale=scale, metadata={"variant": "core"}
                ))
        
        total_items = sum(c.count for c in ring)
        if total_items == 0: return out_comps
        
        base_radius = calculate_dynamic_spacing(ring, blueprint.semantic_relations, base_spacing=5.0) + (total_items * 0.3)
        
        if variant == "uneven_sector":
            total_weight = sum(get_importance_weight(c.importance) * c.count for c in ring)
            angle_allocations = []
            for c in ring:
                w = get_importance_weight(c.importance)
                for _ in range(c.count):
                    angle_allocations.append((w / total_weight) * 2 * math.pi)
        else:
            angle_allocations = [(2 * math.pi) / total_items for _ in range(total_items)]

        current_idx = 0
        current_angle = 0.0
        
        for c in ring:
            scale = get_base_scale(c)
            for j in range(c.count):
                radius = base_radius
                if variant == "spiral":
                    radius = base_radius + (current_idx * 1.5)
                
                slice_angle = angle_allocations[current_idx]
                angle = current_angle + (slice_angle / 2.0)
                
                x = radius * math.cos(angle)
                z = radius * math.sin(angle)
                y = scale.y / 2.0
                
                comp_id = f"{c.id}_{j}" if c.count > 1 else c.id
                out_comps.append(OutputComponent(
                    id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                    position=Position(x=x, y=y, z=z), scale=scale, metadata={"variant": variant}
                ))
                current_angle += slice_angle
                current_idx += 1
                
        return out_comps

class NetworkLayout(BaseLayoutEngine):
    def process(self, blueprint: Blueprint) -> List[OutputComponent]:
        out_comps = []
        random.seed(42)  # For deterministic initial state
        
        nodes = []
        for c in blueprint.geometric_components:
            for j in range(c.count):
                comp_id = f"{c.id}_{j}" if c.count > 1 else c.id
                nodes.append({
                    "id": comp_id,
                    "original_id": c.id,
                    "component": c,
                    "pos": [random.uniform(-10, 10), get_base_scale(c).y/2.0, random.uniform(-10, 10)],
                    "vel": [0.0, 0.0, 0.0]
                })
        
        edges = []
        for r in blueprint.semantic_relations:
            from_nodes = [n for n in nodes if n["original_id"] == r.from_id]
            to_nodes = [n for n in nodes if n["original_id"] == r.to_id]
            strength = get_relation_strength(r.strength)
            for fn in from_nodes:
                for tn in to_nodes:
                    edges.append((fn, tn, strength))

        iterations = 50
        max_repulsion = 20.0
        k = calculate_dynamic_spacing(blueprint.geometric_components, blueprint.semantic_relations, base_spacing=5.0)
        
        # Lightweight Fruchterman-Reingold Force-Directed execution
        for _ in range(iterations):
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    n1, n2 = nodes[i], nodes[j]
                    dx = n1["pos"][0] - n2["pos"][0]
                    dz = n1["pos"][2] - n2["pos"][2]
                    dist2 = dx*dx + dz*dz
                    if dist2 < 0.1: dist2 = 0.1
                    dist = math.sqrt(dist2)
                    
                    rep_force = (k * k) / dist
                    if rep_force > max_repulsion: rep_force = max_repulsion
                    
                    fx = (dx / dist) * rep_force
                    fz = (dz / dist) * rep_force
                    
                    w1 = get_importance_weight(n1["component"].importance)
                    w2 = get_importance_weight(n2["component"].importance)
                    
                    n1["vel"][0] += fx / w1
                    n1["vel"][2] += fz / w1
                    n2["vel"][0] -= fx / w2
                    n2["vel"][2] -= fz / w2

            for fn, tn, strength in edges:
                dx = tn["pos"][0] - fn["pos"][0]
                dz = tn["pos"][2] - fn["pos"][2]
                dist = math.sqrt(dx*dx + dz*dz)
                if dist < 0.1: dist = 0.1
                
                attr_force = (dist * dist) / k * (strength * 0.05)
                
                fx = (dx / dist) * attr_force
                fz = (dz / dist) * attr_force
                
                fn["vel"][0] += fx
                fn["vel"][2] += fz
                tn["vel"][0] -= fx
                tn["vel"][2] -= fz

            for n in nodes:
                n["pos"][0] += n["vel"][0]
                n["pos"][2] += n["vel"][2]
                n["vel"][0] *= 0.5
                n["vel"][2] *= 0.5

        if nodes:
            cx = sum(n["pos"][0] for n in nodes) / len(nodes)
            cz = sum(n["pos"][2] for n in nodes) / len(nodes)
            for n in nodes:
                c = n["component"]
                scale = get_base_scale(c)
                out_comps.append(OutputComponent(
                    id=n["id"], original_id=n["original_id"], semantic_type=c.semantic_type,
                    label=c.label, shape=c.shape,
                    position=Position(x=n["pos"][0] - cx, y=n["pos"][1], z=n["pos"][2] - cz),
                    scale=scale, metadata={"variant": "force_directed"}
                ))
                
        return out_comps

class FieldLayout(BaseLayoutEngine):
    def process(self, blueprint: Blueprint) -> List[OutputComponent]:
        out_comps = []
        
        sources = [c for c in blueprint.geometric_components if c.role in ["source", "center"]]
        particles = [c for c in blueprint.geometric_components if c not in sources]
        
        total_sources = sum(s.count for s in sources)
        has_directional_rel = any(r.relation_type in ["flows_to", "produces", "transforms_into"] for r in blueprint.semantic_relations)
        
        variant = "grid"
        if has_directional_rel:
            variant = "directional"
        elif total_sources > 1:
            variant = "radial_field"

        source_positions = []
        for c in sources:
            scale = get_base_scale(c)
            for j in range(c.count):
                comp_id = f"{c.id}_{j}" if c.count > 1 else c.id
                px, py, pz = 0.0, scale.y/2, 0.0
                if variant == "directional":
                    px, pz = -10.0, (j * 5.0) - (c.count * 2.5) 
                elif variant == "radial_field":
                    px, pz = math.cos(j)*10.0, math.sin(j)*10.0
                    
                out_comps.append(OutputComponent(
                    id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                    position=Position(x=px, y=py, z=pz), scale=scale, metadata={"variant": variant}
                ))
                source_positions.append((px, pz))
                
        total_particles = sum(p.count for p in particles)
        if total_particles == 0: return out_comps
        
        spacing = calculate_dynamic_spacing(particles, blueprint.semantic_relations, base_spacing=3.0)
        
        if variant == "directional":
            current_x = -5.0
            p_idx = 0
            while p_idx < len(particles):
                c = particles[p_idx]
                scale = get_base_scale(c)
                width_capacity = int(10 / spacing) + 1
                group_z_start = -(width_capacity * spacing) / 2.0
                
                for i in range(c.count):
                    x = current_x + (i // width_capacity) * spacing
                    z = group_z_start + (i % width_capacity) * spacing
                    y = scale.y / 2.0
                    
                    comp_id = f"{c.id}_{i}" if c.count > 1 else c.id
                    out_comps.append(OutputComponent(
                        id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                        position=Position(x=x, y=y + (get_importance_weight(c.importance)*2.0), z=z), scale=scale, metadata={"variant": variant}
                    ))
                current_x += ((c.count // width_capacity) + 2) * spacing
                p_idx += 1
                
        else: # Grid or radial field
            grid_dim = math.ceil(math.pow(total_particles, 1/3))
            p_idx, j_idx = 0, 0
            for gx in range(grid_dim):
                for gy in range(grid_dim):
                    for gz in range(grid_dim):
                        if p_idx >= len(particles): break
                        
                        c = particles[p_idx]
                        scale = get_base_scale(c)
                        
                        x = (gx - grid_dim/2.0) * spacing
                        y = (gy) * spacing + (scale.y/2.0)
                        z = (gz - grid_dim/2.0) * spacing
                        
                        if variant == "radial_field" and source_positions:
                            for sx, sz in source_positions:
                                dx, dz = x - sx, z - sz
                                dist = math.sqrt(dx*dx + dz*dz)
                                if dist > 0.1:
                                    x += (dx/dist) * (10.0 / dist)
                                    z += (dz/dist) * (10.0 / dist)

                        comp_id = f"{c.id}_{j_idx}" if c.count > 1 else c.id
                        out_comps.append(OutputComponent(
                            id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                            position=Position(x=x, y=y, z=z), scale=scale, metadata={"variant": variant}
                        ))
                        
                        j_idx += 1
                        if j_idx >= c.count:
                            p_idx += 1
                            j_idx = 0
                        
        return out_comps

class LinearLayout(BaseLayoutEngine):
    def process(self, blueprint: Blueprint) -> List[OutputComponent]:
        out_comps = []
        
        # Sort or maintain order, assuming LLM generated them in sequential flow order
        components = blueprint.geometric_components
        
        current_x = 0.0
        total_comps = len(components)
        
        for idx, c in enumerate(components):
            scale = get_base_scale(c)
            
            # Determine flow metadata
            if idx == 0:
                variant = "entry"
            elif idx == total_comps - 1:
                variant = "sink"
            else:
                variant = "progression"
                
            for j in range(c.count):
                comp_id = f"{c.id}_{j}" if c.count > 1 else c.id
                
                # Advance X by half the current item's width (so center is correct)
                x_pos = current_x + (scale.x / 2.0)
                
                out_comps.append(OutputComponent(
                    id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                    position=Position(x=x_pos, y=scale.y / 2.0, z=0.0), scale=scale, metadata={"variant": variant}
                ))
                
                # Advance X for the NEXT item by the remaining half of this item's width + semantic spacing
                spacing = 1.0
                # Extra spacing between distinct logic blocks, compact spacing for repeats (count > 1)
                if j == c.count - 1:
                    spacing = 2.0 
                    
                current_x = x_pos + (scale.x / 2.0) + spacing
                
        # Center the entire linear sequence around x=0
        if out_comps:
            total_width = current_x - 2.0 # Remove the trailing spacing from the last item
            shift_x = -total_width / 2.0
            for oc in out_comps:
                oc.position.x += shift_x
                
        return out_comps

class SequentialMorphologyLayout(BaseLayoutEngine):
    def process(self, blueprint: Blueprint) -> List[OutputComponent]:
        out_comps = []
        components = blueprint.geometric_components
        
        current_x = 0.0
        current_y = 0.0
        current_z = 0.0
        
        total_comps = len(components)
        
        for idx, c in enumerate(components):
            scale = get_base_scale(c)
            
            if idx == 0:
                variant = "entry"
            elif idx == total_comps - 1:
                variant = "sink"
            else:
                variant = "progression"
                
            for j in range(c.count):
                comp_id = f"{c.id}_{j}" if c.count > 1 else c.id
                
                # Advance X
                x_pos = current_x + (scale.x / 2.0)
                y_pos = current_y + (scale.y / 2.0)
                z_pos = current_z
                
                out_comps.append(OutputComponent(
                    id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                    position=Position(x=x_pos, y=y_pos, z=z_pos), scale=scale, metadata={"variant": variant}
                ))
                
                # Introduce a morphological "bend" or loop if it's the middle element
                if variant == "progression" and j == c.count - 1 and idx == total_comps // 2:
                    current_y -= (scale.y + 2.0)
                    current_z += 2.0
                elif variant == "progression" and j == c.count - 1 and idx > total_comps // 2:
                    current_y += (scale.y + 2.0)  # Ascending back up
                    current_z -= 2.0
                
                spacing = 1.0 if j < c.count - 1 else 2.0
                current_x = x_pos + (scale.x / 2.0) + spacing
                
        # Center the structure
        if out_comps:
            total_width = current_x - 2.0
            shift_x = -total_width / 2.0
            for oc in out_comps:
                oc.position.x += shift_x
                
        return out_comps

class BilateralMotifLayout(BaseLayoutEngine):
    def process(self, blueprint: Blueprint) -> List[OutputComponent]:
        out_comps = []
        components = blueprint.geometric_components
        
        rail_comps = [c for c in components if c.importance == "high" or c.role in ["anchor", "peripheral"]]
        connector_comps = [c for c in components if c not in rail_comps]
        
        # Determine how many "rungs"
        rung_count = max([c.count for c in connector_comps] + [len(connector_comps)])
        if rung_count < 2: 
            rung_count = 5 # Default to a nice ladder
            
        y_step = 2.0
        rail_spacing = 4.0
        
        # Build Rails
        for c in rail_comps:
            scale = get_base_scale(c)
            # Make rails tall
            scale.y = rung_count * y_step + 1.0
            
            # Left Rail
            out_comps.append(OutputComponent(
                id=f"{c.id}_left", original_id=c.id, semantic_type=c.semantic_type, label=f"{c.label} (Left)", shape=c.shape,
                position=Position(x=-rail_spacing/2.0, y=scale.y/2.0, z=0.0), scale=scale, metadata={"variant": "rail_left"}
            ))
            # Right Rail
            out_comps.append(OutputComponent(
                id=f"{c.id}_right", original_id=c.id, semantic_type=c.semantic_type, label=f"{c.label} (Right)", shape=c.shape,
                position=Position(x=rail_spacing/2.0, y=scale.y/2.0, z=0.0), scale=scale, metadata={"variant": "rail_right"}
            ))

        # Build Connectors
        if connector_comps:
            for i in range(rung_count):
                c = connector_comps[i % len(connector_comps)]
                scale = get_base_scale(c)
                scale.x = rail_spacing # stretch across
                
                y_pos = (i + 1) * y_step
                
                # Twist motif (like DNA) by offseting Z slightly over progression
                z_offset = math.sin(i * 0.5) * 1.5 if blueprint.pattern == "hybrid" else 0.0
                
                out_comps.append(OutputComponent(
                    id=f"{c.id}_{i}", original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                    position=Position(x=0.0, y=y_pos, z=z_offset), scale=scale, metadata={"variant": "connector"}
                ))
                
        return out_comps

class ClusteredCoreLayout(BaseLayoutEngine):
    def process(self, blueprint: Blueprint) -> List[OutputComponent]:
        out_comps = []
        components = blueprint.geometric_components
        
        cores = [c for c in components if c.importance == "high" or c.role in ["central", "node"]]
        peripherals = [c for c in components if c not in cores]
        
        # 1. Tightly cluster the multiple cores
        core_centers = []
        for c in cores:
            scale = get_base_scale(c)
            for j in range(c.count):
                comp_id = f"{c.id}_{j}" if c.count > 1 else c.id
                
                # Tight cluster: small radius around center
                angle = (j / max(1, c.count)) * 2 * math.pi
                radius = 1.0 + random.uniform(0.0, 0.5)
                
                x_pos = radius * math.cos(angle)
                z_pos = radius * math.sin(angle)
                y_pos = (scale.y / 2.0) + random.uniform(0.0, 1.0)
                
                core_centers.append((x_pos, z_pos))
                
                out_comps.append(OutputComponent(
                    id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                    position=Position(x=x_pos, y=y_pos, z=z_pos), scale=scale, metadata={"variant": "core_cluster"}
                ))

        # 2. Spread peripherals OUTSIDE the core boundary
        max_core_radius = max((math.sqrt(x*x + z*z) for x, z in core_centers), default=1.0)
        
        total_p = sum(c.count for c in peripherals)
        p_idx = 0
        for c in peripherals:
            scale = get_base_scale(c)
            for j in range(c.count):
                comp_id = f"{c.id}_{j}" if c.count > 1 else c.id
                
                angle = (p_idx / max(1, total_p)) * 2 * math.pi
                radius = max_core_radius + 3.0 + random.uniform(0.0, 1.0)
                
                x_pos = radius * math.cos(angle)
                z_pos = radius * math.sin(angle)
                y_pos = (scale.y / 2.0)
                
                out_comps.append(OutputComponent(
                    id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                    position=Position(x=x_pos, y=y_pos, z=z_pos), scale=scale, metadata={"variant": "peripheral_scatter"}
                ))
                p_idx += 1
                
        return out_comps

class TubularMorphologyLayout(BaseLayoutEngine):
    def __init__(self):
        self.tube_path = []
        
    def process(self, blueprint: Blueprint) -> List[OutputComponent]:
        out_comps = []
        components = list(blueprint.geometric_components)
        
        current_x = 0.0
        current_y = 0.0
        current_z = 0.0
        self.tube_path = []
        
        # 1. Resolve containment grammar before tubular sequence
        contained_pair = None
        for r in blueprint.semantic_relations:
            if r.relation_type == "contains":
                outer = next((c for c in components if c.id == r.from_id), None)
                inner = next((c for c in components if c.id == r.to_id), None)
                if outer and inner:
                    contained_pair = (outer, inner)
                    break
                    
        if contained_pair:
            outer, inner = contained_pair
            outer_scale = get_base_scale(outer)
            inner_scale = get_base_scale(inner)
            
            if outer.shape == "sphere":
                outer.shape = "hemisphere"
                
            y_pos = current_y + (outer_scale.y / 2.0)
            
            # Place Outer First (Enclosure)
            out_comps.append(OutputComponent(
                id=outer.id, original_id=outer.id, semantic_type=outer.semantic_type, label=outer.label, shape=outer.shape,
                position=Position(x=current_x, y=y_pos, z=0.0), scale=outer_scale, metadata={"variant": "container_head"}
            ))
            
            # Place Inner (Nested Core)
            out_comps.append(OutputComponent(
                id=inner.id, original_id=inner.id, semantic_type=inner.semantic_type, label=inner.label, shape=inner.shape,
                position=Position(x=current_x, y=y_pos, z=0.0), scale=inner_scale, metadata={"variant": "nested_core"}
            ))
            
            self.tube_path.append([current_x, y_pos, 0.0])
            
            components.remove(outer)
            components.remove(inner)
            
            # Advance X safely out of the nested structure
            current_x += (outer_scale.x / 2.0)
        
        total_comps = len(components)
        
        for idx, c in enumerate(components):
            scale = get_base_scale(c)
            
            # Step 1: Head/Entry (If no containment resolved)
            if idx == 0 and not contained_pair:
                variant = "head"
                x_pos = current_x
                y_pos = current_y + (scale.y / 2.0)
                z_pos = 0.0
                
            # Step 2: Lateral Progression Start (or first item after containment)
            elif (idx == 1 and not contained_pair) or (idx == 0 and contained_pair):
                variant = "lateral_start"
                current_x += (scale.x / 2.0) + 2.0
                x_pos = current_x
                y_pos = current_y + (scale.y / 2.0)
                z_pos = 0.0
                
            # Step 3: The U-turn (Descending/Ascending Loop)
            elif idx == total_comps // 2:
                variant = "u_turn_loop"
                current_x += (scale.x / 2.0) + 1.0 # slight lateral shift
                current_y -= (scale.y + 4.0)       # Drop down deep
                
                # Add a mid-way point for smoother curve in ThreeJS
                self.tube_path.append([current_x, current_y + (scale.y / 2.0) + 2.0, 0.5])
                
                x_pos = current_x
                y_pos = current_y + (scale.y / 2.0)
                z_pos = 1.0 # slight depth pop
                
            # Step 4: The Ascendant Return
            elif idx == (total_comps // 2) + 1:
                variant = "ascendant_return"
                current_x += (scale.x / 2.0) + 1.0 # slight lateral shift
                current_y += (scale.y + 2.0)       # Come back up
                
                # Add a mid-way point for smoother curve returning
                self.tube_path.append([current_x, current_y + (scale.y / 2.0) - 2.0, 0.5])
                
                x_pos = current_x
                y_pos = current_y + (scale.y / 2.0)
                z_pos = 0.0
                
            # Step 5+: Terminal Sinks (Ducts, drops back down structurally)
            else:
                variant = "terminal_sink"
                current_x += (scale.x / 2.0) + 2.0
                if idx == total_comps - 1:
                    current_y -= (scale.y + 2.0) # Drain down
                    
                x_pos = current_x
                y_pos = current_y + (scale.y / 2.0)
                z_pos = -1.0
                
            # Add locus to tube path once per component type
            self.tube_path.append([x_pos, y_pos, z_pos])
                
            for j in range(c.count):
                comp_id = f"{c.id}_{j}" if c.count > 1 else c.id
                
                # Jitter multiplicity slightly around the locus
                j_x = x_pos + (random.uniform(-0.5, 0.5) if c.count > 1 else 0.0)
                j_y = y_pos + (random.uniform(-0.5, 0.5) if c.count > 1 else 0.0)
                j_z = z_pos + (random.uniform(-0.5, 0.5) if c.count > 1 else 0.0)

                out_comps.append(OutputComponent(
                    id=comp_id, original_id=c.id, semantic_type=c.semantic_type, label=c.label, shape=c.shape,
                    position=Position(x=j_x, y=j_y, z=j_z), scale=scale, metadata={"variant": variant}
                ))
            
            # Prepare X for next nominal step (width / 2)
            current_x = x_pos + (scale.x / 2.0)
            
        # Center the entire structure
        if out_comps:
            total_width = current_x
            shift_x = -total_width / 2.0
            
            lowest_y = min(oc.position.y - (oc.scale.y/2.0) for oc in out_comps)
            shift_y = -lowest_y # Push entire lowest point to y=0 exactly
            
            for oc in out_comps:
                oc.position.x += shift_x
                oc.position.y += shift_y
            
            for p in self.tube_path:
                p[0] += shift_x
                p[1] += shift_y
                
        return out_comps
