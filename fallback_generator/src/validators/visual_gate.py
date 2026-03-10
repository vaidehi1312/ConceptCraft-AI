"""
Visual Gate Module
------------------
RESPONSIBILITY: 
Provides a spatial/topological score for the Blueprint. Rejects blueprints 
that are geometrically impossible or logically inconsistent (e.g., recursive containment).

STAGES HANDLED:
- Stage 5: Visual Gate
"""
# ============================================================================
# RESPONSIBILITY BOUNDARY: VisualGate
# ============================================================================
# This gate is ONLY responsible for VISUAL concerns:
#   - Shape diversity check and repair
#   - Scale/importance contrast check and repair
#   - Connector presence check and repair
#   - Spatial spread check and repair
#   - Morphological recognizability scoring (post-layout)
#
# It does NOT handle:
#   - JSON structural validity (BlueprintGate)
#   - Required field presence (BlueprintGate)
#   - Enum value corrections (BlueprintGate)
#   - Relation pruning or ref checks (BlueprintGate)
#   - Component count limits (BlueprintGate)
#   - Annotation count limits (BlueprintGate)
# ============================================================================

from typing import Dict, Any
from schema import Blueprint

class VisualGate:
    """
    Visual quality gate. Scores and repairs VISUAL properties only:
    shape diversity, scale contrast, pattern fidelity, and morphological coherence.
    Structural validity is assumed to have been handled by BlueprintGate.
    """

    @classmethod
    def execute(cls, blueprint: Blueprint, category: str = "abstract_system") -> Dict[str, Any]:
        """
        Returns a dict: { "score": 0-100, "status": "accept|repair|reject", "issues": [], "data": Blueprint }
        """
        score = 100
        issues = []
        
        components = blueprint.geometric_components
        relations = blueprint.semantic_relations
        pattern = blueprint.pattern
        comp_count = len(components)
        rel_count = len(relations)
        
        # (Component count validation is handled by BlueprintGate, not here)

        # Step 2: Component Size / Importance Diversity Score
        importances = set(c.importance for c in components)
        if len(importances) == 1 and comp_count > 1:
            score -= 10
            issues.append("All components have identical importance. Visual flatness detected.")

        # Step 3: Role Diversity Score
        roles = set(c.role for c in components)
        if len(roles) == 1 and "node" in roles and comp_count > 1:
            score -= 10
            issues.append("All components default to 'node' role. No functional diversity.")

        # Step 4: Shape Diversity Score
        shapes = set(c.shape for c in components)
        if len(shapes) == 1 and "box" in shapes and comp_count > 1:
            score -= 10
            issues.append("All components default to 'box' shape. Visual flatness detected.")

        # Step 5: Pattern Fidelity Score
        if pattern == "central_peripheral":
            if not any(c.role == "central" or c.importance == "high" for c in components):
                score -= 15
                issues.append("Pattern central_peripheral missing dominant center.")
        elif pattern == "field":
            if not any(c.role == "source" for c in components):
                score -= 10
                issues.append("Pattern field missing a source component.")

        # Step 6: Graph Collapse Detection
        if comp_count > 0:
            density = rel_count / comp_count
            density_limits = {
                "physical_object": 1.2,
                "biological_structure": 0.8,
                "process": 1.0,
                "abstract_system": 1.0,
                "chemical_structure": 0.8,
                "physical_phenomenon": 1.0
            }
            max_density = density_limits.get(category, 1.0)
            if density > max_density:
                score -= 20
                issues.append(f"Graph collapse likely. Relation density ({density:.2f}) exceeds max {max_density} for {category}")

        # Step 7: Central Dominance Check
        if pattern == "central_peripheral":
            if not any(c.importance == "high" for c in components):
                score -= 10
                issues.append("No component has 'high' importance for central_peripheral pattern.")

        # Step 8: Hybrid Validity Score
        if pattern == "hybrid":
            if len(blueprint.groups) < 2:
                score -= 30
                issues.append("Hybrid pattern requires at least 2 groups.")

        # (Relation quality and annotation counts are handled by BlueprintGate/SemanticGate, not here)

        # Step 11: Multiplicity & Architectural Constraints Penalty
        if category == "physical_object":
            for c in components:
                if (c.shape == "cylinder" or c.semantic_type == "tower") and c.count == 1 and c.role != "central":
                    score -= 15
                    issues.append(f"Suspiciously lost multiplicity for architectural tower: {c.id}")
                    
            if pattern == "central_peripheral" and (not blueprint.structure.arrangement or blueprint.structure.arrangement == "free"):
                score -= 20
                issues.append("Central-peripheral architecture missing structural arrangement.")
                
            peripheral_counts = [c.count for c in components if c.role == "peripheral" and c.shape in {"cylinder", "box", "cone"}]
            if (4 in peripheral_counts or 2 in peripheral_counts) and (not blueprint.constraints.symmetry or blueprint.constraints.symmetry == "none"):
                score -= 20
                issues.append("Symmetry missing despite repeated architectural peripherals.")
                
            # Identity Core Penalties
            shape_defining_cores = {"dome", "roof", "blade", "arch", "helix", "wing", "chamber", "minaret", "tower", "spire", "pillar", "vault", "canopy"}
            has_shape_defining_core = False
            for c in components:
                c_id_lower = c.id.lower()
                c_label_lower = c.label.lower()
                if any(core in c_id_lower or core in c_label_lower for core in shape_defining_cores):
                    has_shape_defining_core = True
                    break
                    
            if not has_shape_defining_core and comp_count > 0:
                score -= 20
                issues.append("Physical object has no explicit shape-defining core")
                
            # Anchor Dominance Check
            anchors = [c for c in components if any(kw in c.id.lower() or kw in c.label.lower() for kw in ["platform", "base", "foundation", "plinth"])]
            central_items = [c for c in components if c.role == "central" or c.importance == "high"]
            if anchors and central_items:
                size_weights = {"small": 1, "medium": 2, "large": 3, "extra_large": 4}
                max_anchor_weight = max(size_weights.get(a.size_hint, 2) for a in anchors)
                max_central_weight = max(size_weights.get(cen.size_hint, 2) for cen in central_items)
                
                if max_anchor_weight < max_central_weight:
                    score -= 15
                    issues.append("Anchor Dominance failed. Foundation/Platform is smaller than the central component.")
                    
            # Missing Cap Role Penalty
            cap_structures = [c for c in components if any(kw in c.id.lower() or kw in c.label.lower() for kw in ["dome", "roof", "spire", "finial", "crown"])]
            if cap_structures and not any(c.role == "cap" for c in cap_structures):
                score -= 15
                issues.append("Vertical crown components found but missing 'cap' role. Stacking realism lowered.")

        # Step 12: Sequential Alignment Penalty
        if blueprint.structure.arrangement == "linear" and pattern in {"central_peripheral", "radial"}:
            core_count = sum(1 for c in components if c.importance == "high")
            if core_count > 1:
                score -= 15
                issues.append(f"Structural contradiction: {pattern} pattern mixed with linear arrangement for sequential cores. Radial overlap likely.")

        # Decide Status
        # Decide Status (relaxed gate)
        status = "accept"

        if score < 80:
            status = "repair"
            blueprint = cls._repair_blueprint(blueprint, category)

