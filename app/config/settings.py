"""Application settings loaded from environment and YAML files."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
#.resolve() بجيب المسار كامل
# .parent ذكرناها 3 مرات عشان يرجع مجلد فوق مجلد فوق مجلد فوقه ونوصل للمكان الصحيح

# بدون الكلاس اللي تحت رح يكون عندي اكثر من ملف ومش بس هيك لكل ملف اعداداته الخاصة فبالتالي بصير الموضوع مزعج
# مع AppSettings: بعمل هذا الكلاس وبنظم كلشي فيه 
class AppSettings(BaseSettings):
    """Top-level application settings."""

    model_config = SettingsConfigDict(
        env_prefix="RETOUR_",
        env_file=".env",
        env_file_encoding="utf-8", #طريقة قراءة ملف ال .env
        extra="ignore",  # اذا وجد متغيرات اضافية ما بتخص هذا الكلاس بملف الenv ف عادي يتجاهلهم
    )
# هذول المتغيرات اللي هون مرتبطات باللي موجودات بملف ال.env
# يعني إذا لم يوجد شيء في .env يستخدم هذه.

    app_name: str = "ReTour AI Brain"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ]
    )
    prompts_directory: str = "prompts"
    package_generation_sections: list[str] = Field(
        default_factory=lambda: [
            "01_role_and_rules.md",
            "02_retriever.md",
            "03_output_schema.md",
        ]
    )
    llm_config_path: str = "config/llm.yaml"
    log_level: str = "INFO"
    planner_fast_mode: bool = False
    planner_fast_polish: bool = False
    # Team Beta Retriever (RAG) — Alpha calls this before LLM generation
    retriever_enabled: bool = True
    retriever_base_url: str = "http://127.0.0.1:8001"
    retriever_timeout_seconds: float = 120.0
    sme_data_dir: str = "data/sme data"
    tourism_data_dir: str = "data/customized_packages/knowledge"
    weather_enabled: bool = True
    weather_timeout_seconds: float = 8.0
    sme_max_per_day: int = 0
    sme_min_match_score: float = 0.35
    sme_subscription_boost_cap: float = 0.05
    retrieval_max_pois_prompt: int = 10
    retrieval_max_restaurants_prompt: int = 6
    retrieval_max_hotels_prompt: int = 4
    retrieval_max_smes_prompt: int = 2

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT    # هون بعطيني مكان المشروع

    @property
    def prompts_dir(self) -> Path:
        return PROJECT_ROOT / self.prompts_directory  # هون بعطيني مكان البرومبت

    @property
    def llm_config_file(self) -> Path:
        return PROJECT_ROOT / self.llm_config_path   # هون بعطيني مكان ال llm config


#هذا الجزء مسؤول عن شيء واحد فقط:
# قراءة إعدادات الـ LLM (الموديل) من ملف llm.yaml وتحويلها إلى كائن Python سهل الاستخدام.
# ملفات ال yaml ما بفهمها الباثون ف عشان هيك بدي اقرأهم من خلال هذا الكلاس 

class LLMSettings:
    """LLM configuration loaded from llm.yaml — change model here only."""

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path  # config_path بحفظ مكانه يعني الباث
        self._data = self._load()  # اقرأ الملف الآن واحفظ البيانات.
 
    def _load(self) -> dict[str, Any]:  # افتح ملف YAML وحوله إلى Dictionary.
        if not self._config_path.exists():
            raise FileNotFoundError(f"LLM config not found: {self._config_path}")
        with self._config_path.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def reload(self) -> None:  # يعني ال configration اللي موجودة بملفات ال yaml مرات بغيرها لما اغيرها انه يعمل ريلود عشان انه فعلا تتفعل وما ارد اشغل البرنامج بايدي خلص هو تلقائي بعمل ريلود
        """Reload configuration from disk."""
        self._data = self._load()

    @property  # @property هاي بتخلي الفنكشن كامل مثل كانه متغير يعني بدون ()
    def provider(self) -> str:
        return str(self._data.get("provider", "ollama")) # هون برجع شو البروفايدر اللي بدي اجيس منه الموديل

    @property
    def model_name(self) -> str:
        return str(self._data["model"]["name"])  # برجع اسم الموديل اللي بدي استخدمه 

    @property
    def model_display_name(self) -> str:
        return str(self._data["model"].get("display_name", self.model_name))  # هون برجع شو اعرض اسم الموديل 

    @property
    def temperature(self) -> float:
        return float(self._data["generation"]["temperature"]) # برجع ال temp

    @property
    def top_p(self) -> float:
        return float(self._data["generation"]["top_p"]) # برجع ال p

    @property
    def max_tokens(self) -> int:
        return int(self._data["generation"]["max_tokens"]) # برجع الماكي توكنز

    @property
    def timeout_seconds(self) -> float:
        return float(self._data["generation"]["timeout_seconds"]) # برجع التايم اوت

    @property
    def max_retries(self) -> int:
        return int(self._data["generation"]["max_retries"]) 

    @property
    def ollama_base_url(self) -> str:
        return str(self._data["ollama"]["base_url"])

    @property
    def ollama_api_path(self) -> str:
        return str(self._data["ollama"]["api_path"])

    @property
    def ollama_think(self) -> bool | str | None:
        """Thinking mode: a bool for Qwen3, or a level for gpt-oss.

        gpt-oss reasons no matter what `false` says — measured: 528 characters of
        thinking with `think: false` against 22 with `think: low` — and that reasoning is
        drawn from the same `num_predict` budget as the answer, so an ignored `false` can
        consume the whole budget and return empty content. Levels must therefore survive
        as strings instead of being flattened to a bool.
        """
        value = self._data.get("ollama", {}).get("think")
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip().lower() or None
        return bool(value)

    @property
    def ollama_format(self) -> str | None:
        """Ollama response format, e.g. 'json' to constrain content to a JSON object."""
        value = self._data.get("ollama", {}).get("format")
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @property
    def ollama_keep_alive(self) -> str | None:
        value = self._data.get("ollama", {}).get("keep_alive")
        return str(value) if value else None

    @property
    def ollama_num_ctx(self) -> int | None:
        """Optional Ollama context window override (helps when RAG inflates the prompt)."""
        value = self._data.get("ollama", {}).get("num_ctx")
        if value is None:
            return None
        return int(value)

    @property
    def ollama_num_gpu(self) -> int | None:
        """Layers to offload to GPU (99 ≈ all). None = Ollama default."""
        value = self._data.get("ollama", {}).get("num_gpu")
        if value is None:
            return None
        return int(value)

    def provider_config(self, provider_name: str | None = None) -> dict[str, Any]:
        """Return provider-specific configuration block."""
        name = provider_name or self.provider
        return dict(self._data.get(name, {}))


@lru_cache
def get_app_settings() -> AppSettings:
    """Cached application settings singleton."""
    return AppSettings()


def get_llm_settings() -> LLMSettings:
    """Load LLM settings from configured path."""
    settings = get_app_settings()
    return LLMSettings(settings.llm_config_file)

# الشرح للكاش تحت الفكرة مش كل مرة بدي ابني اوبجت يرد يقرأ الاعدادات لأنه همه ثابتات وما بتغيروا ف بالتالي ما في داعير بقرأهم المرة الأولى وبحفظهم ولما ارد اعمل اوبجكت ثاني بس يستخدم المحفوظ
"""  
Request 1 → اقرأ الإعدادات واحفظها

Request 2 → استخدم المحفوظ

Request 3 → استخدم المحفوظ
"""



###################################################
###################################################
""" 
فكرته الأساسية:

بدل ما يكون عندك إعدادات موزعة داخل الكود، يجمع كل إعدادات التطبيق والـ LLM في مكان واحد، يقرأها، ينظمها، ويحولها إلى Objects في Python بحيث باقي النظام يستخدمها بسهولة.

يعني هو حلقة الوصل بين ملفات الـ configuration وبين الكود.
"""