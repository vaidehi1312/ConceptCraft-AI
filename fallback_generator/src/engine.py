"""
LayoutEngine Module
-------------------
RESPONSIBILITY: 
Orchestrates the translation of a conceptual semantic Blueprint into concrete 3D coordinates. 
It ingests the JSON output from the LLM, validates it, selects the appropriate layout 
algorithm, and packages the resulting spatial data for the 3D renderer.

FIXES APPLIED:
  1. resolved_shape is now explicitly carried into repacked_comps so it
     survives format_final_output and reaches Three.js
  2. ExplanationsModel parsing is null-safe — handles null, missing, or
     wrong-typed explanations from Gemini without silent empty-string failure
  3. intro / layout_logic written from blueprint.explanations with a
     nonempty-string guard so empty strings don't overwrite good values

STAGES HANDLED:
- Stage 8: Layout Engine Selector
- Stage 9: Coordinate Generation
"""
import json
import random
import dataclasses
import math
from typing import Dict, Any
from pipeline_contract import validate_incoming

from schema import (
    Blueprint, LayoutResult, ComponentInput,
    StructureDetails, ConstraintsModel, RelationInput, GroupInput, AnnotationInput, ExplanationsModel
)
from layouts import (
    BaseLayoutEngine,
    CentralPeripheralLayout,
    HierarchicalLayout,
    RadialLayout,
    NetworkLayout,
    FieldLayout,
    LinearLayout,
    SequentialMorphologyLayout,
    BilateralMotifLayout,
    ClusteredCoreLayout,
    TubularMorphologyLayout
)

# Import these here so helical path can reference them
from schema import OutputComponent, Position, Scale


