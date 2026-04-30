"""
Ollama client for local LLM classification.
Uses the official `ollama` Python library (pip install ollama).
"""

import json
import ollama

# Models to use per stage — change these based on what you have pulled
STAGE1_MODEL = "qwen3.6:latest"  # broad category classification
STAGE2_MODEL = "qwen3.6:latest"  # specific question classification


def is_running():
    """Check if Ollama server is up."""
    try:
        ollama.list()
        return True
    except Exception:
        return False


def list_models():
    """Return list of pulled model names."""
    response = ollama.list()
    return [m.model for m in response.models]


def generate(prompt, model, system=None, max_tokens=500, retries=3):
    """
    Single generation call to Ollama.
    Returns the response text or None on failure.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(retries):
        try:
            response = ollama.chat(
                model=model,
                messages=messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": 0.1,
                    "top_p": 0.9,
                },
            )
            return response.message.content.strip()

        except ollama.ResponseError as e:
            print(f"  [ollama] response error on attempt {attempt+1}: {e}")
        except Exception as e:
            print(f"  [ollama] error on attempt {attempt+1}: {e}")

    return None


def generate_json(prompt, model, system=None, max_tokens=500):
    """
    Like generate() but parses and returns JSON.
    Uses Ollama's native JSON format mode, with fallback extraction.
    """
    json_prompt = (
        prompt + "\n\nIMPORTANT: Return only a valid JSON object. "
        "No explanation, no markdown, no code fences. Just the JSON."
    )
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": json_prompt})

    for attempt in range(3):
        try:
            response = ollama.chat(
                model=model,
                messages=messages,
                format="json",
                options={
                    # "num_predict": max_tokens,
                    "temperature": 0.1,
                    "top_p": 0.9,
                },
            )
            text = response.message.content.strip()
            print(f"  [ollama] raw response: {text[:200]}")

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

            # Fallback: extract JSON substring if model added preamble
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass

        except ollama.ResponseError as e:
            print(f"  [ollama] response error on attempt {attempt+1}: {e}")
        except Exception as e:
            print(f"  [ollama] error on attempt {attempt+1}: {e}")

        print(f"  [ollama] attempt {attempt+1}: could not parse JSON from response")

    return None
