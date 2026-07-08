"""Load API config from .env and provider presets."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"

PROVIDERS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "key_env": "OPENAI_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "key_env": "DEEPSEEK_API_KEY",
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "key_env": "MOONSHOT_API_KEY",
    },
    "dashscope": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "key_env": "DASHSCOPE_API_KEY",
    },
}


def load_dotenv(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def resolve_llm_config(provider: str | None = None) -> tuple[str, str, str]:
    load_dotenv()
    provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
    preset = PROVIDERS.get(provider, PROVIDERS["openai"])

    base_url = os.getenv("OPENAI_BASE_URL", preset["base_url"])
    model = os.getenv("OPENAI_MODEL", preset["model"])

    key = (
        os.getenv("OPENAI_API_KEY")
        or os.getenv(preset["key_env"])
        or os.getenv("LLM_API_KEY")
    )
    if not key:
        raise RuntimeError(
            f"未找到 API Key。请在 {ENV_PATH} 中设置 OPENAI_API_KEY 或 {preset['key_env']}"
        )
    return key, base_url, model