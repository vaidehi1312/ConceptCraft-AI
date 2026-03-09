# ConceptCraftAI: Semantic 3D Visualization Pipeline

ConceptCraftAI is an architectural system for transforming abstract conceptual data into semantically structured 3D visualizations. The system utilizes a multi-stage deterministic pipeline to translate linguistic concepts into spatial coordinates, ensuring geometric integrity and logical consistency.

## Technical Architecture: The 10-Stage Pipeline

The pipeline follows a data-driven sequence where each stage operates under a strict data contract to maintain system state and reliability.

1.  **Semantic Decomposition:** Transformation of raw concepts into essential entities and relational metadata.
2.  **Semantic Gate:** Validation and automated repair of initial semantic proposals.
3.  **Blueprint Compilation:** Translation of semantic structures into geometric blueprints including shapes, roles, and importance metrics.
4.  **Blueprint Gate:** Normalization of spatial relations and enforcement of geometric attribute requirements.
5.  **Visual Gate:** Topological scoring and verification of blueprint viability.
6.  **Morphology Resolution:** Classification of the concept into specific morphological families for specialized rendering logic.
7.  **Relational Geometry Pass:** Calculation of visual properties for semantic connections and scale ratios.
8.  **Layout Engine Selector:** Selection of mathematical algorithms (Radial, Hierarchical, Network, etc.) based on blueprint logic.
9.  **Coordinate Generation:** Execution of spatial layouts and post-process passes for containment and stacking logic.
10. **Final Output Formatting:** Serialization of optimized geometric data for the Three.js visualization engine.

## System Features

- **Morphological Specialization:** Dedicated processing logic for biological structures, architectural assemblies, and process sequences.
- **Data Contract Enforcement:** Centralized schema definition via `pipeline_contract.py` to prevent structural regressions.
- **Spatial Logic Resolution:** Deterministic handling of hierarchical containment and vertical structural stacking.
- **Weighted Geometric Scaling:** Calculation of proportions based on semantically assigned importance and size hints.

## Installation and Execution

### Environment Setup

1. Create a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Pipeline

To execute the pipeline via the command-line interface:

```bash
PYTHONPATH=src python3 src/main.py
```

Concepts provided to the interface are processed through all ten stages, and the resulting geometric state is exported to `public/output.json` for consumption by the visualization interface.

## Project Structure

- `src/main.py`: Primary pipeline orchestrator and entry point.
- `src/pipeline_contract.py`: Authority for valid schema definitions and contract validation.
- `src/engine.py`: Coordination of layout engines and spatial processing passes.
- `src/validators/`: Integrity enforcement gates for each stage transition.
- `src/documentation/architecture_flow.md`: Technical documentation of internal pipeline logic and data flow.
