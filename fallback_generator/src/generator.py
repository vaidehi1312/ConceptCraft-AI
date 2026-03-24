"""
LLM Generator Module
--------------------
RESPONSIBILITY:
Handles all interactions with LLMs.
Priority order:
  1. Kaggle (ngrok public URL) — llama3 8B on GPU
  2. Gemini API — if GOOGLE_API_KEY set and quota available
  3. Ollama — local fallback

STAGES HANDLED:
- Stage 1: Semantic Decomposition
- Stage 2: Blueprint Compilation
"""
import os
import json
import re
import requests
import google.generativeai as genai
from prompts import (
    STAGE_1_PROMPT, generate_stage_1_user_prompt,
    STAGE_2_PROMPT, generate_stage_2_user_prompt,
    GEMINI_STAGE_1_SUFFIX, OLLAMA_STAGE_1_SUFFIX,
    GEMINI_STAGE_2_SUFFIX, OLLAMA_STAGE_2_SUFFIX
)

# ── Paste your ngrok URL here when Kaggle notebook is running ──────────────
KAGGLE_LLM_URL = "https://impressional-kristy-nonalined.ngrok-free.dev"
KAGGLE_LLM_URL = os.getenv("KAGGLE_LLM_URL", "")
# ──────────────────────────────────────────────────────────────────────────


