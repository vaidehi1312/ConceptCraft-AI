"""
LLM Generator Module
--------------------
RESPONSIBILITY:
Handles all interactions with Large Language Models (Gemini via Google API or Ollama locally).
Responsible for generating Stage 1 (Semantic Decomposition) and Stage 2 (Blueprint Compilation).

STAGES HANDLED:
- Stage 1: Semantic Decomposition
- Stage 3: Blueprint Compilation
"""
import os
import json
import requests
import google.generativeai as genai
from prompts import (
    STAGE_1_PROMPT, generate_stage_1_user_prompt,
    STAGE_2_PROMPT, generate_stage_2_user_prompt,
    GEMINI_STAGE_1_SUFFIX, OLLAMA_STAGE_1_SUFFIX,
    GEMINI_STAGE_2_SUFFIX, OLLAMA_STAGE_2_SUFFIX
)

class BlueprintGenerator:
    """Answers the question: What geometry represents this Concept?"""
    
    def __init__(self, provider: str = "auto"):
        self.provider = provider
        if provider == "auto":
            if os.getenv("GOOGLE_API_KEY"):
                self.provider = "gemini"
            elif os.getenv("OPENAI_API_KEY"):
                self.provider = "openai"
            else:
                print("[BlueprintGenerator] No API keys found, defaulting to Ollama local instance.")
                self.provider = "ollama"
                
    def generate_stage_1(self, concept: str) -> str:
        """Generates the Semantic Decomposition."""
        max_retries = 2
        current_provider = self.provider
        
        for attempt in range(max_retries + 1):
            try:
                if current_provider == "openai":
                    return self._call_openai(1, concept)
                elif current_provider == "gemini":
                    return self._call_gemini(1, concept)
                elif current_provider == "ollama":
                    return self._call_ollama(1, concept)
                elif current_provider == "mock":
                    return self._call_mock_stage_1(concept)
                else:
                    raise ValueError(f"Unknown LLM provider: {current_provider}")
            except Exception as e:
                is_quota_error = ("429" in str(e) or "quota" in str(e).lower())
                if current_provider in ["gemini", "openai"] and is_quota_error:
                    print(f"[!] {current_provider.capitalize()} API rate limit hit. Switching to Ollama for Stage 1...")
                    current_provider = "ollama"
                    continue
                if attempt == max_retries:
                    raise e
        return ""

    def generate_stage_2(self, semantic_data_str: str) -> str:
        """Generates the full Blueprint from Semantic JSON."""
        max_retries = 3
        current_provider = self.provider
        
        for attempt in range(max_retries + 1):
            try:
                if current_provider == "openai":
                    res = self._call_openai(2, semantic_data_str)
                elif current_provider == "gemini":
                    res = self._call_gemini(2, semantic_data_str)
                elif current_provider == "ollama":
                    res = self._call_ollama(2, semantic_data_str)
                elif current_provider == "mock":
                    res = self._call_mock_stage_2(semantic_data_str)
                else:
                    raise ValueError(f"Unknown LLM provider: {current_provider}")
                
                # JSON Format Check & Retry
                clean_res = res
                if "```" in res:
                    import re
                    match = re.search(r'```(?:json)?\s*(.*?)\s*```', res, re.DOTALL)
                    if match: clean_res = match.group(1).strip()
                
                try:
                    import json
                    blueprint_data = json.loads(clean_res)
                    res = clean_res # Normalize back to stripped JSON for validators
                except Exception as e:
                    print(f"      [!] Stage 2 LLM returned malformed JSON syntax: {e}. Retrying ({attempt+1}/{max_retries})...")
                    if attempt < max_retries:
                        continue
                        
                # Ollama Safety Check: Prevent Semantic Collapse
                if (current_provider == "ollama") and semantic_data_str:
                    try:
                        sem_data = json.loads(semantic_data_str)
                        
                        identity_cores = [e["id"] for e in sem_data.get("entities", []) if e.get("priority") == "identity_core"]
                        geo_comps = [c["id"] for c in blueprint_data.get("geometric_components", [])]
                        
                        # Case insensitive check
                        core_ids = {ic.lower() for ic in identity_cores}
                        geo_ids = {gc.lower() for gc in geo_comps}
                        
                        missing = [ic for ic in identity_cores if ic.lower() not in geo_ids]
                        
                        if len(geo_comps) < len(identity_cores) or missing:
                            print(f"      [!] {current_provider.capitalize()} Stage 2 semantic collapse detected (Missing: {missing}). Retrying ({attempt+1}/{max_retries})...")
                            if attempt < max_retries:
                                continue
                    except Exception as e:
                        pass
                
                return res
                
            except Exception as e:
                is_quota_error = ("429" in str(e) or "quota" in str(e).lower())
                if current_provider in ["gemini", "openai"] and is_quota_error:
                    print(f"[!] {current_provider.capitalize()} API rate limit hit. Switching to Ollama for Stage 2...")
                    current_provider = "ollama"
                    # Reset attempt count for the new provider
                    # attempt = 0 # Not allowed in for loop, but it's okay, we have max_retries
                    continue
                if attempt == max_retries:
                    raise e
        return ""
            
    def _call_openai(self, stage: int, content: str) -> str:
        sys_prompt = STAGE_1_PROMPT if stage == 1 else STAGE_2_PROMPT
        user_prompt = generate_stage_1_user_prompt(content) if stage == 1 else generate_stage_2_user_prompt(content)
        try:
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                response_format={ "type": "json_object" }
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"OpenAI LLM interaction failed: {e}")
            
    def _call_gemini(self, stage: int, content: str) -> str:
        sys_prompt = STAGE_1_PROMPT if stage == 1 else STAGE_2_PROMPT
        # Append Gemini-specific suppression suffix
        sys_prompt += GEMINI_STAGE_1_SUFFIX if stage == 1 else GEMINI_STAGE_2_SUFFIX
        
        user_prompt = generate_stage_1_user_prompt(content) if stage == 1 else generate_stage_2_user_prompt(content)
        try:
            from google import genai
            from google.genai import types
            
            api_key = os.environ.get("GOOGLE_API_KEY")
            client = genai.Client(api_key=api_key)
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=sys_prompt,
                    response_mime_type="application/json"
                )
            )
            return response.text
        except Exception as e:
            raise RuntimeError(f"Google GenAI LLM interaction failed: {e}")

    def _call_ollama(self, stage: int, content: str) -> str:
        sys_prompt = STAGE_1_PROMPT if stage == 1 else STAGE_2_PROMPT
        # Append Ollama-specific preservation suffix
        sys_prompt += OLLAMA_STAGE_1_SUFFIX if stage == 1 else OLLAMA_STAGE_2_SUFFIX
        
        user_prompt = generate_stage_1_user_prompt(content) if stage == 1 else generate_stage_2_user_prompt(content)
        try:
            import requests
            response = requests.post("http://localhost:11434/api/chat", json={
                "model": "llama3.2",
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "format": "json",
                "stream": False
            })
            response.raise_for_status()
            return response.json()["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Ollama local LLM interaction failed. Make sure Ollama is running ('ollama run llama3.2'). Error: {e}")

    def _call_mock_stage_1(self, concept: str) -> str:
        print(f"[BlueprintGenerator] Using Mock LLM Stage 1 for concept: '{concept}'")
        c = concept.lower()
        if "dna" in c:
            return '''
{
  "category": "biological_structure",
  "dominant_pattern": "radial",
  "hybrid_needed": false,
  "entities": [
    {"id": "nucleotide_group_A", "count": 20, "priority": "identity_core"},
    {"id": "nucleotide_group_B", "count": 20, "priority": "identity_core"}
  ],
  "relations": [
    {"from_id": "nucleotide_group_A", "to_id": "nucleotide_group_B", "relation_type": "influences"}
  ]
}
'''
        elif "ecosystem" in c or "network" in c:
            return '''
{
  "category": "abstract_system",
  "dominant_pattern": "network",
  "hybrid_needed": false,
  "entities": [
    {"id": "producer", "count": 5, "priority": "identity_core"},
    {"id": "prey", "count": 4, "priority": "support_core"},
    {"id": "predator", "count": 2, "priority": "context_optional"}
  ],
  "relations": [
    {"from_id": "producer", "to_id": "prey", "relation_type": "flows_to"},
    {"from_id": "prey", "to_id": "predator", "relation_type": "flows_to"}
  ]
}
'''
        else:
            return '''
{
  "category": "process",
  "dominant_pattern": "hybrid",
  "hybrid_needed": true,
  "entities": [
    {"id": "core_engine", "count": 1, "priority": "identity_core"},
    {"id": "input_stream", "count": 2, "priority": "support_core"},
    {"id": "output_valve", "count": 1, "priority": "support_core"},
    {"id": "regulatory_node", "count": 3, "priority": "context_optional"}
  ],
  "relations": [
    {"from_id": "input_stream", "to_id": "core_engine", "relation_type": "flows_to"},
    {"from_id": "core_engine", "to_id": "output_valve", "relation_type": "produces"},
    {"from_id": "regulatory_node", "to_id": "core_engine", "relation_type": "regulates"}
  ]
}
'''

    def _call_mock_stage_2(self, semantic_json: str) -> str:
        print(f"[BlueprintGenerator] Using Mock LLM Stage 2")
        if "dna" in semantic_json.lower():
            return '''
{
  "pattern": "radial",
  "explanations": {"intro": "DNA structure", "layout_logic": "Spiral radial layout to demonstrate double helix."},
  "geometric_components": [
    {"id": "nucleotide_group_A", "semantic_type": "chemical_unit", "label": "Adenine-Thymine", "shape": "sphere", "role": "node", "count": 20, "size_hint": "small", "vertical_relation": "none", "importance": "high"},
    {"id": "nucleotide_group_B", "semantic_type": "chemical_unit", "label": "Guanine-Cytosine", "shape": "sphere", "role": "node", "count": 20, "size_hint": "small", "vertical_relation": "none", "importance": "high"}
  ],
  "semantic_relations": [
    {"from_id": "nucleotide_group_A", "to_id": "nucleotide_group_B", "relation_type": "influences", "connector": "line", "label": "Hydrogen bond", "strength": "strong"}
  ],
  "groups": [],
  "contextual_annotations": [],
  "structure": {},
  "constraints": { "symmetry": "none", "density": "high" }
}
'''
        elif "ecosystem" in semantic_json.lower() or "network" in semantic_json.lower() or "producer" in semantic_json.lower():
            return '''
{
  "pattern": "network",
  "explanations": {"intro": "Ecosystem network", "layout_logic": "Clustered network of energy transfer."},
  "geometric_components": [
    {"id": "producer", "semantic_type": "resource", "label": "Plants", "shape": "box", "role": "source", "count": 5, "size_hint": "medium", "vertical_relation": "none", "importance": "high"},
    {"id": "prey", "semantic_type": "actor", "label": "Herbivores", "shape": "cylinder", "role": "node", "count": 4, "size_hint": "small", "vertical_relation": "none", "importance": "medium"},
    {"id": "predator", "semantic_type": "actor", "label": "Carnivores", "shape": "cone", "role": "sink", "count": 2, "size_hint": "large", "vertical_relation": "none", "importance": "low"}
  ],
  "semantic_relations": [
    {"from_id": "producer", "to_id": "prey", "relation_type": "flows_to", "connector": "arrow", "label": "Eaten by", "strength": "strong"},
    {"from_id": "prey", "to_id": "predator", "relation_type": "flows_to", "connector": "arrow", "label": "Eaten by", "strength": "medium"}
  ],
  "groups": [],
  "contextual_annotations": [],
  "structure": {},
  "constraints": { "symmetry": "none", "density": "medium" }
}
'''
        else:
            return '''
{
  "pattern": "hybrid",
  "explanations": {"intro": "A conceptual system.", "layout_logic": "Hybrid pattern."},
  "geometric_components": [
    {"id": "core_engine", "semantic_type": "structure", "label": "Core Engine", "shape": "box", "role": "central", "count": 1, "size_hint": "large", "vertical_relation": "none", "importance": "high"},
    {"id": "input_stream", "semantic_type": "resource", "label": "Input Stream", "shape": "cylinder", "role": "source", "count": 2, "size_hint": "medium", "vertical_relation": "above", "importance": "medium"},
    {"id": "output_valve", "semantic_type": "entrance", "label": "Output Valve", "shape": "cone", "role": "sink", "count": 1, "size_hint": "small", "vertical_relation": "below", "importance": "low"},
    {"id": "regulatory_node", "semantic_type": "institution", "label": "Regulator", "shape": "sphere", "role": "node", "count": 3, "size_hint": "medium", "vertical_relation": "same_level", "importance": "high"}
  ],
  "semantic_relations": [
    {"from_id": "input_stream", "to_id": "core_engine", "relation_type": "flows_to", "connector": "arrow", "label": "Feeds raw data", "strength": "strong"},
    {"from_id": "core_engine", "to_id": "output_valve", "relation_type": "produces", "connector": "line", "label": "Outputs processed data", "strength": "medium"},
    {"from_id": "regulatory_node", "to_id": "core_engine", "relation_type": "regulates", "connector": "dashed_line", "label": "Monitors output rate", "strength": "weak"}
  ],
  "groups": [
    {"id": "processing_group", "layout": "central_peripheral", "members": ["core_engine", "input_stream", "output_valve"]},
    {"id": "governance_group", "layout": "radial", "members": ["regulatory_node"]}
  ],
  "contextual_annotations": [],
  "structure": {"arrangement": "free", "levels": []},
  "constraints": {"symmetry": "bilateral", "density": "medium"}
}
'''
