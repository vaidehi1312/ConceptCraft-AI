"""
Blueprint Gate Module
---------------------
RESPONSIBILITY: 
Processes and repairs the Stage 2 Blueprint. Normalizes relations, 
repairs missing component fields, and validates the geometric structure 
before layout occurs.

STAGES HANDLED:
- Stage 4: Blueprint Gate
"""
import json
from typing import Dict, Any, Tuple
from schema import (
    Blueprint, ComponentInput, StructureDetails, ConstraintsModel, 
    ExplanationsModel, RelationInput, GroupInput, AnnotationInput
)
from pipeline_contract import (
    VALID_SHAPES, VALID_ROLES, VALID_SIZE_HINTS, 
    VALID_VERTICAL_RELATIONS, VALID_RELATION_TYPES,
    SIZE_HINT_SCALE, validate_incoming
)

# ============================================================================
# RESPONSIBILITY BOUNDARY: BlueprintGate
# ============================================================================
# This gate is ONLY responsible for STRUCTURAL concerns:
#   - JSON structure validity and required field presence
#   - Enum value correctness (shape, role, size_hint, vertical_relation, etc.)
#   - Component ID validation (uniqueness, forbidden generics)
#   - Relation ref integrity (prune relations referencing non-existent IDs)
#   - Group member ref integrity
#   - Annotation target ref integrity
#   - Count normalization (textual multiplicity to integer)
#   - Role normalization (support keywords → anchor, crown keywords → cap)
#   - Context component pruning (physical objects)
#
# It does NOT handle:
#   - Shape diversity scoring/repair (VisualGate)
#   - Scale/importance contrast scoring (VisualGate)
#   - Visual recognizability scoring (VisualGate)
#   - Connector presence checks (VisualGate)
# ============================================================================

