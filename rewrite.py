import requests
import json
import sys

class RewriteEngine:
    def __init__(self, config, session=None):
        self.config = config
        self.session = session

    def process(self, text, style="cursor_prompt"):
        """Rewrites the transcribed text based on style and configured engine."""
        if not text or not text.strip():
            return ""

        prompts = {
            "cursor_prompt": self.config.get(
                "prompt_ai_prompt",
                "You are an expert technical director. Translate the following spoken Danish/English description "
                "into a highly precise, structured, and action-oriented prompt for an AI coding agent (like Cursor or Antigravity). "
                "Focus on strict technical requirements, libraries, and clean architecture. "
                "Output ONLY the final prompt. No conversational filler or markdown code blocks."
            ),
            "tech_doc": (
                "Convert this spoken description into a clean, structured JSDoc, PyDoc, or Markdown system documentation "
                "in professional English."
            ),
            "clean_transcription": self.config.get(
                "prompt_ai",
                "You are a professional editor. Clean up the following spoken transcription. "
                "Fix grammatical errors, remove stutters, filler words, and clean up sentence structure. "
                "Keep the language of the original text (Danish or English). "
                "Output ONLY the cleaned text."
            )
        }
        
        system_prompt = prompts.get(style, prompts["cursor_prompt"])
        
        # Decide whether to rewrite locally or in the cloud
        if self.config.get("rewrite_locally", False):
            return self._ollama_rewrite(text, system_prompt)
        
        # If cloud rewrite is selected, try using Groq or Gemini depending on engine/presence of key
        # If gemini is the selected engine, default to Gemini for rewrite, otherwise default to Groq.
        if self.config.get("selected_engine") == "gemini_cloud" and self.config.get("gemini_api_key"):
            return self._gemini_rewrite(text, system_prompt)
        elif self.config.get("groq_api_key"):
            return self._groq_rewrite(text, system_prompt)
        elif self.config.get("gemini_api_key"):
            return self._gemini_rewrite(text, system_prompt)
        else:
            print("No API key available for rewriting. Returning raw text.", file=sys.stderr)
            return text

    def _groq_rewrite(self, text, system_prompt):
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.get('groq_api_key')}",
            "Content-Type": "application/json"
        }
        model = self.config.get("groq_model", "llama-3.1-8b-instant")
        print(f"Rewriting via Groq using model: {model}")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "temperature": 0.2
        }
        try:
            post_func = self.session.post if self.session else requests.post
            r = post_func(url, headers=headers, json=payload, timeout=8)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
            else:
                print(f"Groq API error ({r.status_code}): {r.text}", file=sys.stderr)
        except Exception as e:
            print(f"Groq rewrite request failed: {e}", file=sys.stderr)
        return text

    def _gemini_rewrite(self, text, system_prompt):
        model = self.config.get("gemini_model", "gemini-1.5-flash")
        print(f"Rewriting via Gemini using model: {model}")
        api_key = self.config.get("gemini_api_key")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        payload = {
            "systemInstruction": {
                "parts": [
                    {"text": system_prompt}
                ]
            },
            "contents": [
                {
                    "parts": [
                        {"text": text}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2
            }
        }
        try:
            headers = {"Content-Type": "application/json"}
            post_func = self.session.post if self.session else requests.post
            r = post_func(url, headers=headers, json=payload, timeout=8)
            if r.status_code == 200:
                res_data = r.json()
                return res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                print(f"Gemini API error ({r.status_code}): {r.text}", file=sys.stderr)
        except Exception as e:
            print(f"Gemini rewrite request failed: {e}", file=sys.stderr)
        return text

    def _ollama_rewrite(self, text, system_prompt):
        base_url = self.config.get("ollama_api_url", "http://localhost:11434").rstrip("/")
        url = f"{base_url}/api/generate"
        model = self.config.get("local_llm_model", "llama3")
        print(f"Rewriting locally via Ollama using model: {model}")
        payload = {
            "model": model,
            "prompt": f"System instruction: {system_prompt}\n\nUser text to rewrite: {text}",
            "stream": False
        }
        try:
            post_func = self.session.post if self.session else requests.post
            r = post_func(url, json=payload, timeout=60)
            if r.status_code == 200:
                return r.json().get("response", "").strip()
            else:
                print(f"Ollama API error ({r.status_code}): {r.text}", file=sys.stderr)
        except Exception as e:
            print(f"Ollama rewrite request failed (is Ollama running?): {e}", file=sys.stderr)
        return text
