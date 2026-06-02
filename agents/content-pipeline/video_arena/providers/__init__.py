"""Video generation provider adapters."""

from video_arena.providers.base import ArenaProvider, ProviderResult

PROVIDERS: dict[str, type[ArenaProvider]] = {}


def register(provider_cls: type[ArenaProvider]) -> type[ArenaProvider]:
    PROVIDERS[provider_cls.provider_id] = provider_cls
    return provider_cls


def all_providers() -> list[type[ArenaProvider]]:
    # Import registers side effects
    from video_arena.providers import (  # noqa: F401
        azure_sora,
        bedrock_luma,
        replicate_hailuo,
        vertex_veo,
    )

    return [
        PROVIDERS["azure_sora"],
        PROVIDERS["bedrock_luma"],
        PROVIDERS["vertex_veo"],
        PROVIDERS["replicate_hailuo"],
    ]
