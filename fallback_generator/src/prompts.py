"""
LLM Prompts Module
------------------
Two-step pipeline:
  Stage 1 — Spatial Artist Brief: describes concept like briefing a 3D modeler
  Stage 2 — Blueprint Compiler: translates that brief into precise 3D JSON
"""

# ==============================================================================
# STAGE 1 — SPATIAL ARTIST BRIEF
# ==============================================================================
STAGE_1_PROMPT = """You are briefing a 3D modeler who has never seen this concept before.
They need enough detail to build a clean, educational 3D model without looking anything up.

YOUR OUTPUT IS ONLY JSON. NO PROSE. NO MARKDOWN FENCES.

==================================================
EDUCATIONAL SIMPLIFICATION RULE
==================================================
Always simplify for visual clarity:
- Atom: show 3 electrons max, not actual electron count
- Cell: show 5-6 key organelles, not all 20+
- Solar system: show sun + 4-5 planets, not all 8
- DNA: show one full twist (10 base pairs), not millions
- Crystal: show a 3x3 unit cell, not full lattice
The goal is RECOGNITION, not scientific completeness.

==================================================
STEP 1 — CLASSIFY
==================================================
category (choose one):
  physical_object, biological_structure, chemical_structure,
  process, abstract_system, physical_phenomenon

dominant_pattern (choose one):
  radial        — physical center radiating outward (atom, sun, hurricane)
  hierarchical  — stacked levels top-to-bottom (pyramid, food chain, org chart)
  network       — peer nodes, NO dominant center (ecosystem, molecule bonds)
  central_peripheral — one dominant center + surrounding parts (cell, castle)
  sequential    — ordered steps in a flow (water cycle, digestion, circuit)
  field         — distributed in space (galaxy, magnetic field, gas cloud)

PATTERN DECISION RULES:
- Has a physical center others surround concentrically? → radial
- Has clear top-to-bottom ranking? → hierarchical  
- All parts are peers, no center dominates? → network
- One dominant hub + distinct surrounding parts? → central_peripheral
- Ordered process with direction? → sequential
- Pyramid, building, tree → hierarchical (NEVER network or radial)
- Atom, sun, cell nucleus → radial or central_peripheral
- Ecosystem, food web → network

==================================================
STEP 2 — DESCRIBE EACH COMPONENT AS A 3D ARTIST WOULD
==================================================
For each component specify:

SIZE: Give as fraction of total concept size
  "nucleus takes up 1/10 of atom diameter"
  "pyramid base is as wide as it is tall"
  "sun is 10x larger than any planet shown"

POSITION: Give exact spatial relationship
  "nucleus sits dead center at origin"
  "electrons orbit at 3x the nucleus radius"
  "apex sits directly above the base center"

SHAPE: Be specific
  "nucleus = solid dense sphere"
  "pyramid = perfect cone shape"
  "DNA backbone = twisted cylinder"
  "crystal unit = cube lattice"

COLOR (scientifically accurate where known):
  Sun/stars         → bright yellow-orange (#FFA500)
  Nucleus (atom)    → bright red-orange (#FF4500)
  Electrons         → electric blue (#00BFFF)
  Protons           → red (#FF0000)
  Neutrons          → gray (#888888)
  Mitochondria      → dark red (#8B0000)
  Cell nucleus      → purple (#800080)
  Cell membrane     → translucent green (#00FF7F at 50% opacity)
  Chloroplast       → green (#228B22)
  Water             → blue (#1E90FF)
  Bone/skeleton     → ivory (#FFFAF0)
  DNA strand A      → blue (#0000FF)
  DNA strand B      → orange (#FF8C00)
  For unknowns      → use visually distinct contrasting colors

EDUCATIONAL COUNT (simplified):
  Show minimum count for visual recognition
  "3 electrons shown (simplified from actual count)"
  "4 planets shown (inner solar system)"

==================================================
STEP 3 — SPATIAL RELATIONS
==================================================
CONCENTRIC/LAYERED structures (sun, atom, earth, onion):
  MUST use "contains" chaining from outermost to innermost.
  outer_layer contains middle_layer contains inner_core

HIERARCHICAL structures (pyramid, tree, food chain):
  Use "stacked_above": apex stacked_above middle stacked_above base

FLOW structures (water cycle, digestion):
  Use "flows_to" in sequence order

NEVER leave relations empty for layered or hierarchical concepts.

==================================================
STEP 4 — SIZE CLASS (for scale mapping)
==================================================
Assign size_class based on actual relative size:
  dominant  → largest element (nucleus in atom, base in pyramid, sun in solar system)
  large     → clearly bigger than average
  medium    → average
  small     → clearly smaller
  tiny      → very small relative to dominant (electron vs nucleus)

RADIAL RULE: innermost = dominant, each outer layer gets smaller size_class
HIERARCHICAL RULE: base/foundation = dominant, apex = small or tiny

==================================================
OUTPUT JSON SCHEMA — RETURN EXACTLY THIS
==================================================
{
  "category": "",
  "dominant_pattern": "",
  "concept_description": "2 sentences: what it is + what makes it visually distinctive",
  "spatial_logic": "1 sentence: why components are arranged this way",
  "entities": [
    {
      "id": "snake_case_id",
      "label": "Human Readable Label",
      "count": 1,
      "priority": "identity_core|support_core|context_optional",
      "size_class": "dominant|large|medium|small|tiny",
      "shape_description": "exact shape name: sphere|box|cone|cylinder|torus|hemisphere|icosphere",
      "spatial_role": "center|layer|orbit|apex|base|branch|node",
      "position_hint": "center|above_center|below_center|surrounding|orbiting|corner|sequential",
      "color_hex": "#RRGGBB",
      "color_name": "descriptive color name",
      "contains": ["id_of_entity_enclosed_by_this"],
      "educational_note": "why simplified (e.g. 3 electrons shown for clarity)"
    }
  ],
  "relations": [
    {
      "source": "entity_id",
      "target": "entity_id",
      "type": "contains|stacked_above|flows_to|attached_to|orbits|supports"
    }
  ],
  "scene_notes": "brief description of overall scene composition for the modeler"
}

==================================================
STRICT RULES
==================================================
- Return ONLY valid JSON — no prose, no markdown, no backticks
- Every entity MUST have color_hex and shape_description set
- Relations MUST be non-empty for layered, hierarchical, and flow concepts
- size_class MUST follow the RADIAL RULE and HIERARCHICAL RULE above
- dominant_pattern MUST reflect physical structure not conceptual domain
- Simplify counts for visual clarity
"""

