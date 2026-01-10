import json
import logging
from typing import List, Any
from pydantic import BaseModel, Field

class NeologismTerm(BaseModel):
    original: str
    suggestion: str
    reasoning: str

class NeologismMiner:
    """
    Neologism Miner
    Extracts potential neologisms and proper nouns from source text.
    """

    SYSTEM_PROMPT_TEMPLATE = """
# Role: Senior Paradox Interactive Localization Expert / Terminology Analyst

# Goal
Your task is to read the provided game mod source text and extract all **potential, undefined proper nouns or neologisms**.
For each extracted term, you must also provide a translation suggestion and a brief reasoning based on the context.

# Game Context
You are currently working on a mod for the game: **{game_name}**.
Please ensure your analysis and translation suggestions align with the specific lore, style, and terminology of this game.

# Target Language
You should provide translation suggestions in: **{target_lang}** (Language Code: {target_lang_code})

# Extraction Rules

Please filter terms based on the following criteria:

1.  **✅ Targets**:
    *   **Proper Nouns**: Names of people, places, nations, factions (e.g., "Azura", "Gondor", "United Nations of Earth").
    *   **Fictional Concepts**: Terms coined by the author or phrases with specific meanings (e.g., "Plasteel", "Warp Drive", "Mind-Fire").
    *   **Capitalized Terms**: Non-generic words appearing in the middle of sentences with capitalized first letters.

2.  **❌ Exclusions**:
    *   **Script Code**: NEVER extract variables or commands inside `[]`, `{{}}`, `$`, `@` (e.g., `[Root.GetName]`, `$COUNTRY$`, `scope:actor`).
    *   **Color Codes**: Ignore formatting codes like `§R`, `§!`.
    *   **Generic Words**: Do not extract common English words (e.g., "Empire", "Soldier", "Technology") unless they form a specific proper noun phrase.
    *   **Numbers & Symbols**: Pure numbers or punctuation, unless they have a strong, unique meaning (e.g., "42").

# Output Format

*   **Output ONLY a raw JSON string**.
*   Format: A list of objects.
*   Example:
    [
        {{
            "original": "Aetherophasic Engine",
            "suggestion": "以太相引擎",
            "reasoning": "Aetherophasic is a compound of Aether and Phasic. Engine translates to 引擎. This term refers to a specific Stellaris crisis megastructure."
        }},
        {{
            "original": "Blorg Commonality",
            "suggestion": "布洛格公社",
            "reasoning": "Blorg is a species name, transliterated as 布洛格. Commonality implies a shared or communal government, translated as 公社 or 共联. '布洛格公社' sounds like a standard sci-fi faction name."
        }}
    ]
*   Do NOT include markdown formatting (like ```json), and do NOT include any explanatory text.
"""

    def __init__(self, client: Any):
        """
        :param client: Instance of BaseApiHandler (e.g. GeminiHandler, OpenAIHandler)
        """
        self.client = client
        self.logger = logging.getLogger(__name__)

    def extract_terms(self, text_chunk: str, target_lang: str = "Chinese", target_lang_code: str = "zh-CN", game_name: str = "Paradox Game") -> List[NeologismTerm]:
        """
        Call LLM to extract neologisms from text.
        Returns a list of NeologismTerm objects.
        """
        try:
            # Inject target language and game context into system prompt
            system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(
                target_lang=target_lang,
                target_lang_code=target_lang_code,
                game_name=game_name
            )

            # Construct Prompt
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_chunk}
            ]

            # Call LLM
            response_text = ""
            if hasattr(self.client, "generate_with_messages"):
                 response_text = self.client.generate_with_messages(messages, temperature=0.1)
            else:
                 # Fallback for clients without generate_with_messages
                 full_prompt = f"{system_prompt}\n\nInput:\n{text_chunk}\n\nOutput:"
                 if hasattr(self.client, "generate_content"):
                    response_text = self.client.generate_content(full_prompt)
                 else:
                    self.logger.error(f"Client {type(self.client)} does not support generation methods.")
                    return []

            # Parse JSON
            cleaned_response = response_text.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            
            # Handle potential non-JSON output or empty response
            if not cleaned_response:
                return []

            # Load JSON and validate with Pydantic
            terms_data = json.loads(cleaned_response)

            if not isinstance(terms_data, list):
                self.logger.warning(f"Unexpected JSON format from Neologism Miner: {terms_data}")
                return []

            valid_terms = []
            for item in terms_data:
                try:
                    term = NeologismTerm(**item)
                    valid_terms.append(term)
                except Exception as e:
                    self.logger.warning(f"Skipping invalid term: {item} - {e}")

            return valid_terms

        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse JSON from Neologism Miner response: {response_text}")
            return []
        except Exception as e:
            self.logger.error(f"Error in Neologism Miner: {e}")
            return []
