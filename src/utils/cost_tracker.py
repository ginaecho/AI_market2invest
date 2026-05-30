"""
Cost tracker — estimates and tracks API spending across the pipeline.

Tracks:
• Kimi API calls (input + output tokens)
• OpenAI API calls (input + output tokens)
• Per-stage breakdown
• Total estimated cost in USD

SECURITY NOTES
--------------
• No network calls — pure local token counting with tiktoken.
• Cost rates are configurable in config.yaml, not hardcoded.
• No eval/exec.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

try:
    import tiktoken
    _ENCODING = tiktoken.get_encoding("cl100k_base")
except Exception:
    _ENCODING = None

logger = logging.getLogger(__name__)

# Default cost rates (USD per 1K tokens)
_DEFAULT_RATES = {
    "kimi": {"input": 0.0015, "output": 0.008},
    "openai": {"input": 0.00015, "output": 0.0006},
    "gemini": {"input": 0.0001, "output": 0.0004},   # Flash-Lite
    "claude": {"input": 0.0008, "output": 0.004},    # Haiku
}


@dataclass
class APICall:
    """Record of a single API call."""
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    stage: str
    description: str


class CostTracker:
    """
    Accumulates API usage and computes cost estimates.
    Use as a singleton across the pipeline run.
    """

    def __init__(self, rates: Dict[str, Dict[str, float]] | None = None) -> None:
        self.rates = rates or _DEFAULT_RATES
        self.calls: List[APICall] = []
        self.estimated_calls: int = 0
        self.estimated_input_tokens: int = 0
        self.estimated_output_tokens: int = 0

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    @staticmethod
    def count_tokens(text: str) -> int:
        """Count tokens using cl100k_base encoding (GPT-4 / Kimi compatible)."""
        if _ENCODING is None:
            # Fallback: rough heuristic ~4 chars per token
            return len(text) // 4
        try:
            return len(_ENCODING.encode(text))
        except Exception:
            return len(text) // 4

    # ------------------------------------------------------------------
    # Recording actual usage
    # ------------------------------------------------------------------

    def record(
        self,
        provider: str,
        model: str,
        input_text: str,
        output_text: str,
        stage: str = "",
        description: str = "",
    ) -> None:
        """Record an API call after it completes."""
        input_tokens = self.count_tokens(input_text)
        output_tokens = self.count_tokens(output_text)
        self.calls.append(
            APICall(
                provider=provider.lower(),
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                stage=stage,
                description=description,
            )
        )
        logger.debug(
            "Recorded %s call: %d in + %d out tokens (%s)",
            provider,
            input_tokens,
            output_tokens,
            description,
        )

    def record_tokens(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        stage: str = "",
        description: str = "",
    ) -> None:
        """Record an API call with pre-counted tokens."""
        self.calls.append(
            APICall(
                provider=provider.lower(),
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                stage=stage,
                description=description,
            )
        )

    # ------------------------------------------------------------------
    # Estimation (pre-flight)
    # ------------------------------------------------------------------

    def estimate_api_call(
        self,
        provider: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost of a single API call in USD."""
        rates = self.rates.get(provider.lower(), {})
        in_rate = rates.get("input", 0.0)
        out_rate = rates.get("output", 0.0)
        cost = (input_tokens / 1000 * in_rate) + (output_tokens / 1000 * out_rate)
        return cost

    def add_estimate(
        self,
        provider: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Add to the pre-flight estimate."""
        self.estimated_calls += 1
        self.estimated_input_tokens += input_tokens
        self.estimated_output_tokens += output_tokens

    def total_estimate(self) -> Dict[str, Any]:
        """Return pre-flight cost estimate breakdown."""
        in_cost = sum(
            self.estimated_input_tokens / 1000 * self.rates.get(p, {}).get("input", 0.0)
            for p in set(c.provider for c in self.calls) | {"kimi", "openai"}
        )
        out_cost = sum(
            self.estimated_output_tokens / 1000 * self.rates.get(p, {}).get("output", 0.0)
            for p in set(c.provider for c in self.calls) | {"kimi", "openai"}
        )
        # Avoid double-counting: just use average rates for estimate
        avg_in_rate = (
            sum(self.rates.get(p, {}).get("input", 0.0) for p in self.rates) / len(self.rates)
            if self.rates else 0.0
        )
        avg_out_rate = (
            sum(self.rates.get(p, {}).get("output", 0.0) for p in self.rates) / len(self.rates)
            if self.rates else 0.0
        )
        est_cost = (
            self.estimated_input_tokens / 1000 * avg_in_rate
            + self.estimated_output_tokens / 1000 * avg_out_rate
        )
        return {
            "calls": self.estimated_calls,
            "input_tokens": self.estimated_input_tokens,
            "output_tokens": self.estimated_output_tokens,
            "estimated_cost_usd": round(est_cost, 4),
        }

    # ------------------------------------------------------------------
    # Actuals (post-run)
    # ------------------------------------------------------------------

    def total_actual(self) -> Dict[str, Any]:
        """Return actual cost breakdown."""
        total_in = sum(c.input_tokens for c in self.calls)
        total_out = sum(c.output_tokens for c in self.calls)
        cost = 0.0
        for c in self.calls:
            rates = self.rates.get(c.provider, {})
            cost += c.input_tokens / 1000 * rates.get("input", 0.0)
            cost += c.output_tokens / 1000 * rates.get("output", 0.0)

        by_provider: Dict[str, Dict[str, Any]] = {}
        for c in self.calls:
            p = c.provider
            if p not in by_provider:
                by_provider[p] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
            by_provider[p]["calls"] += 1
            by_provider[p]["input_tokens"] += c.input_tokens
            by_provider[p]["output_tokens"] += c.output_tokens
            rates = self.rates.get(p, {})
            by_provider[p]["cost_usd"] += (
                c.input_tokens / 1000 * rates.get("input", 0.0)
                + c.output_tokens / 1000 * rates.get("output", 0.0)
            )

        by_stage: Dict[str, Dict[str, Any]] = {}
        for c in self.calls:
            s = c.stage or "other"
            if s not in by_stage:
                by_stage[s] = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
            by_stage[s]["calls"] += 1
            by_stage[s]["input_tokens"] += c.input_tokens
            by_stage[s]["output_tokens"] += c.output_tokens

        return {
            "total_calls": len(self.calls),
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "total_cost_usd": round(cost, 4),
            "by_provider": {
                k: {
                    "calls": v["calls"],
                    "input_tokens": v["input_tokens"],
                    "output_tokens": v["output_tokens"],
                    "cost_usd": round(v["cost_usd"], 4),
                }
                for k, v in by_provider.items()
            },
            "by_stage": by_stage,
        }

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def summary_table(self) -> str:
        """Return a Markdown table of the cost breakdown."""
        actual = self.total_actual()
        lines = [
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total API calls | {actual['total_calls']} |",
            f"| Input tokens | {actual['total_input_tokens']:,} |",
            f"| Output tokens | {actual['total_output_tokens']:,} |",
            f"| **Total cost** | **${actual['total_cost_usd']}** |",
        ]
        for provider, data in actual["by_provider"].items():
            lines.append(
                f"| {provider.capitalize()} ({data['calls']} calls) | ${data['cost_usd']} |"
            )
        return "\n".join(lines)


# Singleton instance
_tracker: CostTracker | None = None


def get_tracker(rates: Dict[str, Dict[str, float]] | None = None) -> CostTracker:
    """Get or create the global cost tracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = CostTracker(rates=rates)
    return _tracker


def reset_tracker(rates: Dict[str, Dict[str, float]] | None = None) -> CostTracker:
    """Reset and return a fresh tracker."""
    global _tracker
    _tracker = CostTracker(rates=rates)
    return _tracker
