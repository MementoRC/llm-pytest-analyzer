import logging
from typing import Optional

from ...utils.settings import Settings
from ..analysis.llm_suggester import LLMSuggester
from ..di.container import Container
from ..llm.backward_compat import LLMService
from ..llm.llm_service_protocol import LLMServiceProtocol

logger = logging.getLogger(__name__)


def create_llm_service(container: Container) -> Optional[LLMServiceProtocol]:
    """Factory to create an LLM service with auto-detection."""
    settings = container.resolve(Settings)
    if not settings.use_llm:
        return None
    try:
        from ..llm.llm_service_factory import detect_llm_client

        llm_client, provider = detect_llm_client(
            settings=settings,
            preferred_provider=settings.llm_provider,
            fallback=settings.use_fallback,
        )
        if llm_client:
            logger.info(
                f"Created LLM service with detected client: {type(llm_client).__name__}"
            )
        else:
            logger.warning("No LLM client detected, creating service with no client.")
        return LLMService(
            llm_client=llm_client,
            timeout_seconds=settings.llm_timeout,
            disable_auto_detection=(llm_client is None),
        )
    except ImportError:
        logger.debug(
            "LLM service factory not available, creating service with no client."
        )
        return LLMService(
            llm_client=None,
            timeout_seconds=settings.llm_timeout,
            disable_auto_detection=True,
        )
    except Exception as e:
        logger.warning(
            f"Error creating LLM service: {e}. Creating service with no client."
        )
        return LLMService(
            llm_client=None,
            timeout_seconds=settings.llm_timeout,
            disable_auto_detection=True,
        )


def create_llm_suggester(container: Container) -> Optional[LLMSuggester]:
    """Factory to create an LLM suggester."""
    settings = container.resolve(Settings)
    if not settings.use_llm:
        return None

    llm_service = container.resolve(LLMServiceProtocol)
    if llm_service:
        return LLMSuggester(
            llm_client=llm_service,
            min_confidence=settings.min_confidence,
            timeout_seconds=settings.llm_timeout,
            batch_size=settings.batch_size,
            max_concurrency=settings.max_concurrency,
        )
    return None
