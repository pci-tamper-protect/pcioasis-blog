"""Base provider adapter for the video arena."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class ProviderResult:
    provider_id: str
    model: str
    status: str  # ok | skipped | failed
    message: str = ""
    video_path: str | None = None
    job_path: str | None = None
    elapsed_seconds: float | None = None
    extra: dict = field(default_factory=dict)

    def write(self, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "job.json").write_text(
            json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8"
        )
        if self.status == "skipped":
            (out_dir / "SKIPPED.md").write_text(
                f"# {self.provider_id}\n\n{self.message}\n", encoding="utf-8"
            )
        elif self.status == "failed":
            (out_dir / "FAILED.md").write_text(
                f"# {self.provider_id}\n\n{self.message}\n", encoding="utf-8"
            )


class ArenaProvider(ABC):
    provider_id: str = ""
    display_name: str = ""
    default_model: str = ""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True when required credentials/env are present."""

    @abstractmethod
    def missing_config_help(self) -> str:
        """Human-readable setup instructions when not configured."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        out_dir: Path,
        *,
        reference_image: Path | None = None,
    ) -> ProviderResult:
        """Generate video into out_dir/video.mp4 on success."""

    def run(
        self,
        prompt: str,
        out_dir: Path,
        *,
        reference_image: Path | None = None,
    ) -> ProviderResult:
        started = datetime.now(UTC)
        if not self.is_configured():
            result = ProviderResult(
                provider_id=self.provider_id,
                model=self.default_model,
                status="skipped",
                message=self.missing_config_help(),
            )
            result.write(out_dir)
            return result

        try:
            result = self.generate(prompt, out_dir, reference_image=reference_image)
        except Exception as exc:  # noqa: BLE001 — surface provider errors in arena manifest
            result = ProviderResult(
                provider_id=self.provider_id,
                model=self.default_model,
                status="failed",
                message=str(exc),
            )
        result.elapsed_seconds = (datetime.now(UTC) - started).total_seconds()
        result.write(out_dir)
        return result
