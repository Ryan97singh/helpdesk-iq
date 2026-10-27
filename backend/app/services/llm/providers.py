import json
import re
from collections.abc import Iterator

from app.core.config import Settings
from app.services.llm.base import LLMProvider, LLMRequest, LLMResult, ProviderError, Tier


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, s: Settings) -> None:
        import anthropic

        self._anthropic = anthropic
        # Retries are owned by the gateway (so they compose with fallback), not the SDK.
        self._client = anthropic.Anthropic(api_key=s.anthropic_api_key, max_retries=0, timeout=s.llm_timeout_seconds)
        self._models = {"chat": s.chat_model_claude, "fast": s.fast_model_claude}

    def model_for(self, tier: Tier) -> str:
        return self._models[tier]

    def _params(self, req: LLMRequest) -> dict:
        output_config: dict = {"effort": "low"}  # helpdesk answers and triage don't need deep reasoning
        if req.json_schema:
            output_config["format"] = {"type": "json_schema", "schema": req.json_schema}
        return {
            "model": self.model_for(req.tier),
            "max_tokens": req.max_tokens,
            "system": req.system,
            "messages": req.messages,
            "output_config": output_config,
        }

    def _wrap(self, exc: Exception) -> ProviderError:
        a = self._anthropic
        if isinstance(exc, (a.RateLimitError, a.APIConnectionError)):
            return ProviderError(f"claude: {exc}", retryable=True)
        if isinstance(exc, a.APIStatusError):
            return ProviderError(f"claude {exc.status_code}: {exc.message}", retryable=exc.status_code >= 500)
        return ProviderError(f"claude: {exc}", retryable=False)

    def _result(self, msg) -> LLMResult:
        if msg.stop_reason == "refusal":
            raise ProviderError("claude: request refused", retryable=False)
        text = "".join(b.text for b in msg.content if b.type == "text")
        return LLMResult(text, self.name, msg.model, msg.usage.input_tokens, msg.usage.output_tokens)

    def complete(self, req: LLMRequest) -> LLMResult:
        try:
            return self._result(self._client.messages.create(**self._params(req)))
        except ProviderError:
            raise
        except Exception as exc:
            raise self._wrap(exc) from exc

    def stream(self, req: LLMRequest) -> Iterator[str | LLMResult]:
        try:
            with self._client.messages.stream(**self._params(req)) as stream:
                yield from stream.text_stream
                yield self._result(stream.get_final_message())
        except ProviderError:
            raise
        except Exception as exc:
            raise self._wrap(exc) from exc


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, s: Settings) -> None:
        import openai

        self._openai = openai
        self._client = openai.OpenAI(api_key=s.openai_api_key, max_retries=0, timeout=s.llm_timeout_seconds)
        self._models = {"chat": s.chat_model_openai, "fast": s.fast_model_openai}

    def model_for(self, tier: Tier) -> str:
        return self._models[tier]

    def _params(self, req: LLMRequest) -> dict:
        params: dict = {
            "model": self.model_for(req.tier),
            "max_tokens": req.max_tokens,
            "messages": [{"role": "system", "content": req.system}, *req.messages],
        }
        if req.json_schema:
            params["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "schema": req.json_schema, "strict": True},
            }
        return params

    def _wrap(self, exc: Exception) -> ProviderError:
        o = self._openai
        if isinstance(exc, (o.RateLimitError, o.APIConnectionError)):
            return ProviderError(f"{self.name}: {exc}", retryable=True)
        if isinstance(exc, o.APIStatusError):
            return ProviderError(f"{self.name} {exc.status_code}: {exc.message}", retryable=exc.status_code >= 500)
        return ProviderError(f"{self.name}: {exc}", retryable=False)

    def complete(self, req: LLMRequest) -> LLMResult:
        try:
            r = self._client.chat.completions.create(**self._params(req))
        except Exception as exc:
            raise self._wrap(exc) from exc
        return LLMResult(r.choices[0].message.content or "", self.name, r.model,
                         r.usage.prompt_tokens, r.usage.completion_tokens)

    def stream(self, req: LLMRequest) -> Iterator[str | LLMResult]:
        try:
            chunks = self._client.chat.completions.create(
                **self._params(req), stream=True, stream_options={"include_usage": True}
            )
            parts, usage, model = [], None, self.model_for(req.tier)
            for chunk in chunks:
                if chunk.usage:
                    usage = chunk.usage
                if chunk.choices and chunk.choices[0].delta.content:
                    parts.append(chunk.choices[0].delta.content)
                    yield chunk.choices[0].delta.content
        except Exception as exc:
            raise self._wrap(exc) from exc
        yield LLMResult("".join(parts), self.name, model,
                        usage.prompt_tokens if usage else 0, usage.completion_tokens if usage else 0)


