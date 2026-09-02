import requests
import json
import sys

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
                    "You are an expert technical director. Generate a highly precise, structured, and action-oriented prompt "
                    "for an AI coding agent (like Cursor or Antigravity) based on the user's spoken instruction and the selected code/context. "
                    "Output ONLY the final prompt. No conversational filler or markdown code blocks."
                )
                user_content = (
                    f"Selected Context/Code:\n```\n{selected_text}\n```\n\n"
                    f"Spoken Instruction: {text}"
                )
            else: # clean_transcription
                system_prompt = (
                    "Du er en intelligent tekstforfatter og assistent, der hjælper med at redigere tekst, svare på mails eller skrive indhold baseret på brugerens instruktion og den markerede tekst.\n\n"
                    "Følg disse retningslinjer:\n"
                    "1. Udfør instruktionen direkte på eller i relation til den markerede tekst (f.eks. svar på mailen, forkort teksten, gør tonen mere venlig/professionel osv.).\n"
                    "2. Skriv i et naturligt, levende og professionelt sprog på samme sprog som konteksten (dansk eller engelsk).\n"
                    "3. Output KUN det færdige resultat, som skal indsættes. Ingen indledende hilsner som 'Her er dit svar:', ingen forklaringer og ingen citationstegn."
                )
                user_content = (
                    f"Markeret tekst:\n{selected_text}\n\n"
                    f"Mundtlig instruktion: {text}"
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
                "tech_doc": (
                    "Convert this spoken description into a clean, structured JSDoc, PyDoc, or Markdown system documentation "
                    "in professional English."
                ),
                "clean_transcription": self.config.get(
                    "prompt_ai",
                    "Du er en intelligent, professionel tekstforfatter og redaktør. Din opgave er at omdanne brugerens mundtlige indtaling til klar, velskrevet og naturlig tekst i samme sprog (typisk dansk eller engelsk).\n\n"
                    "Følg disse retningslinjer:\n"
                    "1. Instruktioner: Hvis indtalingen er en opgave eller instruktion (f.eks. 'Skriv en mail til...', 'Svar høfligt på...', 'Formuler en besked om...', 'Opsummer i tre punkter...'), skal du udføre opgaven og skrive den færdige mail eller besked i en passende, naturlig og professionel tone.\n"
                    "2. Rå diktat / Tanker: Hvis indtalingen er en strøm af tanker eller almindelig tale, skal du omskrive teksten, så den flyder ubesværet, fjerne fyldord/gentagelser og indsætte naturlige afsnit og tegnsætning.\n"
                    "3. Fakta & Mening: Bevar altid brugerens intention, navne og konkrete detaljer uden at opfinde nye oplysninger.\n"
                    "4. Output: Output KUN den færdige tekst klar til indsættelse – ingen indledende kommentarer, ingen forklaringer og ingen citationstegn."
                )
            }
            system_prompt = prompts.get(style, prompts["cursor_prompt"])
            query_text = text
        
        temp = 0.2 if style == "cursor_prompt" else 0.4
        
        # Decide whether to rewrite locally or in the cloud
        if self.config.get("rewrite_locally", False):
            return self._ollama_rewrite(query_text, system_prompt, temperature=temp)
        
        # If cloud rewrite is selected, try using Groq or Gemini depending on engine/presence of key
        # If gemini is the selected engine, default to Gemini for rewrite, otherwise default to Groq.
        if self.config.get("selected_engine") == "gemini_cloud" and self.config.get("gemini_api_key"):
            return self._gemini_rewrite(query_text, system_prompt, temperature=temp)
        elif self.config.get("groq_api_key"):
            return self._groq_rewrite(query_text, system_prompt, temperature=temp)
        elif self.config.get("gemini_api_key"):
            return self._gemini_rewrite(query_text, system_prompt, temperature=temp)
        else:
            print("No API key available for rewriting. Returning raw text.", file=sys.stderr)
            return text

    def _groq_rewrite(self, text, system_prompt, temperature=0.4):
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.get('groq_api_key')}",
            "Content-Type": "application/json"
        }
        model = self.config.get("groq_model", "llama-3.1-8b-instant")
        print(f"Rewriting via Groq using model: {model} (temp={temperature})")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "temperature": temperature
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

    def _gemini_rewrite(self, text, system_prompt, temperature=0.4):
        model = self.config.get("gemini_rewrite_model") or self.config.get("gemini_model", "gemini-flash-lite-latest")
        # Transcribe models only accept audio input; fallback to Flash-Lite for text rewriting
        if "transcribe" in model:
            model = "gemini-flash-lite-latest"
        print(f"Rewriting via Gemini using model: {model} (temp={temperature})")
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
                "temperature": temperature
            }
        }
        try:
            headers = {"Content-Type": "application/json"}
            post_func = self.session.post if self.session else requests.post
            r = post_func(url, headers=headers, json=payload, timeout=8)
            if r.status_code == 200:
                res_data = r.json()
                candidate = res_data.get("candidates", [{}])[0]
                content = candidate.get("content", {})
                parts = content.get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
                return text
            else:
                print(f"Gemini API error ({r.status_code}): {r.text}", file=sys.stderr)
        except Exception as e:
            print(f"Gemini rewrite request failed: {e}", file=sys.stderr)
        return text

    def _ollama_rewrite(self, text, system_prompt, temperature=0.4):
        base_url = self.config.get("ollama_api_url", "http://localhost:11434").rstrip("/")
        url = f"{base_url}/api/generate"
        model = self.config.get("local_llm_model", "llama3")
        print(f"Rewriting locally via Ollama using model: {model} (temp={temperature})")
        payload = {
            "model": model,
            "prompt": f"System instruction: {system_prompt}\n\nUser text to rewrite: {text}",
            "stream": False,
            "options": {
                "temperature": temperature
            }
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
