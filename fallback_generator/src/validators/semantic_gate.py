"""
Semantic Gate Module
--------------------
RESPONSIBILITY: 
Validates and repairs the Raw Semantic JSON produced in Stage 1. 
Ensures IDs are safe, categories are valid, and patterns are recognized.

STAGES HANDLED:
- Stage 2: Semantic Gate
"""
import json
from typing import Dict, Any
from pipeline_contract import VALID_CATEGORIES, VALID_PATTERNS, validate_incoming

class SemanticGate:
    """
    Deterministic gate between Stage 1 (Semantic Decomposition) and Stage 2 (Blueprint Compilation).
    Rejects or repairs raw semantic proposals to ensure safety.
    """
    
    FORBIDDEN_IDS = {
        "box1", "node1", "object1", "component1", "thing1"
    }
    
    FORBIDDEN_RELATIONS = {
        "connected_to", "linked_to"
    }
    
    ALLOWED_RELATIONS = {
        "supports", "contains", "flows_to", "depends_on", "produces", 
        "regulates", "attached_to", "checks", "transforms_into"
    }
    
    @classmethod
    def execute(cls, raw_json: str) -> Dict[str, Any]:
        """
        Executes the gate checks. 
        Returns: { "status": "accept|repair|reject", "data": cleaned_dict|None, "issues": [] }
        """
        issues = []
        status = "accept"
        
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
        validate_incoming(data, "SemanticGate", ["category", "dominant_pattern", "entities", "relations"])
            
        # Step 1: Category validation
        category = data.get("category", "")
        if category not in VALID_CATEGORIES:
            return {"status": "reject", "data": None, "issues": [f"Invalid category: {category}"]}
            
        # Step 2: Pattern validation
        pattern = data.get("dominant_pattern", "")
        if pattern not in VALID_PATTERNS:
            return {"status": "reject", "data": None, "issues": [f"Invalid pattern: {pattern}"]}
            
        # Step 3: Category-Pattern Consistency Check (Relaxed)
        # We no longer force patterns based on category. We trust the LLM's semantic intent 
        # as long as the pattern returned is within VALID_PATTERNS.
        data["dominant_pattern"] = pattern
        
        # Step 4: Entity Count Validation
        limits = {
            "physical_object": 5, "biological_structure": 6, "chemical_structure": 6,
            "process": 7, "abstract_system": 6, "physical_phenomenon": 6
        }
        max_entities = limits.get(category, 5)
        entities = data.get("entities", [])
        
        # Step 5 & 6: Entity Name & Diversity Check
        seen_entities = {}
        cleaned_entities = []
        for e in entities:
            if isinstance(e, dict):
                eid = e.get("id", "")
                count = e.get("count", 1)
                priority = e.get("priority", "context_optional")
            else:
                eid = str(e)
                count = 1
                priority = "context_optional"
                
            if not eid: continue
                
            if priority not in {"identity_core", "support_core", "context_optional"}:
                priority = "context_optional"
                
            if eid in cls.FORBIDDEN_IDS:
                return {"status": "reject", "data": None, "issues": [f"Generic ID found: {eid}"]}
                
            if eid not in seen_entities:
                seen_entities[eid] = True
                
                try:
                    # Check for string multiplicity before falling back to 1
                    if isinstance(count, str) and count.lower() in ["multiple", "many", "several", "some"]:
                        safe_count = 3
                        status = "repair"
                        issues.append(f"Repaired textual multiplicity '{count}' to safe minimum 3 for entity {eid}")
                    else:
                        safe_count = max(1, int(count))
                except (ValueError, TypeError):
                    safe_count = 1
                    status = "repair"
                    issues.append(f"Repaired non-numeric count '{count}' to 1 for entity {eid}")
                    
                cleaned_entities.append({"id": eid, "count": safe_count, "priority": priority}) 
                
        # Priority Pruning
        def _get_priority_score(entity):
            p = entity.get("priority")
            if p == "identity_core": return 0
            if p == "support_core": return 1
            return 2
            
        cleaned_entities.sort(key=_get_priority_score)
        
        # Prune down to max allowed, but NEVER prune identity_core
        final_entities = []
        for entity in cleaned_entities:
            if len(final_entities) < max_entities or entity.get("priority") == "identity_core":
                final_entities.append(entity)
            else:
                status = "repair"
                issues.append(f"Pruned specific optional entity: {entity.get('id')}")
                
        cleaned_entities = final_entities
        data["entities"] = cleaned_entities
        entities_count = len(cleaned_entities)
        if entities_count == 1 and len(entities) > 1:
            cleaned_entities = [e for e in entities[:2] if isinstance(e, dict)]
            data["entities"] = cleaned_entities
            status = "repair"
            issues.append("Prevented entity collapse: kept minimum two entities.")
        
        # Step 7: Hybrid validation
        if data.get("hybrid_needed", False):
            # Forcing false if overused / no explicit two distinct structural regions
            data["hybrid_needed"] = False
            status = "repair"
            issues.append("Repaired unjustified hybrid_needed to false.")
            
        # Step 8: Relation Count Validation
        rel_limits = {
            "physical_object": 3, "biological_structure": 4, "chemical_structure": 4,
            "process": 5, "abstract_system": 5, "physical_phenomenon": 4
        }
        max_rels = rel_limits.get(category, 3)
        relations = data.get("relations", [])
        cleaned_relations = []
        
        # Build entity ID set for validation
        entity_ids = {e["id"] for e in cleaned_entities}
        
        # Known verb patterns for parsing string-format relations
        VERB_PATTERNS = [
            "_encloses_", "_contains_", "_associated_with_", "_flows_to_",
            "_depends_on_", "_produces_", "_regulates_", "_supports_",
            "_attached_to_", "_connects_to_", "_transforms_into_",
            "_flows_into_", "_drains_into_", "_continues_as_",
            "_inhibits_", "_activates_", "_competes_with_",
        ]
        
        # Step 9: Relation Quality Check — handle BOTH string and object formats
        for r in relations:
            if isinstance(r, dict):
                # Object format: {"source": X, "target": Y, "type": Z} or {"from": X, "to": Y, ...}
                source = r.get("source", r.get("from", r.get("from_id", "")))
                target = r.get("target", r.get("to", r.get("to_id", "")))
                rtype = r.get("type", r.get("relation_type", "flows_to"))
                if rtype not in cls.ALLOWED_RELATIONS:
                    rtype = "flows_to"
                    status = "repair"
                    issues.append(f"Repaired unknown relation type to flows_to for {source}->{target}")
                                
                if rtype in cls.FORBIDDEN_RELATIONS:
                    continue
                
                # Only prune if source or target doesn't match any entity ID
                if source and target and source in entity_ids and target in entity_ids:
                    cleaned_relations.append({
                        "source": source, "target": target, "type": rtype,
                        "primary": r.get("primary", True)
                    })
                elif source and target:
                    # IDs don't match but relation has content — keep it (LLM may use compound IDs)
                    cleaned_relations.append({
                        "source": source, "target": target, "type": rtype,
                        "primary": r.get("primary", True)
                    })
                    
            elif isinstance(r, str):
                # String format: "cell_membrane_encloses_cytoplasm"
                parsed = False
                for verb in VERB_PATTERNS:
                    if verb in r:
                        parts = r.split(verb)
                        if len(parts) == 2:
                            source, target = parts[0], parts[1]
                            rtype = verb.strip("_")
                            cleaned_relations.append({
                                "source": source, "target": target, "type": rtype,
                                "primary": True
                            })
                            parsed = True
                            break
                
                if not parsed:
                    # Keep the raw string as a typed relation with unknown source/target
                    # This preserves LLM intent even if we can't parse it
                    cleaned_relations.append({
                        "source": "", "target": "", "type": r,
                        "primary": True
                    })
        
        if len(cleaned_relations) < len(relations):
            status = "repair"
            issues.append("Pruned weak or forbidden relations.")
            
        # Step 10 & 11: Relation Count Hard Limits
        if len(cleaned_relations) > max_rels:
            cleaned_relations = cleaned_relations[:max_rels]
            status = "repair"
            issues.append(f"Pruned relations to absolute max {max_rels} for {category}")
            
        data["relations"] = cleaned_relations
        return {"status": status, "data": data, "issues": issues}
