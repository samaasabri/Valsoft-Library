"""Thin AI wrapper with Gemini API and Vertex AI support.

The rest of the app calls this module and stays unaware of provider details.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from ..config import get_settings

logger = logging.getLogger(__name__)

_configured = False


def _missing_config_message() -> str:
    settings = get_settings()
    provider = (settings.ai_provider or "gemini_api").strip().lower()
    if provider == "vertex_ai":
        return (
            "Vertex AI is not configured. Set AI_PROVIDER=vertex_ai, "
            "VERTEX_PROJECT_ID, and VERTEX_LOCATION."
        )
    return "Gemini is not configured. Set GEMINI_API_KEY."


def _configure() -> bool:
    global _configured
    settings = get_settings()
    if not settings.gemini_enabled:
        return False
    if _configured:
        return True
    provider = (settings.ai_provider or "gemini_api").strip().lower()
    try:
        if provider == "vertex_ai":
            import vertexai

            vertexai.init(
                project=settings.vertex_project_id,
                location=settings.vertex_location,
            )
            _configured = True
            return True

        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        _configured = True
        return True
    except Exception as e:
        logger.warning("Failed to configure AI provider (%s): %s", provider, e)
        return False


class GeminiUnavailable(RuntimeError):
    pass


AUTOFILL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "genre": {"type": "string"},
        "published_year": {"type": "integer"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "cover_keywords": {"type": "string"},
    },
    "required": ["summary", "genre", "tags"],
}

AUTOFILL_SYSTEM = (
    "You are a careful librarian assistant. Given a book's title and author, "
    "return concise, accurate metadata as JSON matching the provided schema. "
    "Rules: keep summary to 2-3 sentences, no spoilers. "
    "Pick a single best genre (e.g. 'Fantasy', 'Mystery', 'Science Fiction', 'Non-fiction'). "
    "Provide 3-6 lowercase tags. "
    "If you are not confident the book exists, return empty string for summary and empty tags. "
    "Never invent an ISBN."
)


def _parse_json_object(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = raw[start : end + 1]
        data = json.loads(snippet)
        if isinstance(data, dict):
            return data
    raise ValueError("Model did not return a valid JSON object")


def autofill_book_metadata(title: str, author: str) -> Dict[str, Any]:
    """Call Gemini to suggest metadata for a book. Raises GeminiUnavailable on fail."""
    if not _configure():
        raise GeminiUnavailable(_missing_config_message())
    settings = get_settings()
    provider = (settings.ai_provider or "gemini_api").strip().lower()

    prompt = (
        f'Book title: "{title}"\n'
        f'Author: "{author}"\n'
        "Return JSON with: summary, genre, published_year, tags (array), cover_keywords."
    )
    try:
        if provider == "vertex_ai":
            from vertexai.generative_models import GenerativeModel

            model = GenerativeModel(
                model_name=settings.gemini_model,
                system_instruction=[AUTOFILL_SYSTEM],
            )
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.4,
                    "response_mime_type": "application/json",
                },
            )
            data = _parse_json_object(getattr(response, "text", "") or "")
        else:
            import google.generativeai as genai

            model = genai.GenerativeModel(
                model_name=settings.gemini_model,
                system_instruction=AUTOFILL_SYSTEM,
            )
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.4,
                },
            )
            data = _parse_json_object(getattr(response, "text", "") or "")
    except Exception as e:
        logger.exception("Gemini autofill failed")
        raise GeminiUnavailable(f"AI request failed: {e}")

    # Defensive normalization
    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    return {
        "summary": (data.get("summary") or "").strip() or None,
        "genre": (data.get("genre") or "").strip() or None,
        "published_year": data.get("published_year"),
        "tags": [str(t).strip().lower() for t in tags if str(t).strip()],
        "cover_keywords": (data.get("cover_keywords") or "").strip() or None,
    }


# ---------------------------------------------------------------------------
# Librarian chat with function calling
# ---------------------------------------------------------------------------

LIBRARIAN_SYSTEM = (
    "You are the Mini Library's friendly AI librarian. Help the user discover books "
    "that are actually in this library. Use the provided tools to search the catalog "
    "or find similar books. Always ground recommendations in tool results - if a tool "
    "returns no books, say so and suggest a different search. Keep replies short (<= 4 "
    "sentences), warm, and end with a concrete suggestion or follow-up question. "
    "When you recommend specific books, list them by title and author."
)

LIBRARIAN_TOOLS = [
    {
        "name": "search_books",
        "description": (
            "Search the library catalog by free-text query, optional genre, author, "
            "and availability. Returns matching books."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text search across title/author/tags/summary."},
                "genre": {"type": "string", "description": "Optional genre filter."},
                "author": {"type": "string", "description": "Optional author filter."},
                "available_only": {"type": "boolean", "description": "Only return books with available copies."},
                "limit": {"type": "integer", "description": "Max number of results (default 5)."},
            },
        },
    },
    {
        "name": "recommend_similar",
        "description": "Find books in the catalog similar to the given title (by genre/tags/author).",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "A book title the user likes."},
                "limit": {"type": "integer", "description": "Max number of recs (default 5)."},
            },
            "required": ["title"],
        },
    },
]


def librarian_reply(user_message: str, tool_dispatcher) -> Dict[str, Any]:
    """Run one conversation turn with function calling.

    tool_dispatcher(name, args) -> list of book dicts for the tool result.
    Returns: { "reply": str, "books": [book dicts from tools], "tool_calls": [...] }
    """
    if not _configure():
        raise GeminiUnavailable(_missing_config_message())
    settings = get_settings()
    provider = (settings.ai_provider or "gemini_api").strip().lower()

    if provider == "vertex_ai":
        return _librarian_reply_vertex(user_message, tool_dispatcher)
    return _librarian_reply_gemini_api(user_message, tool_dispatcher)


def _librarian_reply_gemini_api(user_message: str, tool_dispatcher) -> Dict[str, Any]:
    import google.generativeai as genai
    from google.generativeai import protos

    settings = get_settings()
    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=LIBRARIAN_SYSTEM,
        tools=[{"function_declarations": LIBRARIAN_TOOLS}],
    )
    chat = model.start_chat(enable_automatic_function_calling=False)

    try:
        response = chat.send_message(user_message)
    except Exception as e:
        raise GeminiUnavailable(f"AI request failed: {e}")

    collected_books: List[Dict[str, Any]] = []
    tool_calls: List[Dict[str, Any]] = []

    for _ in range(3):  # up to 3 tool-use hops
        function_calls: List[Any] = []
        for part in getattr(response.candidates[0].content, "parts", []) or []:
            fc = getattr(part, "function_call", None)
            if fc and fc.name:
                function_calls.append(fc)
        if not function_calls:
            break
        response_parts = []
        for fc in function_calls:
            args = {k: v for k, v in (fc.args or {}).items()}
            tool_calls.append({"name": fc.name, "args": args})
            try:
                result_books = tool_dispatcher(fc.name, args) or []
                payload = {"books": result_books}
            except Exception as e:
                logger.exception("Tool %s failed", fc.name)
                result_books = []
                payload = {"error": str(e)}
            collected_books.extend(result_books)
            response_parts.append(
                protos.Part(
                    function_response=protos.FunctionResponse(name=fc.name, response=payload)
                )
            )
        try:
            response = chat.send_message(protos.Content(role="user", parts=response_parts))
        except Exception as e:
            raise GeminiUnavailable(f"AI tool-response failed: {e}")

    try:
        reply_text = response.text or ""
    except Exception:
        reply_text = ""

    return _finalize_librarian_result(reply_text, collected_books, tool_calls)


def _librarian_reply_vertex(user_message: str, tool_dispatcher) -> Dict[str, Any]:
    from vertexai.generative_models import (
        FunctionDeclaration,
        GenerativeModel,
        Part,
        Tool,
    )

    settings = get_settings()
    function_declarations = [
        FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=t["parameters"],
        )
        for t in LIBRARIAN_TOOLS
    ]
    tools = [Tool(function_declarations=function_declarations)]
    model = GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=[LIBRARIAN_SYSTEM],
        tools=tools,
    )
    chat = model.start_chat()

    try:
        response = chat.send_message(user_message)
    except Exception as e:
        raise GeminiUnavailable(f"AI request failed: {e}")

    collected_books: List[Dict[str, Any]] = []
    tool_calls: List[Dict[str, Any]] = []

    for _ in range(3):
        function_calls: List[Any] = []
        for candidate in getattr(response, "candidates", []) or []:
            parts = getattr(getattr(candidate, "content", None), "parts", []) or []
            for part in parts:
                fc = getattr(part, "function_call", None)
                if fc and getattr(fc, "name", None):
                    function_calls.append(fc)
        if not function_calls:
            break

        response_parts = []
        for fc in function_calls:
            args = {k: v for k, v in dict(getattr(fc, "args", {}) or {}).items()}
            tool_calls.append({"name": fc.name, "args": args})
            try:
                result_books = tool_dispatcher(fc.name, args) or []
                payload = {"books": result_books}
            except Exception as e:
                logger.exception("Tool %s failed", fc.name)
                result_books = []
                payload = {"error": str(e)}
            collected_books.extend(result_books)
            response_parts.append(Part.from_function_response(name=fc.name, response=payload))

        try:
            response = chat.send_message(response_parts)
        except Exception as e:
            raise GeminiUnavailable(f"AI tool-response failed: {e}")

    try:
        reply_text = response.text or ""
    except Exception:
        reply_text = ""

    return _finalize_librarian_result(reply_text, collected_books, tool_calls)


def _finalize_librarian_result(
    reply_text: str,
    collected_books: List[Dict[str, Any]],
    tool_calls: List[Dict[str, Any]],
) -> Dict[str, Any]:
    seen_ids = set()
    unique_books: List[Dict[str, Any]] = []
    for b in collected_books:
        bid = b.get("id")
        if bid in seen_ids:
            continue
        seen_ids.add(bid)
        unique_books.append(b)

    return {"reply": reply_text.strip(), "books": unique_books, "tool_calls": tool_calls}