class BlueprintGate:
    """
    Structural validation gate between Stage 2 (Blueprint Compilation) and Visual Scorer.
    Validates JSON structure, required fields, enum boundaries, and ref integrity.
    Does NOT perform any visual quality scoring or visual repairs.
    """
    
    VALID_PATTERNS = {"central_peripheral", "hierarchical", "radial", "network", "field", "hybrid"}
    
    # Synonym → canonical mapping for LLM-generated relation types
    RELATION_SYNONYM_MAP = {
        # contains / enclosure family
        "is_located_within": "contains",
        "located_in": "contains",
        "found_in": "contains",
        "resides_in": "contains",
        "embedded_in": "contains",
        "housed_in": "contains",
        "inside": "contains",
        "within": "contains",
        "exists_in": "contains",
        "encloses": "contains",
        "enclosed_by": "part_of",
        "wraps": "contains",
        "houses": "contains",
        # structural support / attachment family
        "holds": "supports",
        "bears": "supports",
        "rests_on": "supports",
        "sits_on": "supports",
        "attached_to": "supports",
        # spatial / vertical family
        "has_on_top": "stacked_above",
        "on_top_of": "stacked_above",
        "above": "stacked_above",
        "below": "stacked_below",
        "beneath": "stacked_below",
        # flow / connection family
        "flows_into": "flows_to",
        "leads_to": "flows_to",
        "connects_to": "flows_to",
        "branches_from": "flows_to",
        "drains_into": "flows_to",
        "continues_as": "flows_to",
        "connected_to": "flows_to",
        "linked_to": "flows_to",
        "associated_with": "flows_to",
        "adjacent_to": "flows_to",
        # biological / structural
        "forms": "part_of",
        "composes": "part_of",
        "makes_up": "part_of",
        "is_part_of": "part_of",
        "belongs_to": "part_of",
        # activation / regulation
        "signals_to": "activates",
    }
    VALID_CONNECTORS = {"arrow", "bidirectional_arrow", "line", "curved_arrow", "dashed_line"}
    VALID_STRENGTHS = {"weak", "medium", "strong"}
    FORBIDDEN_IDS = {"box1", "node1", "object1", "component1"}
    VALID_ARRANGEMENTS = {"radial", "corner_based", "linear", "layered", "free"}
    VALID_SYMMETRIES = {"none", "bilateral", "radial", "four_fold"}
    VALID_DENSITIES = {"low", "medium", "high"}
    VALID_SEMANTIC_TYPES = {"structure", "tower", "building", "platform", "entrance", "organ", "resource", "institution", "force"}
    
    @classmethod
    def execute(cls, raw_json: str, semantic_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Returns: { "status": "accept|repair|reject", "data": Blueprint|None, "issues": [] }"""
        issues = []
        status = "accept"
        
        # Priority mapping from semantic context
        priority_map = {}
        if semantic_context and "entities" in semantic_context:
            priority_map = {e["id"].lower(): e.get("priority", "identity_core") for e in semantic_context["entities"]}
        
        # Robust JSON extraction
        try:
            import re
            raw_json = raw_json.strip()
            
            # Attempt 1: Direct parse
            try:
                data = json.loads(raw_json, strict=False)
            except json.JSONDecodeError:
                data = None
                
            # Attempt 2: Markdown block extraction
            if data is None:
                match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw_json, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1).strip(), strict=False)
                    except json.JSONDecodeError:
                        pass
                        
            # Attempt 3: Bracket extraction
            if data is None:
                start = raw_json.find('{')
                end = raw_json.rfind('}')
                if start != -1 and end != -1 and end > start:
                    clean = raw_json[start:end+1]
                    try:
                        data = json.loads(clean, strict=False)
                    except json.JSONDecodeError:
                        # Attempt 4: Clean trailing commas
                        clean = re.sub(r',\s*}', '}', clean)
                        clean = re.sub(r',\s*\]', ']', clean)
                        try:
                            data = json.loads(clean, strict=False)
                        except json.JSONDecodeError:
                            pass
                            
            if data is None:
                return {"status": "reject", "data": None, "issues": ["Invalid JSON structure."]}
                
        except Exception as e:
            return {"status": "reject", "data": None, "issues": [f"Invalid JSON structure (Parsing crashed: {e})."]}
            
        # Contract verification
        validate_incoming(data, "BlueprintGate", ["pattern", "geometric_components"])
            
        # Step 1: Top Level Field Validation & Repair
        required_fields = {
            "pattern": None, 
            "geometric_components": [], 
            "semantic_relations": [], 
            "groups": [], 
            "contextual_annotations": [], 
            "structure": {}, 
            "constraints": {},
            "explanations": {"intro": "", "layout_logic": ""}
        }
        for field, default in required_fields.items():
            if field not in data:
                if field == "pattern":
                    return {"status": "reject", "data": None, "issues": ["Missing required top-level field: pattern"]}
                data[field] = default
                issues.append(f"Repaired missing top-level field: {field}")
                status = "repair"
                
        # Step 2: Pattern Validation
        pattern = data.get("pattern", "")
        if pattern not in cls.VALID_PATTERNS:
            return {"status": "reject", "data": None, "issues": [f"Invalid pattern: {pattern}"]}
            
        # Step 3, 4, 5, 6: Geometric Component Validation
        raw_components = data.get("geometric_components", [])
        normalized_components = []
        valid_component_ids = set()
        
        for c in raw_components:
            if not isinstance(c, dict):
                issues.append(f"Rejected non-dictionary geometric_component: {c}")
                status = "repair"
                continue
                
            cid = c.get("id", "")
            if cid in cls.FORBIDDEN_IDS or not cid:
                return {"status": "reject", "data": None, "issues": [f"Invalid or generic component ID: {cid}"]}
                
            if cid in valid_component_ids:
                return {"status": "reject", "data": None, "issues": [f"Duplicate component ID: {cid}"]}
            valid_component_ids.add(cid)
            
            sem_type = c.get("semantic_type", "structure").lower()
            if sem_type not in cls.VALID_SEMANTIC_TYPES:
                sem_type = "structure"
                status = "repair"
                issues.append(f"Repaired semantic_type to structure for {cid}")
                
            label = c.get("label", cid)
            
            shape = c.get("shape", "box").lower()
            if shape not in VALID_SHAPES: 
                shape = "box"
                status = "repair"
                issues.append(f"Repaired shape to box for {cid}")
                
            role = c.get("role", "node").lower()
            
            # Support Role Normalization
            support_kws = ["platform", "base", "foundation", "support", "plinth"]
            is_support = sem_type in ["platform", "structure"] and any(kw in cid.lower() or kw in label.lower() for kw in support_kws)
            if is_support:
                if role != "anchor":
                    role = "anchor"
                    status = "repair"
                    issues.append(f"Normalized support role to anchor for {cid}")
            
            if any(kw in cid.lower() or kw in label.lower() for kw in ["dome", "roof", "spire", "finial", "crown"]):
                if role != "cap":
                    role = "cap"
                    status = "repair"
                    issues.append(f"Auto-repaired role to cap for crown element {cid}")
            elif role not in VALID_ROLES:
                role = "node"
                status = "repair"
                issues.append(f"Repaired role to node for {cid}")
                
            size = c.get("size_hint", "medium").lower()
            if size not in VALID_SIZE_HINTS:
                if size in ["very_large", "huge", "massive", "giant"]:
                    size = "extra_large"
                else:
                    size = "medium"
                status = "repair"
                issues.append(f"Repaired size to {size} for {cid}")
                
            rel = c.get("vertical_relation", "none").lower()
            # Fuzzy relation repair map — preserve spatial meaning
            if rel not in VALID_VERTICAL_RELATIONS:
                old_rel = rel
                if any(x in rel for x in ["atop", "on_top", "above", "top"]):
                    rel = "above"
                elif any(x in rel for x in ["base", "under", "below", "beneath"]):
                    rel = "below"
                elif any(x in rel for x in ["adjacent", "beside", "next"]):
                    rel = "adjacent"
                elif "stack" in rel:
                    rel = "stacked"
                elif any(x in rel for x in ["contained", "inside", "within", "enclosed"]):
                    rel = "inside"
                elif any(x in rel for x in ["enclos", "contain", "surround", "wrap", "fill"]):
                    rel = "container"
                else:
                    rel = "none"
                status = "repair"
                issues.append(f"Fuzzy repaired vertical_relation '{old_rel}' to '{rel}' for {cid}")
            
            importance = c.get("importance", "").lower()
            if importance not in {"high", "medium", "low"}:
                # Recover from priority_map if available
                prio = priority_map.get(cid.lower(), "support_core")
                prio_to_imp = {
                    "identity_core": "high",
                    "support_core": "medium",
                    "context_optional": "low"
                }
                importance = prio_to_imp.get(prio, "medium")
                status = "repair"
                issues.append(f"Recovered importance '{importance}' from Stage 1 priority '{prio}' for {cid}")
                
            try:
                raw_count = c.get("count", 1)
                # Check for string multiplicity before falling back to 1
                if isinstance(raw_count, str) and raw_count.lower() in ["multiple", "many", "several", "some"]:
                    count = 3
                    status = "repair"
                    issues.append(f"Repaired textual multiplicity '{raw_count}' to safe minimum 3 for {cid}")
                else:
                    count = int(raw_count)
                    if count < 1: 
                        count = 1
                        status = "repair"
                        issues.append(f"Repaired count to 1 for {cid}")
            except (ValueError, TypeError):
                count = 1
                status = "repair"
                issues.append(f"Repaired missing count to 1 for {cid}")
            
            resolved_shape = c.get("resolved_shape", "").lower().strip()
            if not resolved_shape or resolved_shape not in VALID_SHAPES:
                    resolved_shape = shape  # fall back to shape if missing/invalid

            color_hint = c.get("color_hint", "neutral")
            layout_hint = c.get("layout_hint", "none")

            normalized_components.append(ComponentInput(
                id=cid, semantic_type=sem_type, label=label, shape=shape,
                resolved_shape=resolved_shape,
                role=role, count=count, size_hint=size,
                vertical_relation=rel, importance=importance,
                color_hint=color_hint, layout_hint=layout_hint
            ))
            
        # Context Component Pruning for Physical Objects
        category = semantic_context.get("category") if semantic_context else None
        if category == "physical_object":
            has_core = any(c.role == "central" or c.importance == "high" for c in normalized_components)
            if has_core:
                context_kws = ["garden", "flanking", "surrounding", "context", "background", "plaza", "yard", "tree", "boundary", "wall"]
                context_comps = []
                core_comps = []
                for c in normalized_components:
                    if c.importance == "low" or any(kw in c.id.lower() or kw in c.label.lower() for kw in context_kws):
                        context_comps.append(c)
                    else:
                        core_comps.append(c)
                
                if context_comps:
                    normalized_components = core_comps
                    if "contextual_annotations" not in data:
                        data["contextual_annotations"] = []
                    for c in context_comps:
                        valid_component_ids.remove(c.id)
                        data["contextual_annotations"].append({"id": f"ano_{c.id}", "text": f"Context element: {c.label}", "type": "label"})
                    status = "repair"
                    issues.append(f"Pruned {len(context_comps)} context geometries into annotations to preserve core identity.")
            
        # Step 7, 8, 9, 10: Semantic Relation Validation
        # Normalize field names: accept source/target, from/to, AND from_id/to_id
        normalized_relations = []
        raw_relations = data.get("semantic_relations", [])
        valid_relation_ids = set()
        
        for r in raw_relations:
            if not isinstance(r, dict):
                issues.append(f"Rejected non-dictionary relation: {r}")
                status = "repair"
                continue
            
            # Read from ALL possible field name variants
            from_id = r.get("from_id") or r.get("source") or r.get("from") or ""
            to_id = r.get("to_id") or r.get("target") or r.get("to") or ""
            
            # A relation is only rejected if BOTH variants are absent or empty
            if not from_id or not to_id:
                status = "repair"
                issues.append(f"Rejected relation with missing component ID: '{from_id}' -> '{to_id}'")
                continue
                
            if from_id not in valid_component_ids or to_id not in valid_component_ids:
                status = "repair"
                issues.append(f"Rejected relation with unknown component ID: {from_id} -> {to_id}")
                continue
                
            if from_id == to_id:
                status = "repair"
                issues.append(f"Rejected self relation on {from_id}")
                continue
                
            # Read relation_type from either "relation_type" or "type"
            orig_rtype = r.get("relation_type") or r.get("type") or "flows_to"
            rtype = orig_rtype
            
            # Check for inverted "contains" semantics
            if any(k in orig_rtype.lower() for k in ["_within", "_inside", "located_in", "found_in", "resides_in", "embedded_in", "housed_in"]):
                # Swap source and target, and force to "contains"
                temp = from_id
                from_id = to_id
                to_id = temp
                rtype = "contains"
                status = "repair"
                issues.append(f"Swapped source/target for inverted location relation '{orig_rtype}', mapped to 'contains': {from_id} -> {to_id}")
            
            # 3-tier relation type resolution (minimal intervention):
            if rtype in VALID_RELATION_TYPES:
                pass  # Tier 1: Already canonical — keep as-is
            elif rtype in cls.RELATION_SYNONYM_MAP:
                # Tier 2: Known synonym — map to canonical
                old_rtype = rtype
                rtype = cls.RELATION_SYNONYM_MAP[rtype]
                status = "repair"
                issues.append(f"Mapped relation_type '{old_rtype}' → '{rtype}' for {from_id} -> {to_id}")
            else:
                # Tier 3: Unknown — last resort fallback
                old_rtype = rtype
                rtype = "flows_to"
                status = "repair"
                issues.append(f"[WARNING] Unknown relation_type '{old_rtype}' → fallback 'flows_to' for {from_id} -> {to_id}")
            
            conn = r.get("connector", "arrow")
            if conn not in cls.VALID_CONNECTORS:
                conn = "arrow"
                status = "repair"
                issues.append(f"Repaired connector to arrow for {from_id} -> {to_id}")
            
            strength = r.get("strength", "medium")
            if strength not in cls.VALID_STRENGTHS:
                strength = "medium"
                status = "repair"
                issues.append(f"Repaired strength to medium for {from_id} -> {to_id}")
            
            rel_id = f"{from_id}_{rtype}_{to_id}"
            valid_relation_ids.add(rel_id)
            
            normalized_relations.append(RelationInput(
                from_id=from_id,
                to_id=to_id,
                relation_type=rtype,
                connector=conn,
                label=r.get("label", ""),
                strength=strength
            ))
            
        # Step 11: Group Validation
        normalized_groups = []
        raw_groups = data.get("groups", [])
        for g in raw_groups:
            if not isinstance(g, dict):
                issues.append(f"Rejected non-dictionary group: {g}")
                status = "repair"
                continue
                
            gid = g.get("id", "")
            if not gid: continue
            
            glayout = g.get("layout", "central_peripheral")
            if glayout not in {"central_peripheral", "hierarchical", "radial", "network", "field"}:
                status = "repair"
                issues.append(f"Rejected group {gid} for invalid layout {glayout}")
                continue
                
            members = g.get("members", [])
            valid_members = [m for m in members if m in valid_component_ids]
            
            if len(valid_members) != len(members) or not valid_members:
                status = "repair"
                issues.append(f"Rejected group {gid} for missing/invalid members")
                continue # Reject group if any invalid member or empty
                
            normalized_groups.append(GroupInput(
                id=gid,
                layout=glayout,
                members=valid_members
            ))
            
        # Step 12: Hybrid Consistency Check
        if pattern == "hybrid":
            if len(normalized_groups) < 2:
                pattern = "central_peripheral" # Downgrade
                status = "repair"
                issues.append("Downgraded hybrid pattern due to insufficient groups.")
            
        # Step 13: Contextual Annotation Validation
        normalized_annotations = []
        raw_annotations = data.get("contextual_annotations", [])
        for a in raw_annotations:
            if not isinstance(a, dict):
                continue
                
            target = a.get("target", "")
            text = a.get("text", "")
            
            if not target or not text: continue
            
            # Target must be either a valid component ID or a rough match for a relation ID
            if target in valid_component_ids or target in valid_relation_ids or "_" in target:
                normalized_annotations.append(AnnotationInput(
                    target=target,
                    text=text
                ))
            
        # Step 14: Structure Validation
        struct_data = data.get("structure", {})
        arrangement = struct_data.get("arrangement", "free")
        if arrangement not in cls.VALID_ARRANGEMENTS:
            arrangement = "free"
            status = "repair"
            issues.append("Repaired structure arrangement to free.")
        
        structure = StructureDetails(
            arrangement=arrangement,
            levels=struct_data.get("levels", [])
        )
        
        # Step 15: Constraint Validation (Symmetry preservation)
        const_data = data.get("constraints", {})
        symmetry = const_data.get("symmetry", "none")
        if symmetry and symmetry not in cls.VALID_SYMMETRIES:
            symmetry = "none"
            status = "repair"
            issues.append(f"Repaired invalid constraint symmetry to none.")
        elif not symmetry:
            symmetry = "none"
        
        density = const_data.get("density", "medium")
        if density not in cls.VALID_DENSITIES:
            density = "medium"
            status = "repair"
            issues.append("Repaired missing constraint density to medium.")
            
        constraints = ConstraintsModel(
            symmetry=symmetry,
            density=density
        )
        
        expl_data = data.get("explanations", {})
        explanations = ExplanationsModel(
            intro=expl_data.get("intro", "No intro provided."),
            layout_logic=expl_data.get("layout_logic", "No layout logic provided.")
        )
        
        # Step 16 & 17: Return normalized executable blueprint
        bp = Blueprint(
            pattern=pattern,
            explanations=explanations,
            geometric_components=normalized_components,
            semantic_relations=normalized_relations,
            groups=normalized_groups,
            contextual_annotations=normalized_annotations,
            structure=structure,
            constraints=constraints
        )
        return {"status": status, "data": bp, "issues": issues}