class LayoutEngine:
    """Orchestrator for the Fallback Generation Layouts"""

    def __init__(self):
        self.engines: Dict[str, BaseLayoutEngine] = {
            "central_peripheral": CentralPeripheralLayout(),
            "hierarchical": HierarchicalLayout(),
            "radial": RadialLayout(),
            "network": NetworkLayout(),
            "field": FieldLayout(),
            "linear": LinearLayout(),
            "sequential_morphology": SequentialMorphologyLayout(),
            "bilateral_motif": BilateralMotifLayout(),
            "clustered_core": ClusteredCoreLayout(),
            "tubular_morphology": TubularMorphologyLayout()
        }

    def _parse_blueprint(self, data: dict) -> Blueprint:
        components = [ComponentInput(**c) for c in data.get("geometric_components", [])]
        relations = [RelationInput(**r) for r in data.get("semantic_relations", [])]
        groups = [GroupInput(**g) for g in data.get("groups", [])]
        annotations = [AnnotationInput(**a) for a in data.get("contextual_annotations", [])]

        structure = StructureDetails(**data.get("structure", {}))
        constraints = ConstraintsModel(**data.get("constraints", {}))

        # ── FIX: null-safe explanations parsing ──────────────────────────────
        # Gemini may return: null, {}, {"intro": null, ...}, or correct dict.
        # All cases must produce a valid ExplanationsModel without crashing.
        raw_expl = data.get("explanations") or {}
        if not isinstance(raw_expl, dict):
            raw_expl = {}
        # Sanitize individual fields — replace None with empty string
        safe_expl = {
            "intro": raw_expl.get("intro") or "",
            "layout_logic": raw_expl.get("layout_logic") or ""
        }
        explanations = ExplanationsModel(**safe_expl)

        return Blueprint(
            pattern=data.get("pattern"),
            explanations=explanations,
            geometric_components=components,
            semantic_relations=relations,
            groups=groups,
            contextual_annotations=annotations,
            structure=structure,
            constraints=constraints,
            morphology_family=data.get("morphology_family"),
            morphology_params=data.get("morphology_params"),
            connectors=data.get("connectors", [])
        )

    def select_layout_engine(self, blueprint: Blueprint, category: str = "unknown"):
        """
        Two-stage engine selector.
        Stage A: Pattern selects provisional engine.
        Stage B: Semantic confidence overrides provisional engine if confidence is high.
        Returns: (engine, engine_name, effective_pattern, override_reason)
        """
        pattern = blueprint.pattern
        effective_pattern = pattern
        override_reason = None

        arrangement = blueprint.structure.arrangement

        core_comps = [c for c in blueprint.geometric_components if c.importance == "high" or c.role == "central"]
        core_count = sum(c.count for c in core_comps)

        all_labels_ids = " ".join([c.id.lower() + " " + c.label.lower() for c in blueprint.geometric_components])

        sequence_roles = {"source", "entry", "sink", "output", "stage"}
        tubular_cues = ["duct", "tubule", "loop", "vascular", "tract", "vein", "artery", "intestine", "canal", "flow"]
        paired_connector_cues = ["dna", "rna", "ladder", "pair", "strand", "rail", "backbone", "chromosome", "dimer"]
        cluster_cues = ["alveoli", "cluster", "pack", "bundle", "lobe"]

        has_seq_roles = any(c.role in sequence_roles for c in blueprint.geometric_components)
        has_tube_semantics = any(cue in all_labels_ids for cue in tubular_cues)
        has_paired_semantics = any(cue in all_labels_ids for cue in paired_connector_cues)
        has_cluster_semantics = any(cue in all_labels_ids for cue in cluster_cues)
        has_multiplicity = any(c.count >= 2 for c in blueprint.geometric_components)

        SKIP_STAGE_B_FAMILIES = {
            "architectural_assembly", "process_sequence", "symbolic_abstract",
            "crystalline_lattice", "modular_grid"
        }

        if blueprint.morphology_family in SKIP_STAGE_B_FAMILIES:
            print(f"      Stage B overrides skipped — {blueprint.morphology_family} morphology family")
        else:
            if category in ["biological_structure", "chemical_structure", "process"] and has_multiplicity and has_paired_semantics:
                effective_pattern = "bilateral_motif"
                override_reason = "DNA/ladder semantics detected"

            elif category in ["biological_structure", "process"] and has_tube_semantics:
                pathway_matches = sum(1 for cue in tubular_cues if cue in all_labels_ids)
                if pathway_matches >= 3:
                    effective_pattern = "tubular_morphology"
                    override_reason = "complex tubular loop semantics detected"

            elif category in ["biological_structure", "process"] and arrangement == "linear" and (has_seq_roles or has_tube_semantics):
                effective_pattern = "sequential_morphology"
                override_reason = "directional sequential semantics detected"

            elif (category in ["biological_structure", "chemical_structure"] and has_cluster_semantics) or \
                 (pattern in ["central_peripheral", "radial"] and (len(core_comps) == 1 and core_comps[0].count > 1) or (core_count > 1 and arrangement != "linear")):
                effective_pattern = "clustered_core"
                override_reason = "core cluster genetics detected"

            elif pattern in ["central_peripheral", "radial"] and arrangement == "linear" and core_count > 1:
                effective_pattern = "linear"
                override_reason = "pattern conflicts with linear arrangement for sequential cores"

        engine = self.engines.get(effective_pattern)
        if not engine:
            effective_pattern = "central_peripheral"
            override_reason = f"Unknown pattern '{blueprint.pattern}'. Falling back."
            engine = self.engines["central_peripheral"]

        return engine, type(engine).__name__, effective_pattern, override_reason

    def generate_layout(self, blueprint_json: str, scenario_name: str = "default", category: str = "unknown") -> str:
        try:
            data = json.loads(blueprint_json)
            validate_incoming(data, "LayoutEngine", ["pattern", "geometric_components", "semantic_relations"])
            blueprint = self._parse_blueprint(data)
        except Exception as e:
            raise ValueError(f"Failed to parse or validate Blueprint JSON: {e}")

        pattern = blueprint.pattern

        # ── FIX: Build resolved_shape lookup from raw data BEFORE layout runs ─
        # The layout engines use ComponentInput.shape, but resolved_shape is a
        # separate field set by the morphology pipeline. We need to carry it
        # through repacked_comps → format_final_output → Three.js.
        resolved_shape_lookup = {}
        for c in data.get("geometric_components", []):
            cid = c.get("id", "")
            # Priority: resolved_shape set by pipeline → shape field → None
            rs = c.get("resolved_shape") or c.get("shape") or None
            if cid and rs:
                resolved_shape_lookup[cid] = rs

        # 1. Coordinate Generation (Group aware)
        all_output_components = []
        placed_ids = set()

        y_group_offset = 0.0

        if blueprint.groups and pattern == "hybrid":
            print(f"HYBRID GROUPS: {blueprint.groups}")
            for i, group in enumerate(blueprint.groups):
                print(f"RUNNING GROUP: {group.id} {group.layout}")
                engine = self.engines.get(group.layout, CentralPeripheralLayout())

                group_comps = []
                for m_id in group.members:
                    comp = next((c for c in blueprint.geometric_components if c.id == m_id), None)
                    if comp:
                        group_comps.append(comp)
                    else:
                        print(f"WARNING: Group member '{m_id}' not found in blueprint components.")

                sub_bp = dataclasses.replace(blueprint, geometric_components=group_comps)
                group_out_comps = engine.process(sub_bp)

                anchor_x, anchor_y, anchor_z = 0.0, 0.0, 0.0
                if i > 0:
                    radius = 20.0
                    angle = (i - 1) * (2 * math.pi / max(1, len(blueprint.groups) - 1))
                    anchor_x = radius * math.cos(angle)
                    anchor_z = radius * math.sin(angle)
                    anchor_y = 0.0

                for oc in group_out_comps:
                    oc.position.x += anchor_x
                    oc.position.y += anchor_y
                    oc.position.z += anchor_z
                    all_output_components.append(oc)
                    placed_ids.add(oc.original_id)

            if not all_output_components:
                print("WARNING: Hybrid fallback triggered. No coordinates returned.")
                if blueprint.groups:
                    fallback_engine = self.engines.get(blueprint.groups[0].layout, CentralPeripheralLayout())
                    all_output_components = fallback_engine.process(blueprint)
                    for oc in all_output_components:
                        placed_ids.add(oc.original_id)
        else:
            out_bp_dict = dataclasses.asdict(blueprint)

            from layout_morphology_bridge import apply_morphology_to_layout, generate_helix_positions

            layout_params = apply_morphology_to_layout(out_bp_dict, {})
            forced = layout_params.get("forced_pattern")

            if forced == "helical":
                print(f"      Layout pattern: helical (source: morphology_bridge)")
                heli_comps = generate_helix_positions(out_bp_dict.get("geometric_components", []), layout_params)

                for hc in heli_comps:
                    pos = hc["position"]
                    orig_comp = hc["original_component"]
                    oc = OutputComponent(
                        id=orig_comp["id"],
                        original_id=orig_comp["id"],
                        semantic_type=orig_comp.get("semantic_type", "node"),
                        label=orig_comp.get("label", ""),
                        shape=orig_comp.get("resolved_shape", "sphere"),
                        position=Position(x=pos[0], y=pos[1], z=pos[2]),
                        scale=Scale(x=1.0, y=1.0, z=1.0)
                    )
                    all_output_components.append(oc)
                    placed_ids.add(oc.original_id)
                engine = self.engines.get("central_peripheral")

            elif forced:
                heuristic_engine, _, heuristic_pattern, _ = self.select_layout_engine(blueprint, category)

                engine = self.engines.get(forced)
                if not engine:
                    print(f"      [!] morphology_bridge forced unknown pattern '{forced}', falling back to engine heuristics")
                    engine = heuristic_engine
                    print(f"      Layout pattern: {heuristic_pattern} (source: engine_heuristic)")
                elif forced == heuristic_pattern:
                    print(f"      Layout pattern: {forced} (source: engine — matches morphology)")
                else:
                    print(f"      Layout pattern: {forced} (source: morphology_bridge, overrode: {heuristic_pattern})")

                engine.morphology_params = layout_params
                all_output_components = engine.process(blueprint)
                for oc in all_output_components:
                    placed_ids.add(oc.original_id)

            else:
                engine, _, effective_pattern, override_reason = self.select_layout_engine(blueprint, category)
                print(f"      Layout pattern: {effective_pattern} (source: engine_heuristic)")
                if override_reason:
                    print(f"      [~] Engine override reason: {override_reason}")

                engine.morphology_params = layout_params
                all_output_components = engine.process(blueprint)
                for oc in all_output_components:
                    placed_ids.add(oc.original_id)

        # 2. Catchment for unassigned components
        unplaced_comps = [c for c in blueprint.geometric_components if c.id not in placed_ids]
        if unplaced_comps:
            fallback_engine = self.engines["central_peripheral"]
            sub_bp = dataclasses.replace(blueprint, geometric_components=unplaced_comps)
            unplaced_outs = fallback_engine.process(sub_bp)
            for oc in unplaced_outs:
                oc.position.y += y_group_offset
                all_output_components.append(oc)

        if pattern == "hybrid":
            print(f"FINAL HYBRID COMPONENTS: {all_output_components}")

        # ====================================================================
        # SPATIAL PASSES
        # ====================================================================
        from spatial_passes import (
            apply_importance_scale,
            apply_containment_pass,
            apply_vertical_stacking_pass,
            apply_vertical_relation_hints
        )

        for oc in all_output_components:
            bp_comp = next((c for c in blueprint.geometric_components if c.id == oc.original_id), None)
            if bp_comp:
                oc.metadata["importance"] = bp_comp.importance
                oc.metadata["size_hint"] = bp_comp.size_hint

        apply_importance_scale(all_output_components)
        apply_containment_pass(all_output_components, blueprint.semantic_relations)
        apply_vertical_stacking_pass(all_output_components, blueprint.semantic_relations)
        apply_vertical_relation_hints(all_output_components, blueprint.geometric_components)

        print(f"      [SPATIAL PASSES] Scale + Containment + Stacking applied to {len(all_output_components)} components")

        tube_path = getattr(engine, 'tube_path', None) if not (blueprint.groups and pattern == "hybrid") else None

        out_bp_dict = dataclasses.asdict(blueprint)

        # ── FIX: carry resolved_shape into repacked_comps ────────────────────
        # format_final_output rebuilds the component list from repacked_comps.
        # Without resolved_shape here it is always missing in the final JSON
        # that Three.js receives, causing the box fallback to trigger.
        repacked_comps = []
        for oc in all_output_components:
            orig = next((c for c in out_bp_dict.get("geometric_components", []) if c["id"] == oc.original_id), {})

            # Resolve shape: pipeline lookup → orig dict resolved_shape → orig shape → sphere
            final_resolved_shape = (
                resolved_shape_lookup.get(oc.original_id)
                or orig.get("resolved_shape")
                or orig.get("shape")
                or "sphere"
            )

            repacked_comps.append({
                "id": oc.id,
                "original_id": oc.original_id,
                "label": oc.label,
                "resolved_shape": final_resolved_shape,   # ← THE FIX
                "shape": final_resolved_shape,             # keep both in sync
                "original_component": orig,
                "position": [oc.position.x, oc.position.y, oc.position.z],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [oc.scale.x, oc.scale.y, oc.scale.z]
            })

        # 3. Post-Process Connectors via Morphology Bridge
        from layout_morphology_bridge import resolve_connector_positions, format_final_output
        computed_connectors = resolve_connector_positions(out_bp_dict, repacked_comps)

        # 4. Strict formatting
        final_out = format_final_output(out_bp_dict, repacked_comps, computed_connectors)

        # 5. Reinject fields that format_final_output doesn't natively enforce
        final_out["scenario"] = scenario_name
        final_out["pattern"] = pattern
        final_out["tube_path"] = tube_path

        # ── FIX: write intro + layout_logic with nonempty guard ──────────────
        # blueprint.explanations is always populated (null-safe parse above).
        # Only overwrite if the value is a real non-empty string.
        bp_intro = blueprint.explanations.intro or ""
        bp_layout_logic = blueprint.explanations.layout_logic or ""

        # Also check if format_final_output already wrote good values
        existing_intro = final_out.get("intro", "") or ""
        existing_logic = final_out.get("layout_logic", "") or ""

        final_out["intro"] = bp_intro if bp_intro else existing_intro
        final_out["layout_logic"] = bp_layout_logic if bp_layout_logic else existing_logic

        print(f"      [explanations] intro={repr(final_out['intro'][:60]) if final_out['intro'] else 'EMPTY'}")
        print(f"      [explanations] layout_logic={repr(final_out['layout_logic'][:60]) if final_out['layout_logic'] else 'EMPTY'}")

        # ── FIX: ensure resolved_shape propagates into final components list ─
        # format_final_output may rebuild the components list in its own format.
        # Walk the output and patch resolved_shape from repacked_comps if missing.
        rp_shape_map = {rc["id"]: rc["resolved_shape"] for rc in repacked_comps}
        rp_shape_by_orig = {rc["original_id"]: rc["resolved_shape"] for rc in repacked_comps}

        for comp in final_out.get("components", []):
            if not comp.get("resolved_shape"):
                comp["resolved_shape"] = (
                    rp_shape_map.get(comp.get("id", ""))
                    or rp_shape_by_orig.get(comp.get("original_id", ""))
                    or "sphere"
                )

        return json.dumps(final_out, indent=2)