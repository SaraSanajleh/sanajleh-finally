"""
Application-wide exception hierarchy.
يعني بدل ما المشروع يرمي أخطاء عشوائية، يكون عنده لغة أخطاء خاصة فيه.
بشكل عام اي لغة برمجة بكون فيها اخطاء موضحة يعني انه مثلا انه تحول ال string to int هذا الحكي بدنا نخصص اخطاء ممكن تطلع من السستم هذا يعني مش موجوة احنا رح نصنع شو الأخطاء اللي ممكن تنوجد

"""

from __future__ import annotations


class ReTourError(Exception): # هذا الكلاس يرث من Exception الأساسي في Python.
    """Base exception for all ReTour AI Brain errors."""
    """
    Python عندها:
    Exception
    ونحن نبني فوقه:
    ReTourError
    تصبح:
    Exception
        |
        |
    ReTourError هذا هو الأب اللي رح يندرج تحته العديد من الأيرورات اللي رح نصممها لاحقا  
    """

    # هون شو المسج اللي بدي اياه يطلع عشان الموضوع يكون مفهوم 
    def __init__(
        self,
        message: str,
        *,
        code: str = "retour_error",
        details: list[str] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.details = details or []
        super().__init__(message)


class ValidationError(ReTourError): # # هذا الكلاس يرث من ReTourError عشان امنع من الأخطاء اللي ما بتكون من ال llm or severs or whatever  يعني لو دخل مصاري بالسالي ف هذا لازم ينرفض وهيك يعني 
    """Raised when request or response validation fails.""" # يعني رح يطهر هذا الايرور اذا كان في اي اخطاء سواء بال request or response 
# هون ما حطيت الكود ك براميتر لانه الكود نفس تاع الأب الهم كلهم 
    def __init__(self, message: str, *args: object, **kwargs: object) -> None:
        raw = kwargs.get("details")
        if raw is None:
            details: list[str] = []
        elif isinstance(raw, list):
            details = [str(item) for item in raw]
        else:
            details = [str(raw)]
        super().__init__(message, code="validation_error", details=details)
        # السوبر هاي عشان اشغل كونسركتر الأب وببعث المسج من هون 
"""
Exception
    |
ReTourError
    |
ValidationError
لحد هون هيك الشكل صار 
"""


class LLMError(ReTourError):
    """Raised when the LLM provider fails."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        self.retryable = retryable
        super().__init__(message, code="llm_error")
# هون نفس الأفكار فوق بس انه رح احكي عن ال retryable 
# هذا متغير يخبر النظام انه الخطأ هذا هل يمكن اصلاحه او لا 

class LLMTimeoutError(LLMError):
    """Raised when an LLM request times out."""

    def __init__(self, message: str = "LLM request timed out") -> None:
        super().__init__(message, retryable=True)
# هون كذلك الامر 

class LLMResponseParseError(ReTourError): # هذا الخطأ عشان نشرح انه اذا صار في اي خطأ بقدرته ع انتاج ال json النهائي يحكيلي بالزبط انه الخطأ صار بال parse 
    """Raised when LLM output cannot be parsed as valid JSON."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="llm_parse_error")


class PackageGenerationError(ReTourError): # هاي برضه تقريبا نفس الفكرة  
    """Raised when package generation fails after retries."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="package_generation_error")


class PackageGenerationBusyError(ReTourError):
    """Raised when a generation request is already in progress."""

    def __init__(
        self,
        message: str = "Package generation already in progress. Wait for it to finish.",
    ) -> None:
        super().__init__(message, code="generation_busy")

# تعريف نظام الأخطاء الخاص بمشروع ReTour AI Brain. يعني بدل ما يستخدم أخطاء بايثون 

