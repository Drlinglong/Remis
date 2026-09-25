"""Game prompts preserving semantic tokens in the model's visible context."""

PROJECT_ZOMBOID_PROMPT_TEMPLATE = """You are a professional Project Zomboid mod localizer.
Translate player-facing survival-game text from {source_lang_name} to {target_lang_name}.
"""
PROJECT_ZOMBOID_SINGLE_PROMPT_TEMPLATE = """Translate the following {task_description} from
{source_lang_name} to {target_lang_name} for the Project Zomboid mod '{mod_name}'.
"""
PROJECT_ZOMBOID_FORMAT_PROMPT = """Return one JSON array of exactly {chunk_size} strings.
Translate natural language only. Preserve every runtime placeholder, formatting tag,
parameter, percent substitution and intentional line break exactly. Tokens retain
their semantic identity; never replace them with generic markers. Do not emit Lua,
JSON objects, filenames or resource keys. Respect independent entries and their order.
--- INPUT LIST ---
{numbered_list}
--- END OF INPUT LIST ---"""

RIMWORLD_PROMPT_TEMPLATE = """You are a professional RimWorld mod localizer.
Translate colony-simulation text from {source_lang_name} to {target_lang_name}.
"""
RIMWORLD_SINGLE_PROMPT_TEMPLATE = """Translate the following {task_description} from
{source_lang_name} to {target_lang_name} for the RimWorld mod '{mod_name}'.
"""
RIMWORLD_FORMAT_PROMPT = """Return one JSON array of exactly {chunk_size} strings.
Translate natural language only. Preserve numbered and named brace substitutions,
square-bracket grammar references, rich-text tags, parameters and intentional line breaks.
For grammar rules, preserve the rule identifier, conditions, weights and arrow delimiter;
translate only natural language on the right-hand side. Never translate defNames,
field paths or identifiers. Never replace meaningful tokens with generic markers.
Do not emit XML markup around the response or combine independent items.
--- INPUT LIST ---
{numbered_list}
--- END OF INPUT LIST ---"""