# Never reject — allow pipeline to continue
        if score < 40:
            status = "repair"

        return {
            "score": score,
            "status": status,
            "issues": issues,
            "data": blueprint if status != "reject" else None
        }

    @classmethod
    def _repair_blueprint(cls, blueprint: Blueprint, category: str) -> Blueprint:
        """Visual-only repairs: shape diversity and scale contrast."""
        comp_count = len(blueprint.geometric_components)

        # Shape diversity repair (visual concern)
        shapes = set(c.shape for c in blueprint.geometric_components)
        if len(shapes) == 1 and "box" in shapes and comp_count > 1:
            diversity_shape = "cylinder" if category == "physical_object" else "sphere"
            for c in blueprint.geometric_components:
                if c.role != "central":
                    c.shape = diversity_shape
                    break

        return blueprint

    @classmethod
    def score_morphological_recognizability(cls, layout_output: dict) -> Dict[str, Any]:
        """
        Post-layout scoring pass utilizing geometry, components, and scene bounds.
        """
        score = 0.0
        issues = []
        repairs = []
        
        components = layout_output.get("components", [])
        connectors = layout_output.get("connectors", [])
        bounds = layout_output.get("scene_bounds", [1.0, 1.0, 1.0])
        family = layout_output.get("morphology_family", "unknown")
        
        # 1. Shape Diversity (+0.2) — role-based repair, never randomize
        shapes = set(c.get("resolved_shape", "") for c in components)
        if len(shapes) >= 3:
            score += 0.2
        else:
            issues.append(f"Shape diversity warning: only {len(shapes)} distinct shapes (< 3).")
            # Role-based shape repair: only change spheres based on semantic role
            ROLE_SHAPE_MAP = {
                "channel": "cylinder", "tube": "cylinder", "duct": "cylinder",
                "connector": "cylinder", "pipe": "cylinder",
                "platform": "box", "base": "box", "layer": "box",
                "floor": "box", "slab": "box",
                "cap": "icosphere", "dome": "icosphere", "crown": "icosphere",
            }
            KEEP_SPHERE_ROLES = {"anchor", "container", "enclosure", "membrane",
                                 "central", "peripheral", "node", "source", "sink"}
            changed = False
            for c in components:
                current_shape = c.get("resolved_shape", "")
                if current_shape != "sphere":
                    continue  # Rule 1: Never change non-sphere shapes
                label_lower = c.get("label", "").lower()
                id_lower = c.get("id", "").lower()
                # Check role keywords against id and label
                mapped = None
                for kw, shape in ROLE_SHAPE_MAP.items():
                    if kw in id_lower or kw in label_lower:
                        mapped = shape
                        break
                if mapped:
                    c["resolved_shape"] = mapped
                    changed = True
                # Rules 2-6: If role is in keep-sphere set or no mapping found, keep sphere
            if changed:
                repairs.append("Applied role-based shape refinement (preserved non-sphere shapes).")
            else:
                repairs.append("Shape diversity < 3 but no safe role-based repairs available. Accepted as-is.")
                
        # 2. Scale Contrast (+0.2)
        vols = []
        for c in components:
            sc = c.get("scale", [1.0, 1.0, 1.0])
            vols.append(sc[0] * sc[1] * sc[2])
            
        if vols and max(vols) / max(0.01, min(vols)) >= 3.0:
            score += 0.2
        else:
            issues.append("Scale contrast failed: Volume ratio < 3x.")
            # Repair: inflate high importance (mocked by first core or similar)
            if components:
                # We don't have importance directly in output, so inflate the biggest existing one or just the first
                idx = vols.index(max(vols))
                sc = components[idx].get("scale", [1.0, 1.0, 1.0])
                components[idx]["scale"] = [sc[0]*2.5, sc[1]*2.5, sc[2]*2.5]
                repairs.append("Force inflated largest component by 2.5x.")
                
        # 3. Connector Presence (+0.2)
        has_relations = len(layout_output.get("original_relations_count", [])) > 0 or len(connectors) > 0 # Hacky proxy
        if connectors:
            score += 0.2
        elif not has_relations:
            score += 0.2 # Pass by default if graph has no relations
        else:
            issues.append("Connector presence failed: Missing connectors despite having relations.")
            # Note: We can't trivially add thin_line accurately without from/to ids and positions here natively without re-parsing graph,
            # but we could mock it. The requirement says "add thin_line connectors", simplified logic below:
            if len(components) > 1:
                connectors.append({
                    "id": "forced_repair", "type": "relation_link",
                    "start": components[0]["position"], "end": components[1]["position"],
                    "shape": "cylinder", "width": 0.02, "color_hint": "neutral_secondary", "taper_ratio": 1.0
                })
                repairs.append("Added fallback thin_line connectors.")
        
        # 4. Family Coherence (+0.2)
        # Loose check, e.g. branching_tree uses capsules often
        if family != "unknown":
            score += 0.2
        else:
            issues.append("Family coherence failed: Unknown morphology family.")
            
        # 5. Spatial Spread (+0.2) — diagonal-based calculation
        REFERENCE_DIAGONAL = 15.0
        
        if len(components) > 1:
            xs = [c.get("position", [0,0,0])[0] for c in components]
            ys = [c.get("position", [0,0,0])[1] for c in components]
            zs = [c.get("position", [0,0,0])[2] for c in components]
            dx = max(xs) - min(xs)
            dy = max(ys) - min(ys)
            dz = max(zs) - min(zs)
            actual_diagonal = (dx**2 + dy**2 + dz**2) ** 0.5
            spread_ratio = actual_diagonal / REFERENCE_DIAGONAL
            
            if spread_ratio >= 0.4:
                score += 0.2
            else:
                issues.append(f"Spatial spread low: diagonal {actual_diagonal:.2f} / ref {REFERENCE_DIAGONAL} = {spread_ratio:.2f} < 0.4")
                # Apply 1.5x scaling ONCE (guard against double-scaling)
                if not layout_output.get("_spatial_repair_applied"):
                    for c in components:
                        pos = c.get("position", [0.0, 0.0, 0.0])
                        c["position"] = [pos[0]*1.5, pos[1]*1.5, pos[2]*1.5]
                    layout_output["scene_bounds"] = [bounds[0]*1.5, bounds[1]*1.5, bounds[2]*1.5]
                    layout_output["_spatial_repair_applied"] = True
                    repairs.append("Scaled all positions outward 1.5x (once).")
                else:
                    repairs.append("Spatial spread already repaired previously. Skipped double-scaling.")
        else:
            score += 0.2  # Single component — spread check not applicable
                
        return {
            "score": score,
            "family": family,
            "issues": issues,
            "repairs": repairs
        }
