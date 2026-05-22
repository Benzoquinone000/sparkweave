from sparkweave.api.routers import settings as settings_router


def test_settings_provider_choices_include_iflytek_spark_models() -> None:
    choices = settings_router._provider_choices()

    ws = next(item for item in choices["llm"] if item["value"] == "iflytek_spark_ws")
    assert ws["label"] == "iFlytek Spark X"
    assert ws["base_url"] == "https://spark-api-open.xf-yun.com/x2/"
    assert ws["default_model"] == "spark-x"
    assert ws["models"] == ["spark-x"]
    assert "APPID" in ws["credential_hint"]
    assert "spark-x" in ws["model_hint"]

    assert "iflytek_spark" not in {item["value"] for item in choices["llm"]}
    assert "iflytek_spark_x2" not in {item["value"] for item in choices["llm"]}
    assert "iflytek_spark_x15" not in {item["value"] for item in choices["llm"]}


def test_settings_provider_choices_include_iflytek_maas_coding() -> None:
    choices = settings_router._provider_choices()

    maas = next(item for item in choices["llm"] if item["value"] == "iflytek_maas_coding")
    assert maas["label"] == "iFlytek MaaS Coding"
    assert maas["base_url"] == "https://maas-coding-api.cn-huabei-1.xf-yun.com/v2"
    assert maas["default_model"] == "astron-code-latest"
    assert maas["models"] == ["astron-code-latest"]
    assert "APIPassword" in maas["credential_hint"]
    assert "Astron Code" in maas["model_hint"]


def test_settings_provider_choices_include_default_llm_model_options() -> None:
    choices = settings_router._provider_choices()
    llm = {item["value"]: item for item in choices["llm"]}

    assert llm["openai"]["default_model"] == "gpt-5.5"
    assert "gpt-5.5" in llm["openai"]["models"]
    assert "gpt-5.4-mini" in llm["openai"]["models"]
    assert llm["openai"]["docs_url"].startswith("https://developers.openai.com")

    assert llm["anthropic"]["default_model"] == "claude-opus-4-7"
    assert "claude-sonnet-4-6" in llm["anthropic"]["models"]

    assert llm["deepseek"]["default_model"] == "deepseek-v4-flash"
    assert llm["deepseek"]["models"][:2] == ["deepseek-v4-flash", "deepseek-v4-pro"]
    assert "deepseek-chat" in llm["deepseek"]["models"]

    assert llm["dashscope"]["default_model"] == "qwen3.6-plus"
    assert "qwen3.6-max-preview" in llm["dashscope"]["models"]

    assert llm["gemini"]["default_model"] == "gemini-3.5-flash"
    assert "gemini-3.1-pro-preview" in llm["gemini"]["models"]
    assert "gemini-2.5-flash" in llm["gemini"]["models"]


def test_settings_provider_choices_include_embedding_defaults() -> None:
    choices = settings_router._provider_choices()
    embedding = {item["value"]: item for item in choices["embedding"]}

    assert embedding["openai"]["base_url"] == "https://api.openai.com/v1"
    assert embedding["openai"]["default_model"] == "text-embedding-3-large"
    assert embedding["openai"]["models"] == ["text-embedding-3-large", "text-embedding-3-small"]
    assert embedding["openai"]["default_dim"] == "3072"
    assert embedding["openai"]["credential_hint"] == "OPENAI_API_KEY"

    assert embedding["cohere"]["default_model"] == "embed-v4.0"
    assert "embed-english-v3.0" in embedding["cohere"]["models"]
    assert embedding["cohere"]["default_dim"] == "1024"

    assert embedding["jina"]["default_model"] == "jina-embeddings-v3"
    assert "jina-clip-v2" in embedding["jina"]["models"]
    assert embedding["jina"]["default_dim"] == "1024"

    assert embedding["siliconflow"]["base_url"] == "https://api.siliconflow.cn/v1"
    assert embedding["siliconflow"]["default_model"] == "Qwen/Qwen3-Embedding-8B"
    assert "BAAI/bge-m3" in embedding["siliconflow"]["models"]
    assert embedding["siliconflow"]["default_dim"] == "4096"

    assert embedding["iflytek_spark"]["base_url"] == "https://emb-cn-huabei-1.xf-yun.com/"
    assert embedding["iflytek_spark"]["label"] == "iFlytek Spark Embedding"
    assert embedding["iflytek_spark"]["default_model"] == "llm-embedding"
    assert embedding["iflytek_spark"]["models"] == ["llm-embedding"]
    assert embedding["iflytek_spark"]["default_dim"] == "2560"

    assert embedding["ollama"]["base_url"] == "http://localhost:11434"
    assert embedding["ollama"]["default_model"] == "nomic-embed-text"
    assert "mxbai-embed-large" in embedding["ollama"]["models"]
    assert embedding["ollama"]["default_dim"] == "768"


