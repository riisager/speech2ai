import requests
import json
import sys

def clean_llm_output(output_str):
    """Strips unnecessary markdown wrappers and quotes from LLM responses."""
    if not output_str:
        return ""
    text = output_str.strip()
    
    # Strip markdown code blocks if the entire response is wrapped in them
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            text = "\n".join(lines[1:-1]).strip()

    # Strip surrounding quotes if wrapped
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        if len(text) >= 2:
            text = text[1:-1].strip()

    return text


class RewriteEngine:
    def __init__(self, config, session=None):
        self.config = config
        self.session = session

    def process(self, text, style="cursor_prompt", selected_text=None):
        """Rewrites the transcribed text based on style and configured engine."""
        if not text or not text.strip():
            return ""

        if selected_text:
            if style == "cursor_prompt":
                system_prompt = (
                    "You are an expert technical director. Translate the user's spoken thoughts and the highlighted context into "
                    "a highly precise, single, actionable prompt for an AI coding agent (like Cursor or Antigravity). "
                    "Output ONLY the final prompt. No conversational filler, no commentary, no markdown code blocks."
                )
                user_content = (
                    f"Selected Context:\n```\n{selected_text}\n```\n\n"
                    f"Spoken Instruction: {text}"
                )
            else: # clean_transcription
                system_prompt = (
                    "Du er en professionel korrekturlæser og sprogassistent. Din opgave er at renskrive og optimere den mundtlige diktat til flydende, korrekt dansk eller engelsk.\n"
                    "- Ret grammatiske fejl, stavefejl og ufuldstændige sætninger.\n"
                    "- Fjern tøveord og fyldord (f.eks. 'øh', 'æh', 'um', 'du ved').\n"
                    "- Bevar sproget fra den mundtlige diktat (dansk eller engelsk).\n"
                    "- Output KUN den færdige, rensede tekst. Skriv ALDRIG samtaler, forklaringer, 'Her er dit svar', eller alternative svarmuligheder."
                )
                user_content = (
                    f"Kontekst (hvis relevant):\n{selected_text}\n\n"
                    f"Mundtlig diktat: {text}"
                )
            query_text = user_content
        else:
            prompts = {
                "cursor_prompt": self.config.get(
                    "prompt_ai_prompt",
                    "You are an expert technical director. Translate the following spoken Danish/English description "
                    "into a highly precise, structured, and action-oriented prompt for an AI coding agent (like Cursor or Antigravity). "
                    "Focus on strict technical requirements, libraries, and clean architecture. "
                    "Output ONLY the final prompt. No conversational filler or markdown code blocks."
                ),
                "clean_transcription": self.config.get(
                    "prompt_ai",
                    "You are a professional editor. Clean up the following spoken transcription. "
                    "Fix grammatical errors, remove stutters, filler words, and clean up sentence structure. "
                    "Keep the language of the original text (Danish or English). "
                    "Output ONLY the cleaned text. Never include explanations or alternative options."
                )
            }
            system_prompt = prompts.get(style, prompts["clean_transcription"])
            query_text = text
        
        # Decide whether to rewrite locally or in the cloud
        if self.config.get("rewrite_locally", False):
            result = self._ollama_rewrite(query_text, system_prompt)
        elif self.config.get("selected_engine") == "gemini_cloud" and self.config.get("gemini_api_key"):
            result = self._gemini_rewrite(query_text, system_prompt)
        elif self.config.get("groq_api_key"):
            result = self._groq_rewrite(query_text, system_prompt)
        elif self.config.get("gemini_api_key"):
            result = self._gemini_rewrite(query_text, system_prompt)
        else:
            print("No API key available for rewriting. Returning raw text.", file=sys.stderr)
            result = text

        return clean_llm_output(result)

    def _groq_rewrite(self, text, system_prompt):
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.get('groq_api_key')}",
            "Content-Type": "application/json"
        }
        model = self.config.get("groq_model", "llama-3.1-8b-instant")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "temperature": 0.1
        }
        try:
            post_func = self.session.post if self.session else requests.post
            r = post_func(url, headers=headers, json=payload, timeout=12)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
            else:
                print(f"Groq API error ({r.status_code}): {r.text}", file=sys.stderr)
        except Exception as e:
            print(f"Groq rewrite request failed: {e}", file=sys.stderr)
        return text

    def _gemini_rewrite(self, text, system_prompt):
        model = self.config.get("gemini_model", "gemini-1.5-flash")
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
                "temperature": 0.1
            }
        }
        try:
            headers = {"Content-Type": "application/json"}
            post_func = self.session.post if self.session else requests.post
            r = post_func(url, headers=headers, json=payload, timeout=12)
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
