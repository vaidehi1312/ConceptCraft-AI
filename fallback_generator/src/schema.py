"""
Schema Module
-------------
This file sets the rigid Data Contracts for the entire ConceptCraftAI pipeline.
Using standard Python `dataclasses`, it defines exactly what the JSON coming 
FROM the LLM should look like (Blueprint, ComponentInput, ExplanationsModel,
RelationInput, GroupInput, AnnotationInput), and exactly what the JSON going TO 
the 3D Web Renderer should look like.
"""
"""
Domain Schema Module
--------------------
RESPONSIBILITY: 
Defines the core Dataclasses and Typing for the entire pipeline. 
Ensures consistent object structures for Blueprints and Output coordinates.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class ComponentInput:
    id: str
    semantic_type: str = "actor" # actor | institution | resource | organ | process_stage | force | chemical_unit | boundary | flow_node
    label: str = ""
    shape: str = "box" # box | sphere | cylinder | cone | hemisphere | torus
    role: str = "node" # central | peripheral | node | source | sink | stage | anchor
    count: int = 1
    size_hint: str = "medium" # small | medium | large
    vertical_relation: str = "none" # above | below | none | same_level
    importance: str = "medium" # high | medium | low
    resolved_shape: Optional[str] = None
    scale_hint: Any = None
    color_hint: Optional[str] = None
    layout_hint: Optional[str] = None

@dataclass
class RelationInput:
    from_id: str
    to_id: str
    relation_type: str = "flows_to" # flows_to | influences | depends_on | produces | transforms_into | regulates | supports | checks | exchanges_with | attached_to | contains
    connector: str = "arrow" # arrow | bidirectional_arrow | line | curved_arrow | dashed_line
    label: str = ""
    strength: str = "medium" # weak | medium | strong

@dataclass
class GroupInput:
    id: str
    layout: str = "central_peripheral" # central_peripheral | hierarchical | radial | network | field
    members: List[str] = field(default_factory=list)

@dataclass
class AnnotationInput:
    target: str
    text: str

@dataclass
class StructureDetails:
    arrangement: str = "free"
    levels: List[str] = field(default_factory=list)

@dataclass
class ExplanationsModel:
    intro: str = ""
    layout_logic: str = ""

@dataclass
class ConstraintsModel:
    symmetry: str = "none" # none | bilateral | radial | four_fold
    density: str = "medium" # low | medium | high

@dataclass
class Blueprint:
    pattern: str # central_peripheral | hierarchical | radial | network | field | hybrid
    explanations: ExplanationsModel
    geometric_components: List[ComponentInput]
    semantic_relations: List[RelationInput] = field(default_factory=list)
    groups: List[GroupInput] = field(default_factory=list)
    contextual_annotations: List[AnnotationInput] = field(default_factory=list)
    structure: StructureDetails = field(default_factory=StructureDetails)
    constraints: ConstraintsModel = field(default_factory=ConstraintsModel)
    morphology_family: Optional[str] = None
    morphology_params: Optional[Dict[str, Any]] = None
    connectors: Optional[List[Dict[str, Any]]] = field(default_factory=list)

# --- Output Schemas for Renderer ---

@dataclass
class Position:
    x: float
    y: float
    z: float

@dataclass
class Scale:
    x: float
    y: float
    z: float

@dataclass
class OutputComponent:
    id: str
    original_id: str
    semantic_type: str
    label: str
    shape: str
    position: Position
    scale: Scale
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LayoutResult:
    scenario: str
    pattern: str
    intro: str
    layout_logic: str
    geometric_components: List[OutputComponent]
    semantic_relations: List[Dict[str, Any]] = field(default_factory=list)
    groups: List[Dict[str, Any]] = field(default_factory=list)
    contextual_annotations: List[Dict[str, Any]] = field(default_factory=list)
    tube_path: Optional[List[List[float]]] = None
