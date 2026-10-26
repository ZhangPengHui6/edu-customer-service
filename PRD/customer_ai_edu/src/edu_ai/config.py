from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """AI 服务配置；密钥只从环境变量/.env 读取。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "edu-ai-service"
    app_version: str = "0.1.0"
    env: str = "dev"

    database_url: str = (
        "postgresql+psycopg://customer_service:customer_service"
        "@192.168.168.100:5432/edu_ai_service"
    )
    customer_service_url: str = "http://127.0.0.1:8000"
    customer_service_timeout_seconds: float = 20.0
    internal_service_token: str = "dev-only-internal-service-token-change-me"

    # 七牛云 OpenAI 兼容网关
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://api.qnaigc.com/v1"

    # 多模型路由：主推理 / 轻量分类 / 图像理解
    main_model: str = "deepseek/deepseek-v4-pro"
    fast_model: str = "qwen/qwen3.7-flash"
    vision_model: str = "qwen2.5-vl-72b-instruct"
    llm_timeout_seconds: float = 60.0
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.0
    llm_thinking_enabled: bool = False

    # 向量检索
    milvus_uri: str = "http://192.168.168.100:19530"
    milvus_health_url: str = "http://192.168.168.100:9091/healthz"
    milvus_token: str = ""
    milvus_collection: str = "edu_cs_knowledge_v1"
    embedding_model_path: str = "C:/data/python_data/langchain/assets/models/bge-m3"
    embedding_dimension: int = 1024
    embedding_device: str = "cpu"
    embedding_batch_size: int = 16
    retrieval_top_k: int = 6
    retrieval_score_threshold: float = 0.30

    # Agent 行为
    agent_name: str = "学习机售后智能客服"
    prompt_version: str = "phase1-v1"
    max_tool_calls: int = 8
    max_correction_attempts: int = 2
    # 单次 Agent 执行上限；必须小于客服服务调用 AI 的超时时间。
    agent_execution_timeout_seconds: float = 150.0
    # 超过该时长仍为 RUNNING 的运行视为孤儿，收到重复请求时按失败收尾。
    agent_run_stale_seconds: float = 300.0
    history_message_limit: int = 20
    history_character_budget: int = 6000


@lru_cache
def get_settings() -> Settings:
    return Settings()
