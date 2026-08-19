"""LLM provider abstraction — all models plug in here.
هذا الملف عبارة عن طبقة تجريد (Abstraction) لمزودي الـ LLM، وجميع النماذج سيتم توصيلها (Plug in) من خلال هذه الواجهة
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)  # هذا الاختصار بسمحلي انشئ Constructor تلقائيًا   
# frozen يعني ممنوع منعا باتا التعديل ع البيانات بعد إنشائها
class LLMMessage:
    """A single message in an LLM conversation."""

    role: str  # يعني السستم ولا اليوزر
    content: str # محتوى الرسالة سواء كانت من السستم او من اليوزر

#هذه هي الصيغة الموحدة التي يتعامل معها النظام، بغض النظر عن مزود الـ LLM.


@dataclass(frozen=True)  # هذا الكلاس لتوليد الاجابة بغض النظر من اي موديل كانت
class LLMGenerationConfig:
    """Runtime generation parameters passed to providers."""

    temperature: float # هي مقدار العشوائية والابداع
    top_p: float
    max_tokens: int
    timeout_seconds: float


@dataclass(frozen=True)  # طرية الرد 
class LLMResponse:
    """Normalized response from any LLM provider."""

    content: str #1
    model: str # بروح للموديل الكونتنت
    provider: str # بشوف مين المزود تاع الموديل
    finish_reason: str | None = None # بجيب الرد
    raw: dict | None = None 
    # الraw معلومات عن usage , latency, prompt tokens , completion tokens


@runtime_checkable
class LLMProvider(Protocol):
    """Contract every LLM backend must implement."""
    #العقد (Contract) الذي يجب أن يلتزم به أي مزود LLM.

    @property
    def provider_name(self) -> str:  # كل مزود يجب أن يعرّف اسمه.
        """Human-readable provider identifier."""
        ...

    async def generate(  # هذه أهم دالة في الملف كله هي المسؤولة عن إرسال الرسائل إلى النموذج وإرجاع النتيجة
        messages: list[LLMMessage],
        config: LLMGenerationConfig,
    ) -> LLMResponse:
        """Generate a completion from the given messages."""
        ...

    async def health_check(self) -> bool:  # وظيفتها التأكد أن مزود الـ LLM يعمل ويمكن الوصول إليه.
        """Return True if the provider is reachable."""
        ...


""" 
هذا الملف لا ينفذ أي نموذج ذكاء اصطناعي، بل يضع القواعد المشتركة التي تجعل جميع مزودي الـ LLM يتصرفون بالطريقة نفسها داخل المشروع. وهو يحقق أربعة أهداف رئيسية:

توحيد شكل الرسائل عبر LLMMessage.
توحيد إعدادات التوليد عبر LLMGenerationConfig.
توحيد شكل النتائج عبر LLMResponse.
إجبار أي مزود جديد (مثل DeepSeek أو OpenAI أو Ollama) على تنفيذ نفس العقد LLMProvider.

لهذا السبب يُعد هذا الملف حجر الأساس في طبقة الـ LLM Abstraction، وهو الذي يجعل النظام قابلًا للتوسع، وسهل الصيانة، ويمكنه تبديل مزودات النماذج اللغوية بأقل قدر ممكن من التعديلات على بقية المشروع.

"""