from sparkweave.services import config as config_module
from sparkweave.services.config_support import provider_catalog


def test_config_reexports_provider_catalog_objects():
    assert config_module.ProviderSpec is provider_catalog.ProviderSpec
    assert config_module.EmbeddingProviderSpec is provider_catalog.EmbeddingProviderSpec
    assert config_module.PROVIDERS is provider_catalog.PROVIDERS
    assert config_module.EMBEDDING_PROVIDERS is provider_catalog.EMBEDDING_PROVIDERS


def test_provider_catalog_lookup_helpers_cover_common_aliases():
    assert provider_catalog.canonical_provider_name("google") == "gemini"
    assert provider_catalog.find_by_name("openrouter").is_gateway is True
    assert provider_catalog.find_by_model("claude-opus-4-7").name == "anthropic"
    assert (
        provider_catalog.strip_provider_prefix(
            "openai/gpt-5.5",
            provider_catalog.find_by_name("aihubmix"),
        )
        == "gpt-5.5"
    )
