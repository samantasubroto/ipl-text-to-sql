"""Turn a natural-language question into a SQL query using OpenAI.

Try it from the project root:
    python -m src.llm "Which team won the most matches in 2016?"
"""
import re
import sys

from openai import OpenAI

from src.config import get_settings
from src.schema import get_schema_description

SYSTEM_PROMPT = """You are an expert SQLite analyst. Convert the user's question into \
one SQLite SELECT query for the database described below.

Rules:
- Return only the SQL query, with no explanation and no markdown.
- Use only the tables and columns listed in the schema.
- Write a single read-only SELECT statement. Never modify data.
- If the question cannot be answered from this schema, return exactly: CANNOT_ANSWER

{schema}
"""


def _clean_sql(text: str) -> str:
    """Strip markdown code fences if the model added them."""
    text = text.strip()
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
    return text


def _require(value: str | None, name: str) -> str:
    if not value:
        raise RuntimeError(f"{name} is not set in .env")
    return value


def _generate_openai(system_prompt: str, question: str, settings) -> str:
    client = OpenAI(api_key=_require(settings.openai_api_key, "OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=_require(settings.openai_model, "OPENAI_MODEL"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
    )
    return response.choices[0].message.content or ""


def _generate_gemini(system_prompt: str, question: str, settings) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_require(settings.gemini_api_key, "GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=_require(settings.gemini_model, "GEMINI_MODEL"),
        contents=question,
        config=types.GenerateContentConfig(system_instruction=system_prompt),
    )
    return response.text or ""


def generate_sql(question: str) -> str:
    """Return a SQL string for the question, or 'CANNOT_ANSWER'.

    The provider is chosen by LLM_PROVIDER in .env ('openai' or 'gemini').
    """
    settings = get_settings()
    system_prompt = SYSTEM_PROMPT.format(schema=get_schema_description())

    if settings.llm_provider == "gemini":
        text = _generate_gemini(system_prompt, question, settings)
    else:
        text = _generate_openai(system_prompt, question, settings)
    return _clean_sql(text)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('Usage: python -m src.llm "your question"')
    print(generate_sql(" ".join(sys.argv[1:])))
