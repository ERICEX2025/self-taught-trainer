"""One async OpenAI client with a concurrency cap, retries, and timing, so speed is measurable."""
import asyncio
import os
import time

from openai import AsyncOpenAI


class LLM:
    def __init__(self, play_model: str | None = None, coach_model: str | None = None, concurrency: int = 8):
        self.client = AsyncOpenAI()
        self.play_model = play_model or os.environ.get("PLAY_MODEL", "gpt-5.4-mini")
        self.coach_model = coach_model or os.environ.get("COACH_MODEL", "gpt-5.4")
        self.sem = asyncio.Semaphore(concurrency)
        self.calls = self.errors = 0
        self.seconds = 0.0
        self.last_error = ""
        # Newer reasoning models think before answering; keep that to a minimum for the player.
        self.reasoning = os.environ.get("PLAY_REASONING", "none")

    async def complete(self, system: str, user: str, model: str, max_tokens: int = 120) -> str:
        async with self.sem:
            for attempt in range(4):
                t0 = time.perf_counter()
                try:
                    self.calls += 1
                    extra = {}
                    if model.startswith(("gpt-5", "o")):
                        extra["reasoning_effort"] = self.reasoning if model == self.play_model else "medium"
                        max_tokens = max(max_tokens, 2000)  # thinking tokens count toward the limit
                    r = await self.client.chat.completions.create(
                        model=model, max_completion_tokens=max_tokens, **extra,
                        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
                    self.seconds += time.perf_counter() - t0
                    return r.choices[0].message.content or ""
                except Exception as e:  # rate limits and transient errors
                    self.errors += 1
                    self.last_error = f"{type(e).__name__}: {str(e)[:200]}"
                    await asyncio.sleep(1.5 * (attempt + 1))
            return ""

    @property
    def avg_seconds(self) -> float:
        ok = self.calls - self.errors
        return self.seconds / ok if ok > 0 else 0.0
