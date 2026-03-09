# ConceptCraftAI Fallback Module

This module dynamically generates structural blueprints from raw concepts using an LLM, and calculates Three.js-ready geometric coordinates.

## How to use Real LLMs

The `BlueprintGenerator` supports both OpenAI and Google Gemini out of the box. By default, if no keys are found, it uses a mocked fallback for testing the pipeline.

To use the real models, you must provide your API key via an environment variable.

### Option 1: Using OpenAI (GPT-4o)
1. Install the OpenAI package:
   ```bash
   pip install openai
   ```
2. Set your environment variable:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

### Option 2: Using Google Gemini
1. Install the Gemini package:
   ```bash
   pip install google-generativeai
   ```
2. Set your environment variable:
   ```bash
   export GOOGLE_API_KEY="your-api-key-here"
   ```

### Running the Example
Once your key is exported in the terminal, you can run the pipeline. It will automatically detect the key and use the real model instead of the mock:

```bash
python3 examples/full_pipeline.py
```
