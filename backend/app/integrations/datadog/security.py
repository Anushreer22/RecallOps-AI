import hmac
from typing import Dict, Optional


def verify_datadog_token(
    headers: Dict[str, str],
    expected_token: Optional[str]
) -> bool:
    """
    Validates Datadog webhook authentication.
    
    Security Specification:
    Datadog webhooks do NOT support native HMAC-SHA256 payload signing.
    Instead, Datadog supports sending custom headers configured on the webhook destination
    (e.g., 'X-Datadog-Webhook-Token' or 'Authorization: Bearer <token>').
    
    We verify the presence and constant-time match of the configured secret token.
    """
    if not expected_token:
        return False

    # Normalize header keys to lowercase
    lower_headers = {k.lower(): v for k, v in headers.items()}

    # Check X-Datadog-Webhook-Token
    token_header = lower_headers.get("x-datadog-webhook-token")
    if token_header and hmac.compare_digest(token_header.strip(), expected_token.strip()):
        return True

    # Check Authorization: Bearer <token> or direct token
    auth_header = lower_headers.get("authorization", "")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided = parts[1].strip()
        else:
            provided = auth_header.strip()
        if hmac.compare_digest(provided, expected_token.strip()):
            return True

    # Check generic X-Webhook-Token
    generic_token = lower_headers.get("x-webhook-token")
    if generic_token and hmac.compare_digest(generic_token.strip(), expected_token.strip()):
        return True

    return False