class AzureOpenAIProvider(OpenAIProvider):
    """Same wire protocol as OpenAI; models are addressed by *deployment name* inside the Azure resource."""

    name = "azure_openai"

    def __init__(self, s: Settings) -> None:
        import openai

        self._openai = openai
        self._client = openai.AzureOpenAI(
            api_key=s.azure_openai_api_key,
            azure_endpoint=s.azure_openai_endpoint or "",
            api_version=s.azure_openai_api_version,
            max_retries=0,
            timeout=s.llm_timeout_seconds,
        )
        self._models = {"chat": s.azure_chat_deployment, "fast": s.azure_fast_deployment}


class MockProvider(LLMProvider):
    """Deterministic, offline provider: makes the demo and the test-suite runnable without API keys,
    and acts as the last-resort fallback so the UI degrades gracefully instead of erroring."""

    name = "mock"

    CATEGORY_KEYWORDS = {
        "Access": ["password", "login", "vpn", "access", "locked", "mfa", "sso"],
        "Payroll": ["salary", "payslip", "payroll", "reimbursement", "tax", "bonus"],
        "HR": ["leave", "holiday", "policy", "maternity", "onboarding", "appraisal", "benefit"],
        "IT": ["laptop", "printer", "email", "software", "install", "wifi", "monitor", "outlook"],
        "Facilities": ["desk", "parking", "ac", "cafeteria", "chair", "office"],
    }

    def model_for(self, tier: Tier) -> str:
        return f"mock-{tier}"

    @staticmethod
    def _tokens(text: str) -> int:
        return max(1, len(text) // 4)

    def _answer(self, req: LLMRequest) -> str:
        if req.json_schema:
            content = req.messages[-1]["content"]
            ticket = re.search(r"<ticket>\n(.*?)\n</ticket>", content, re.S)
            return json.dumps(self._triage(ticket.group(1) if ticket else content))
        prompt = req.messages[-1]["content"]
        docs = re.findall(r'<document index="(\d+)" title="([^"]+)">\n(.*?)\n</document>', prompt, re.S)
        question = prompt.rsplit("Question:", 1)[-1]
        if not docs:
            return ("I couldn't find this in the uploaded policy documents. "
                    "Please raise a ticket and the helpdesk team will get back to you.")
        # Extractive answer: the sentences that share the most words with the question.
        from app.services.embeddings import tokenize

        q_terms = set(tokenize(question))
        scored = []
        for idx, title, body in docs:
            text = re.sub(r"^#+ .*$", "", body, flags=re.M)
            for sent in re.split(r"(?<=[.!?])\s+|\n+", text):
                overlap = len(q_terms & set(tokenize(sent)))
                if sent.strip() and overlap:
                    scored.append((overlap, -int(idx), sent.strip(), idx, title))
        if not scored:
            return f"The closest match is {docs[0][1]} [{docs[0][0]}], but it doesn't answer this directly."
        best = sorted(scored, reverse=True)[:2]
        lines = [f"- {sent} [{idx}]" for _, _, sent, idx, _ in best]
        return f"Based on {best[0][4]}:\n" + "\n".join(lines) + "\n\n(Offline mock model: set ANTHROPIC_API_KEY for Claude.)"

    def _triage(self, text: str) -> dict:
        lower = text.lower()
        scores = {c: sum(k in lower for k in kws) for c, kws in self.CATEGORY_KEYWORDS.items()}
        category = max(scores, key=scores.get) if any(scores.values()) else "Other"
        urgent = any(w in lower for w in ["urgent", "asap", "outage", "down", "cannot work", "blocked"])
        priority = "urgent" if urgent else ("high" if category == "Access" else "medium")
        return {
            "category": category,
            "priority": priority,
            "summary": text.strip().split("\n")[0][:120],
            "suggested_reply": f"Thanks for reaching out. Your {category} request has been logged with "
                               f"{priority} priority and routed to the right team.",
        }

    def complete(self, req: LLMRequest) -> LLMResult:
        text = self._answer(req)
        prompt = req.system + "".join(m["content"] for m in req.messages)
        return LLMResult(text, self.name, self.model_for(req.tier), self._tokens(prompt), self._tokens(text))

    def stream(self, req: LLMRequest) -> Iterator[str | LLMResult]:
        result = self.complete(req)
        yield from re.findall(r"\S+\s*", result.text)
        yield result
