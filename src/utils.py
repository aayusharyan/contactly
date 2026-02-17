"""
Retry utilities with exponential backoff strategy.

Provides decorators for automatic retry logic when dealing with unreliable network
operations, rate-limited APIs, and transient failures. The exponential backoff
algorithm progressively increases delay between attempts to avoid overwhelming
remote services while maintaining reasonable retry behavior.
"""

import time
import logging
from functools import wraps
from typing import Callable, Any, Type, Tuple

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 300.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator that automatically retries failed function calls with exponential backoff.
    Delay doubles after each failure: base_delay, 2x, 4x, 8x, up to max_delay.
    Useful for handling rate limits and transient network errors.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exceptions: Tuple of exception types to catch and retry
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            retries = 0

            while retries < max_retries:
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    retries += 1

                    # Re-raise if we've exhausted all retries
                    if retries >= max_retries:
                        logger.error(f"Max retries ({max_retries}) reached for {func.__name__}")
                        raise

                    # Calculate exponential backoff: base_delay * 2^(retries-1), capped at max_delay
                    delay = min(base_delay * (2 ** (retries - 1)), max_delay)
                    logger.warning(
                        f"Attempt {retries}/{max_retries} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)

            return func(*args, **kwargs)

        return wrapper
    return decorator
