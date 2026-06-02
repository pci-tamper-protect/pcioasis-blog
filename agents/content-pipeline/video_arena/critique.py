"""Text critique of a video candidate (prompt + job metadata; no vision yet)."""

from __future__ import annotations

from pathlib import Path

from ai_backend import complete


CRITIQUE_SPEC = """\
You are reviewing a SHORT-FORM VIDEO CANDIDATE for a tech explainer (Clapper / YouTube Shorts).
You have NOT seen the pixels — only the generation prompt and job metadata.

Write a concise critique (≤200 words) with sections:
## Prompt adherence (1-5)
## Expected motion quality (1-5)
## Artifact risk (1-5)
## Fit for infosec B2B short-form (1-5)
## Verdict
Recommend: ship / re-prompt / discard — and one sentence why.

Be skeptical: text-to-video often drifts on hands, text, and physics.
"""


def write_critique(
    provider_id: str,
    prompt: str,
    job: dict,
    out_path: Path,
) -> None:
    context = f"Provider: {provider_id}\n\nPrompt:\n{prompt}\n\nJob metadata:\n{job}"
    text = complete(context, CRITIQUE_SPEC, canonical_url="https://blog.pcioasis.com/")
    out_path.write_text(text.strip() + "\n", encoding="utf-8")