def generate_stage_1_user_prompt(concept: str) -> str:
    return (
        f"Concept to visualize: \"{concept}\"\n\n"
        f"Brief a 3D modeler to build this. Output ONLY the JSON."
    )


# ==============================================================================
# STAGE 2 — BLUEPRINT COMPILER
# ==============================================================================
STAGE_2_PROMPT = """You are a 3D blueprint compiler for a Three.js educational visualization system.

You receive a spatial artist brief (JSON) and compile it into a precise 3D blueprint.
The blueprint feeds directly into a Three.js renderer — every field you set affects what the user sees.

YOUR OUTPUT IS ONLY JSON. NO PROSE. NO MARKDOWN FENCES.

==================================================
SHAPE MAPPING — MANDATORY
==================================================
Use shape_description from input. Map to these exact values:
  sphere      → sphere       (planets, nuclei, cells, atoms, electrons, stars)
  box         → box          (buildings, crystals, bases, platforms, blocks)
  cone        → cone         (pyramid body, apex, tip, funnel, mountain)
  cylinder    → cylinder     (pillars, tubes, DNA backbone, stems, columns)
  torus       → torus        (rings, orbits, loops, belts, donuts)
  hemisphere  → hemisphere   (domes, caps, bowls, half-spheres)
  icosphere   → icosphere    (viruses, geodesic structures, rough spheres)

Set BOTH "shape" AND "resolved_shape" to the SAME value.
resolved_shape MUST NEVER be empty, null, or missing.

PYRAMID RULE: A pyramid = ONE large cone for the body + ONE flat box for the base.
NEVER use cylinder for any part of a pyramid.

==================================================
SCALE MAPPING — MANDATORY
==================================================
Translate size_class from input to scale_override:
  dominant  → [4.0, 4.0, 4.0]
  large     → [2.5, 2.5, 2.5]
  medium    → [1.5, 1.5, 1.5]
  small     → [0.8, 0.8, 0.8]
  tiny      → [0.3, 0.3, 0.3]

Special overrides:
  cone (pyramid body)    → [3.0, 4.0, 3.0]   (wide base, tall)
  box (pyramid base)     → [4.5, 0.4, 4.5]   (wide flat platform)
  cylinder (pillar/tube) → [s, s*2.5, s]      (taller than wide)
  torus (orbit ring)     → [3.0, 0.2, 3.0]   (wide flat ring)

RADIAL SCALE RULE:
  Innermost entity = dominant [4.0,4.0,4.0]
  Each outer layer or orbit = progressively smaller
  Electrons/outermost particles = tiny [0.3,0.3,0.3]

==================================================
LAYOUT HINT MAPPING
==================================================
Use position_hint from input:
  center         → layout_hint: "center"       (place at origin 0,0,0)
  surrounding    → layout_hint: "surrounding"  (ring around center)
  orbiting       → layout_hint: "orbiting"     (orbital ring)
  above_center   → layout_hint: "above"
  below_center   → layout_hint: "below"
  corner         → layout_hint: "corner"
  sequential     → layout_hint: "none"         (engine handles order)

==================================================
COLOR MAPPING
==================================================
Use color_hex from input. Map to closest color_hint:
  Reds/oranges/yellows  → "gradient_hot"
  Blues/cyans/purples   → "gradient_cool"
  Single bright accent  → "accent_bright"
  Neutral grays/whites  → "neutral"
  Paired components     → "contrast_pair"
  Greens (biology)      → "accent_bright"
  Warning/danger        → "warning_red"

Also pass color_hex directly in the component as "color" field.

==================================================
EXPLANATIONS — MANDATORY
==================================================
  intro:        Use concept_description from input verbatim or lightly expanded
  layout_logic: Use spatial_logic from input verbatim or lightly expanded
  Both MUST be non-empty strings of at least 1 sentence each.

==================================================
OUTPUT SCHEMA — RETURN EXACTLY THIS
==================================================
{
  "pattern": "",
  "explanations": {
    "intro": "",
    "layout_logic": ""
  },
  "geometric_components": [
    {
      "id": "",
      "semantic_type": "structure|organ|layer|node|resource|force|particle",
      "label": "",
      "shape": "",
      "resolved_shape": "",
      "color": "#RRGGBB",
      "color_hint": "neutral|gradient_hot|gradient_cool|accent_bright|contrast_pair|warning_red",
      "role": "central|peripheral|node|source|sink|anchor|cap|layer",
      "count": 1,
      "size_hint": "extra_large|large|medium|small|tiny",
      "scale_override": [1.0, 1.0, 1.0],
      "vertical_relation": "none|above|below|adjacent|inside|container",
      "importance": "high|medium|low",
      "layout_hint": "none|center|surrounding|orbiting|above|below|corner"
    }
  ],
  "semantic_relations": [
    {
      "from_id": "",
      "to_id": "",
      "relation_type": "contains|flows_to|attached_to|supports|stacked_above|orbits",
      "connector": "arrow|line|dashed_line",
      "label": "",
      "strength": "weak|medium|strong"
    }
  ],
  "groups": [],
  "contextual_annotations": [],
  "structure": {
    "arrangement": "radial|corner_based|linear|layered|free",
    "levels": []
  },
  "constraints": {
    "symmetry": "none|bilateral|radial|four_fold",
    "density": "low|medium|high"
  }
}

==================================================
STRICT RULES
==================================================
- Return ONLY valid JSON — no prose, no markdown, no backticks
- resolved_shape MUST equal shape, NEVER empty
- scale_override MUST be set for every component
- color MUST be set to the color_hex from input
- explanations.intro and explanations.layout_logic MUST be non-empty
- Do NOT invent components not in the input
- Do NOT reduce multiple input entities into one component
"""