class BlueprintGenerator:
    """Answers the question: What geometry represents this Concept?"""

    def __init__(self, provider: str = "auto"):
        self.provider = provider
        if provider == "auto":
            if KAGGLE_LLM_URL:
                self.provider = "kaggle"
                print(f"[BlueprintGenerator] Kaggle LLM URL found: {KAGGLE_LLM_URL}")
            elif os.getenv("GOOGLE_API_KEY"):
                self.provider = "gemini"
                print("[BlueprintGenerator] Gemini API key found.")
            else:
                print("[BlueprintGenerator] No API keys found, defaulting to Ollama.")
                self.provider = "ollama"

    def _call_provider(self, stage: int, content: str, provider: str) -> str:
        if provider == "kaggle":
            return self._call_kaggle(stage, content)
        elif provider == "gemini":
            return self._call_gemini(stage, content)
        elif provider == "ollama":
            return self._call_ollama(stage, content)
        elif provider == "mock":
            return self._call_mock_stage_1(content) if stage == 1 else self._call_mock_stage_2(content)
        raise ValueError(f"Unknown provider: {provider}")

    def generate_stage_1(self, concept: str) -> str:
        """Generates the Semantic Decomposition."""
        return self._run_with_fallback(1, concept)

    def generate_stage_2(self, semantic_data_str: str) -> str:
        """Generates the full Blueprint from Semantic JSON."""
        res = self._run_with_fallback(2, semantic_data_str)

        # Strip markdown fences (safety net for Ollama)
        clean_res = res
        if "```" in res:
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', res, re.DOTALL)
            if match:
                clean_res = match.group(1).strip()

        try:
            blueprint_data = json.loads(clean_res)
            components = blueprint_data.get("geometric_components", [])
            relations = blueprint_data.get("semantic_relations", [])

            if components:
                components[0]["importance"] = "high"
            if len(components) > 2:
                components[-1]["importance"] = "low"

            comp_count = len(components)
            max_rel = int(comp_count * 0.6)
            if len(relations) > max_rel:
                blueprint_data["semantic_relations"] = relations[:max_rel]

            has_core = any(
                kw in (c.get("id", "") + c.get("label", "")).lower()
                for c in components
                for kw in ["core", "center", "base", "platform", "foundation"]
            )
            if not has_core and components:
                components[0]["role"] = "central"

            return json.dumps(blueprint_data)
        except Exception as parse_err:
            print(f"[!] Stage 2 JSON parse error: {parse_err}")
            return clean_res

    def _run_with_fallback(self, stage: int, content: str) -> str:
        """Try providers in order: kaggle → gemini → ollama"""
        fallback_chain = []

        if self.provider == "kaggle":
            fallback_chain = ["kaggle", "gemini", "ollama"]
        elif self.provider == "gemini":
            fallback_chain = ["gemini", "ollama"]
        else:
            fallback_chain = ["ollama"]

        last_error = None
        for provider in fallback_chain:
            try:
                print(f"[generator] Trying {provider} for stage {stage}...")
                result = self._call_provider(stage, content, provider)
                print(f"[generator] {provider} succeeded for stage {stage}.")
                return result
            except Exception as e:
                print(f"[generator] {provider} failed: {e}")
                last_error = e
                continue

        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    def _call_kaggle(self, stage: int, content: str) -> str:
        """Call the Kaggle-hosted llama3 8B via ngrok public URL."""
        sys_prompt = STAGE_1_PROMPT if stage == 1 else STAGE_2_PROMPT
        sys_prompt += OLLAMA_STAGE_1_SUFFIX if stage == 1 else OLLAMA_STAGE_2_SUFFIX
        user_prompt = generate_stage_1_user_prompt(content) if stage == 1 else generate_stage_2_user_prompt(content)

        url = KAGGLE_LLM_URL.rstrip("/") + "/generate"
        response = requests.post(url, json={
    "system_prompt": sys_prompt,
    "user_prompt": user_prompt,
    "max_tokens": 1024 if stage == 2 else 512  # ← limit stage 2 output size
}, timeout=300)

        response.raise_for_status()
        result = response.json()

        if "error" in result:
            raise RuntimeError(f"Kaggle LLM error: {result['error']}")

        return result["response"]

    def _call_gemini(self, stage: int, content: str) -> str:
        sys_prompt = STAGE_1_PROMPT if stage == 1 else STAGE_2_PROMPT
        sys_prompt += GEMINI_STAGE_1_SUFFIX if stage == 1 else GEMINI_STAGE_2_SUFFIX
        user_prompt = generate_stage_1_user_prompt(content) if stage == 1 else generate_stage_2_user_prompt(content)
        try:
            api_key = os.environ.get("GOOGLE_API_KEY")
            genai.configure(api_key=api_key)
            generation_config = genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash-lite",
                system_instruction=sys_prompt,
                generation_config=generation_config
            )
            response = model.generate_content(user_prompt)
            return response.text
        except Exception as e:
            print(f"GEMINI ERROR: {e}")
            raise RuntimeError(f"Gemini failed: {e}")

    def _call_ollama(self, stage: int, content: str) -> str:
        sys_prompt = STAGE_1_PROMPT if stage == 1 else STAGE_2_PROMPT
        sys_prompt += OLLAMA_STAGE_1_SUFFIX if stage == 1 else OLLAMA_STAGE_2_SUFFIX
        user_prompt = generate_stage_1_user_prompt(content) if stage == 1 else generate_stage_2_user_prompt(content)
        try:
            response = requests.post("http://localhost:11434/api/chat", json={
                "model": "llama3.2",
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "format": "json",
                "stream": False
            }, timeout=180)
            response.raise_for_status()
            return response.json()["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Ollama failed: {e}")

    def _call_mock_stage_1(self, concept: str) -> str:
        print(f"[BlueprintGenerator] Using Mock LLM Stage 1 for concept: '{concept}'")
        c = concept.lower()
        if "dna" in c:
            return json.dumps({
                "category": "biological_structure",
                "dominant_pattern": "radial",
                "hybrid_needed": False,
                "entities": [
                    {"id": "nucleotide_group_A", "count": 20, "priority": "identity_core"},
                    {"id": "nucleotide_group_B", "count": 20, "priority": "identity_core"}
                ],
                "relations": [
                    {"from_id": "nucleotide_group_A", "to_id": "nucleotide_group_B", "relation_type": "influences"}
                ]
            })
        elif "ecosystem" in c or "network" in c:
            return json.dumps({
                "category": "abstract_system",
                "dominant_pattern": "network",
                "hybrid_needed": False,
                "entities": [
                    {"id": "producer", "count": 5, "priority": "identity_core"},
                    {"id": "prey", "count": 4, "priority": "support_core"},
                    {"id": "predator", "count": 2, "priority": "context_optional"}
                ],
                "relations": [
                    {"from_id": "producer", "to_id": "prey", "relation_type": "flows_to"},
                    {"from_id": "prey", "to_id": "predator", "relation_type": "flows_to"}
                ]
            })
        else:
            return json.dumps({
                "category": "process",
                "dominant_pattern": "hybrid",
                "hybrid_needed": True,
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
            })

    def _call_mock_stage_2(self, semantic_json: str) -> str:
        print(f"[BlueprintGenerator] Using Mock LLM Stage 2")
        return json.dumps({
            "pattern": "radial",
            "explanations": {"intro": "Mock visualization.", "layout_logic": "Mock layout."},
            "geometric_components": [
                {"id": "core", "semantic_type": "structure", "label": "Core", "shape": "sphere",
                 "resolved_shape": "sphere", "role": "central", "count": 1, "size_hint": "large",
                 "vertical_relation": "none", "importance": "high", "color_hint": "neutral", "layout_hint": "center"}
            ],
            "semantic_relations": [],
            "groups": [],
            "contextual_annotations": [],
            "structure": {"arrangement": "radial", "levels": []},
            "constraints": {"symmetry": "none", "density": "medium"}
        })