import hmac
from typing import Dict, Optional


def verify_alertmanager_auth(
    headers: Dict[str, str],
    expected_token: Optional[str]
) -> bool:
    """
    Validates Prometheus Alertmanager webhook authentication.
    
    Security Specification:
    Alertmanager does not provide native cryptographic HMAC payload signatures.
    Instead, Prometheus Alertmanager http_config supports Bearer tokens:
      http_config:
        bearer_token: "<secret>"
    which transmits 'Authorization: Bearer <secret>' in HTTP headers.
    We also support 'X-Alertmanager-Token' for proxy setups.
    
    We verify the presence and constant-time match of the configured secret token.
    """
    if not expected_token:
        return False

    lower_headers = {k.lower(): v for k, v in headers.items()}

    # Check Authorization header (Bearer <token>)
    auth_header = lower_headers.get("authorization", "")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided = parts[1].strip()
        else:
            provided = auth_header.strip()
        if hmac.compare_digest(provided, expected_token.strip()):
            return True

    # Check X-Alertmanager-Token
    am_token = lower_headers.get("x-alertmanager-token")
    if am_token and hmac.compare_digest(am_token.strip(), expected_token.strip()):
        return True

    # Check generic X-Webhook-Token
    generic_token = lower_headers.get("x-webhook-token")
    if generic_token and hmac.compare_digest(generic_token.strip(), expected_token.strip()):
        return True

    return False
