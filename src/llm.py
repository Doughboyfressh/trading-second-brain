# src/llm.py
"""
TradingLLM — thin wrapper around the Anthropic SDK.

Prompt caching:  System prompts are marked with cache_control so Claude caches
them for 5 minutes (Sonnet) / 5 minutes (Haiku).  This cuts repeat API costs
by up to 90% when the same agent is called multiple times within a session.

Usage:
    llm = TradingLLM()
    text = llm.query(system_prompt, user_prompt, max_tokens=2000, model=TradingLLM.SONNET)
"""
import anthropic
import time
from config import ANTHROPIC_API_KEY


class TradingLLM:
    # Model tiers — choose per-agent based on task complexity
    SONNET = "claude-sonnet-4-6"           # Deep reasoning (strategists, critics, signals)
    HAIKU  = "claude-haiku-4-5-20251001"   # Fast summaries (data scouts, classifiers)

    # Minimum system-prompt length for caching to be worth it (Anthropic minimum is 1024 tokens)
    _CACHE_MIN_CHARS = 256

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def query(self, system_prompt: str, user_prompt: str,
              max_tokens: int = 2000, model: str = None,
              temperature: float = 0.15, retries: int = 3) -> str:
        """
        Query Claude with automatic prompt caching on the system prompt.
        The system prompt is sent with cache_control={"type": "ephemeral"} so
        Anthropic caches it for 5 minutes — subsequent calls with the same system
        prompt are served from cache and billed at 10% of normal input token cost.

        temperature : controls output randomness.
          0.0  — fully deterministic (RiskGuardian, ExecutionAgent)
          0.10 — near-deterministic for classifiers and data analysis
          0.15 — default: structured analysis with slight variation
          0.20 — signal generation, critical review, meta-evaluation
          0.30 — creative strategy refinement (Strategist, HistoricalTrainer)

        Retries on both OverloadedError and RateLimitError with exponential back-off.
        """
        model = model or self.SONNET

        # Build system block — use cache_control when prompt is long enough
        if len(system_prompt) >= self._CACHE_MIN_CHARS:
            system_block = [
                {
                    "type":  "text",
                    "text":  system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_block = system_prompt   # short prompts: plain string (no overhead)

        for attempt in range(retries):
            try:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_block,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                # Log cache hit/miss for visibility
                usage = getattr(response, "usage", None)
                if usage:
                    cached  = getattr(usage, "cache_read_input_tokens",    0) or 0
                    created = getattr(usage, "cache_creation_input_tokens", 0) or 0
                    if cached:
                        print(f"   💾 Cache HIT  ({cached:,} cached tokens saved)")
                    elif created:
                        print(f"   📝 Cache MISS ({created:,} tokens cached for next call)")
                return response.content[0].text

            except anthropic._exceptions.OverloadedError:
                wait = 2 ** attempt * 5   # 5s → 10s → 20s
                print(f"⚠️  Anthropic overloaded — retrying in {wait}s "
                      f"(attempt {attempt+1}/{retries})")
                time.sleep(wait)

            except anthropic._exceptions.RateLimitError:
                # 429: too many requests — back off the same way as overload
                wait = 2 ** attempt * 10   # 10s → 20s → 40s (rate limits need longer waits)
                print(f"⚠️  Anthropic rate limit hit — retrying in {wait}s "
                      f"(attempt {attempt+1}/{retries})")
                time.sleep(wait)

            except Exception as e:
                print(f"❌ Unexpected LLM error: {e}")
                raise

        raise RuntimeError("Claude API still unavailable after all retries (overload/rate-limit).")
