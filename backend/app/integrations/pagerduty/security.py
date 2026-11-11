import hmac
import hashlib
from typing import Optional, Dict


def verify_pagerduty_signature(raw_body: bytes, headers: Dict[str, str], secret: Optional[str]) -> bool:
    """
    Verifies PagerDuty Webhook v3 cryptographic signature.
    Official specification:
      Header: X-PagerDuty-Signature: v1=<hmac_sha256_hex>
      Algorithm: HMAC-SHA256(secret, raw_request_body)
      Supports multiple comma-separated signatures for key rotation.
    """
    if not secret:
        # If secret is not configured on server, cannot verify signature
        return False

    # Extract signature header (case-insensitive lookup)
    signature_header = None
    for k, v in headers.items():
        if k.lower() == "x-pagerduty-signature":
            signature_header = v
            break

    if not signature_header:
        # Fallback check for custom token header if configured
        auth_header = None
        for k, v in headers.items():
            if k.lower() in ("x-webhook-token", "x-pagerduty-token"):
                auth_header = v
                break
        if auth_header and hmac.compare_digest(auth_header, secret):
            return True
        return False

    # Compute expected signature
    secret_bytes = secret.encode("utf-8")
    expected_hex = hmac.new(secret_bytes, raw_body, hashlib.sha256).hexdigest()

    # PagerDuty may send comma-separated signatures during key rotation: "v1=sig1, v1=sig2"
    signature_parts = [part.strip() for part in signature_header.split(",")]
    for part in signature_parts:
        if part.startswith("v1="):
            candidate_sig = part[3:]
            if hmac.compare_digest(expected_hex, candidate_sig):
                return True

    return False
