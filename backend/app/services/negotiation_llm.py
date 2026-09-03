"""The model that actually holds the negotiation, behind one interface.

The stt_gemini backend needs a capable model: it has to hold a multi-round
retention call, decide when to push and when to settle, and call tools while
doing it. Which provider serves that is a setting (settings.negotiation_llm),
not a hard-coded choice, because the answer changes with account entitlement:

  gemini_direct - google-genai with GEMINI_API_KEY. The default today. AssemblyAI's
                  LLM Gateway currently grants this account only its own
                  qwen3.5-4b-32k-fast, and a 4B model is not the thing to put
                  opposite a trained retention rep.
  llm_gateway   - AssemblyAI LLM Gateway. One env change away once the account
                  can reach a capable model.

Conversations are carried in OpenAI-shaped messages, since that is what LLM
Gateway speaks natively and it translates cleanly onto google-genai's Contents.
Both providers return the same LLMReply, so the caller never branches.

One wrinkle that forces a small exception to that neutrality: Gemini attaches a
thought_signature to function-call parts and rejects the next request if a
replayed call is missing it ("Function call is missing a thought_signature").
Rebuilding the part from the OpenAI form drops it, so a Gemini reply also stashes
its native Content on the assistant message under a leading-underscore key, and
that key is stripped before anything is sent to LLM Gateway.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.services.assemblyai import llm_gateway_completion
from app.services.gemini import get_client as get_gemini_client

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMReply:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    # The provider's own representation of this turn, when replaying the
    # portable form would lose something the provider needs back (Gemini's
    # thought_signature). Never sent to a different provider.
    native: Any = None


class UnknownNegotiationLLM(RuntimeError):
    pass


# ---- LLM Gateway (OpenAI-compatible) --------------------------------------


def _gateway_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """call_tools' flat Voice Agent schema in LLM Gateway's nested OpenAI form."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in tools
    ]


def _portable(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """History with provider-native baggage removed, safe to put on the wire."""
    return [
        {key: value for key, value in message.items() if not key.startswith("_")}
        for message in messages
    ]


async def _complete_via_gateway(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]]
) -> LLMReply:
    message = await llm_gateway_completion(_portable(messages), tools=_gateway_tools(tools))

    calls = []
    for call in message.get("tool_calls") or []:
        function = call["function"]
        try:
            arguments = json.loads(function.get("arguments") or "{}")
        except json.JSONDecodeError:
            arguments = {}
        calls.append(ToolCall(id=call["id"], name=function["name"], arguments=arguments))

    return LLMReply(content=message.get("content") or "", tool_calls=calls)


# ---- Gemini direct (google-genai) ------------------------------------------


def _gemini_tools(tools: list[dict[str, Any]]):
    from google.genai import types

    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=tool["name"],
                    description=tool["description"],
                    parameters=tool["parameters"],
                )
                for tool in tools
            ]
        )
    ]


def _gemini_contents(messages: list[dict[str, Any]]) -> tuple[str, list]:
    """Split OpenAI-shaped messages into (system_instruction, contents).

    Gemini takes the system prompt out of band, uses "model" where OpenAI says
    "assistant", and carries tool calls and their results as parts rather than
    as separate message roles.
    """
    from google.genai import types

    system = ""
    contents = []

    for message in messages:
        role = message.get("role")

        if role == "system":
            system = message.get("content") or ""

        elif role == "user":
            contents.append(
                types.Content(role="user", parts=[types.Part.from_text(text=message["content"])])
            )

        elif role == "assistant":
            # Replay Gemini's own turn verbatim when we have it: rebuilding a
            # function call from the OpenAI form loses the thought_signature,
            # and the next request is then rejected outright.
            native = message.get("_gemini_content")
            if native is not None:
                contents.append(native)
                continue

            parts = []
            if message.get("content"):
                parts.append(types.Part.from_text(text=message["content"]))
            for call in message.get("tool_calls") or []:
                function = call["function"]
                try:
                    arguments = json.loads(function.get("arguments") or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                parts.append(types.Part.from_function_call(name=function["name"], args=arguments))
            if parts:
                contents.append(types.Content(role="model", parts=parts))

        elif role == "tool":
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=message.get("name", "tool"),
                            response={"result": message.get("content", "")},
                        )
                    ],
                )
            )

    return system, contents


async def _complete_via_gemini(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]]
) -> LLMReply:
    from google.genai import types

    client = get_gemini_client()
    system, contents = _gemini_contents(messages)

    response = await client.aio.models.generate_content(
        model=settings.gemini_model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system or None,
            tools=_gemini_tools(tools) if tools else None,
        ),
    )

    calls = [
        # Gemini doesn't issue call ids; the name is enough to pair a result
        # back up, and the OpenAI-shaped history just needs something stable.
        ToolCall(id=f"call_{index}_{call.name}", name=call.name, arguments=dict(call.args or {}))
        for index, call in enumerate(response.function_calls or [])
    ]

    # response.text warns and returns "" when the turn is purely a function call.
    text = "".join(
        part.text for part in (candidate.content.parts or []) if getattr(part, "text", None)
    ) if (candidate := (response.candidates or [None])[0]) and candidate.content else ""

    return LLMReply(
        content=text,
        tool_calls=calls,
        native=candidate.content if candidate else None,
    )


# ---- dispatch --------------------------------------------------------------

_PROVIDERS = {
    "gemini_direct": _complete_via_gemini,
    "llm_gateway": _complete_via_gateway,
}


async def complete(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMReply:
    provider = _PROVIDERS.get(settings.negotiation_llm)
    if provider is None:
        raise UnknownNegotiationLLM(
            f"NEGOTIATION_LLM={settings.negotiation_llm!r} is not one of {sorted(_PROVIDERS)}"
        )
    return await provider(messages, tools)


def assistant_message(reply: LLMReply) -> dict[str, Any]:
    """The reply as an OpenAI-shaped assistant message, to append to history."""
    message: dict[str, Any] = {"role": "assistant", "content": reply.content}
    if reply.native is not None:
        message["_gemini_content"] = reply.native
    if reply.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
            for call in reply.tool_calls
        ]
    return message
