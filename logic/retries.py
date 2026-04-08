import logging
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from google.api_core.exceptions import ResourceExhausted

# Configure standard PO retry policy for Vertex AI
# - Wait starts at 2s, increases exponentially up to 10s
# - Stops after 3 attempts
# - Only retries on 429 (ResourceExhausted)
# - Adds a small random jitter to prevent "thundering herd"

po_retry_policy = retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(ResourceExhausted),
    before_sleep=lambda retry_state: logging.warning(
        f"⏳ Vertex AI Rate Limit (429) hit. Retrying in {retry_state.next_action.sleep}s... "
        f"(Attempt {retry_state.attempt_number})"
    )
)