def test_settings_provider_choices_include_iflytek_spark_search() -> None:
    choices = settings_router._provider_choices()

    search = {item["value"]: item for item in choices["search"]}
    assert search["iflytek_spark"]["label"] == "iFlytek ONE SEARCH"
    assert (
        search["iflytek_spark"]["base_url"]
        == "https://search-api-open.cn-huabei-1.xf-yun.com/v2/search"
    )
    assert "比赛" in search["iflytek_spark"]["model_hint"]


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
    assert ocr["siliconflow"]["label"] == "SiliconFlow DeepSeek-OCR"
    assert ocr["siliconflow"]["base_url"] == "https://api.siliconflow.cn/v1"
    assert ocr["siliconflow"]["default_model"] == "deepseek-ai/DeepSeek-OCR"
    assert ocr["siliconflow"]["models"] == ["deepseek-ai/DeepSeek-OCR"]
    assert ocr["disabled"]["label"] == "停用"


def test_settings_provider_choices_include_iflytek_speech_options() -> None:
    choices = settings_router._provider_choices()

    tts = {item["value"]: item for item in choices["tts"]}
    assert tts["iflytek"]["label"] == "iFlytek Super Smart TTS"
    assert tts["iflytek"]["base_url"] == "wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6"
    assert "语音生成" in tts["iflytek"]["model_hint"]
    assert tts["disabled"]["label"] == "停用"

    asr = {item["value"]: item for item in choices["asr"]}
    assert asr["iflytek"]["label"] == "iFlytek Voice Dictation"
    assert asr["iflytek"]["base_url"] == "wss://iat-api.xfyun.cn/v2/iat"
    assert "语音输入" in asr["iflytek"]["model_hint"]
    assert asr["disabled"]["label"] == "停用"

    speech_eval = {item["value"]: item for item in choices["speech_eval"]}
    assert speech_eval["iflytek"]["label"] == "iFlytek Speech Evaluation"
    assert speech_eval["iflytek"]["base_url"] == "wss://ise-api.xfyun.cn/v2/open-ise"
    assert "学习效果" in speech_eval["iflytek"]["model_hint"]
    assert speech_eval["disabled"]["label"] == "停用"

    formula_ocr = {item["value"]: item for item in choices["formula_ocr"]}
    assert formula_ocr["iflytek"]["label"] == "iFlytek Formula Recognition"
    assert formula_ocr["iflytek"]["base_url"] == "https://rest-api.xfyun.cn/v2/itr"
    assert "公式" in formula_ocr["iflytek"]["model_hint"]
    assert formula_ocr["disabled"]["label"] == "停用"

    image_understanding = {item["value"]: item for item in choices["image_understanding"]}
    assert image_understanding["iflytek"]["label"] == "iFlytek Spark Image Understanding"
    assert (
        image_understanding["iflytek"]["base_url"]
        == "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image"
    )
    assert "多模态" in image_understanding["iflytek"]["model_hint"]
    assert image_understanding["disabled"]["label"] == "停用"
