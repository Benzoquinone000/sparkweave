from sparkweave.api.routers import settings as settings_router


def test_settings_provider_choices_include_iflytek_spark_models() -> None:
    choices = settings_router._provider_choices()

    ws = next(item for item in choices["llm"] if item["value"] == "iflytek_spark_ws")
    assert ws["label"] == "iFlytek Spark X"
    assert ws["base_url"] == "https://spark-api-open.xf-yun.com/x2/"
    assert ws["default_model"] == "spark-x"
    assert ws["models"] == ["spark-x"]

    assert "iflytek_spark" not in {item["value"] for item in choices["llm"]}
    assert "iflytek_spark_x2" not in {item["value"] for item in choices["llm"]}
    assert "iflytek_spark_x15" not in {item["value"] for item in choices["llm"]}


def test_settings_provider_choices_include_default_llm_model_options() -> None:
    choices = settings_router._provider_choices()
    llm = {item["value"]: item for item in choices["llm"]}

    assert llm["openai"]["default_model"] == "gpt-5.2"
    assert "gpt-5.2" in llm["openai"]["models"]
    assert "gpt-5-mini" in llm["openai"]["models"]

    assert llm["anthropic"]["default_model"] == "claude-opus-4-1-20250805"
    assert "claude-sonnet-4-20250514" in llm["anthropic"]["models"]

    assert llm["deepseek"]["default_model"] == "deepseek-chat"
    assert llm["deepseek"]["models"] == ["deepseek-chat", "deepseek-reasoner"]

    assert llm["dashscope"]["default_model"] == "qwen3.6-plus"
    assert "qwen3.6-max-preview" in llm["dashscope"]["models"]

    assert llm["gemini"]["default_model"] == "gemini-3-pro-preview"
    assert "gemini-2.5-flash" in llm["gemini"]["models"]


def test_settings_provider_choices_include_embedding_defaults() -> None:
    choices = settings_router._provider_choices()
    embedding = {item["value"]: item for item in choices["embedding"]}

    assert embedding["openai"]["base_url"] == "https://api.openai.com/v1"
    assert embedding["openai"]["default_model"] == "text-embedding-3-large"
    assert embedding["openai"]["models"] == ["text-embedding-3-large"]
    assert embedding["openai"]["default_dim"] == "3072"

    assert embedding["cohere"]["default_model"] == "embed-v4.0"
    assert embedding["cohere"]["default_dim"] == "1024"

    assert embedding["jina"]["default_model"] == "jina-embeddings-v3"
    assert embedding["jina"]["default_dim"] == "1024"

    assert embedding["iflytek_spark"]["base_url"] == "https://emb-cn-huabei-1.xf-yun.com/"
    assert embedding["iflytek_spark"]["label"] == "iFlytek Spark Embedding"
    assert embedding["iflytek_spark"]["default_model"] == "llm-embedding"
    assert embedding["iflytek_spark"]["default_dim"] == "2560"

    assert embedding["ollama"]["base_url"] == "http://localhost:11434"
    assert embedding["ollama"]["default_model"] == "nomic-embed-text"
    assert embedding["ollama"]["default_dim"] == "768"


def test_settings_provider_choices_include_iflytek_spark_search() -> None:
    choices = settings_router._provider_choices()

    search = {item["value"]: item for item in choices["search"]}
    assert search["iflytek_spark"]["label"] == "iFlytek ONE SEARCH"
    assert (
        search["iflytek_spark"]["base_url"]
        == "https://search-api-open.cn-huabei-1.xf-yun.com/v2/search"
    )


def test_settings_provider_choices_include_search_base_urls() -> None:
    choices = settings_router._provider_choices()
    search = {item["value"]: item for item in choices["search"]}

    assert search["brave"]["base_url"] == "https://api.search.brave.com/res/v1/web/search"
    assert search["tavily"]["base_url"] == "https://api.tavily.com/search"
    assert search["jina"]["base_url"] == "https://s.jina.ai"
    assert search["searxng"]["base_url"] == "http://localhost:8080"
    assert search["duckduckgo"]["base_url"] == "https://duckduckgo.com"
    assert search["perplexity"]["base_url"] == "https://api.perplexity.ai"
    assert search["serper"]["base_url"] == "https://google.serper.dev"
    assert search["iflytek_spark"]["base_url"] == "https://search-api-open.cn-huabei-1.xf-yun.com/v2/search"


def test_settings_provider_choices_include_ocr_options() -> None:
    choices = settings_router._provider_choices()
    ocr = {item["value"]: item for item in choices["ocr"]}

    assert ocr["iflytek"]["label"] == "iFlytek OCR for LLM"
    assert ocr["iflytek"]["base_url"] == "https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm"
    assert ocr["disabled"]["label"] == "Disabled"
