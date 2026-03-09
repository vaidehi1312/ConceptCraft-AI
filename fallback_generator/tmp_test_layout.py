import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from schema import Blueprint, ComponentInput, RelationInput, ExplanationsModel, ConstraintsModel, StructureDetails
from layouts import TubularMorphologyLayout

b = Blueprint(
    pattern="tubular_morphology",
    explanations=ExplanationsModel(),
    geometric_components=[
        ComponentInput(id="bowman_capsule", shape="sphere"),
        ComponentInput(id="glomerulus", shape="sphere"),
        ComponentInput(id="proximal_tubule", shape="cylinder"),
        ComponentInput(id="loop_of_henle", shape="cylinder"),
        ComponentInput(id="distal_tubule", shape="cylinder")
    ],
    semantic_relations=[
        RelationInput(from_id="bowman_capsule", to_id="glomerulus", relation_type="contains"),
        RelationInput(from_id="bowman_capsule", to_id="proximal_tubule", relation_type="flows_to")
    ],
    groups=[],
    contextual_annotations=[],
    structure=StructureDetails(),
    constraints=ConstraintsModel()
)

layout = TubularMorphologyLayout()
out = layout.process(b)

for c in out:
    print(f"ID: {c.id}, Shape: {c.shape}, Variant: {c.metadata.get('variant')}, Pos: ({c.position.x}, {c.position.y}, {c.position.z})")
    