def generate_stage_2_user_prompt(stage_1_json: str) -> str:
    return (
        f"Spatial Artist Brief (input):\n{stage_1_json}\n\n"
        f"Compile into 3D blueprint. Return ONLY JSON."
    )


# ==============================================================================
# PROVIDER-SPECIFIC SUFFIXES
# ==============================================================================
GEMINI_STAGE_1_SUFFIX = """
GEMINI ADDITIONAL RULES:
- color_hex MUST be set for every entity — use scientifically accurate colors
- For radial patterns: innermost entity size_class = dominant, outer = progressively smaller
- For hierarchical: base = dominant, apex = small
- relations MUST be non-empty for layered or hierarchical concepts
- shape_description MUST be one of: sphere, box, cone, cylinder, torus, hemisphere, icosphere"""

GEMINI_STAGE_2_SUFFIX = """
GEMINI ADDITIONAL RULES:
- resolved_shape MUST equal shape, never empty
- scale_override: dominant=[4.0,4.0,4.0], large=[2.5,2.5,2.5], medium=[1.5,1.5,1.5], small=[0.8,0.8,0.8], tiny=[0.3,0.3,0.3]
- color field MUST be set from input color_hex
- pyramid body = cone [3.0,4.0,3.0], pyramid base = box [4.5,0.4,4.5]
- explanations.intro and explanations.layout_logic MUST be non-empty"""

OLLAMA_STAGE_1_SUFFIX = """
OLLAMA ADDITIONAL RULES:
- color_hex MUST be set for every entity using scientifically accurate colors
- Every identity_core entity MUST appear in output
- For radial: innermost = dominant size_class, outer layers get smaller
- For hierarchical: base = dominant, apex = small
- relations MUST be non-empty for layered/hierarchical/concentric concepts
- shape_description must be exact: sphere, box, cone, cylinder, torus, hemisphere, or icosphere"""

OLLAMA_STAGE_2_SUFFIX = """
OLLAMA ADDITIONAL RULES:
- Every entity from input MUST appear as a geometric_component
- resolved_shape MUST equal shape — NEVER leave empty
- scale_override MUST be set: dominant=[4.0,4.0,4.0], large=[2.5,2.5,2.5], medium=[1.5,1.5,1.5], small=[0.8,0.8,0.8], tiny=[0.3,0.3,0.3]
- color MUST be set from input color_hex
- For radial patterns: innermost component gets largest scale, outermost gets smallest
- Pyramid: cone body [3.0,4.0,3.0] + flat box base [4.5,0.4,4.5]
- explanations.intro and explanations.layout_logic MUST be non-empty strings"""