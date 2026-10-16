from collections.abc import Mapping
from typing import Dict, Any, Optional
from requests import Response

# Request id the platform gateway (AWS) stamps on every response; the only
# handle support has to trace one specific failed call.
PLATFORM_REQUEST_ID_HEADER = "x-amzn-requestid"


def _platform_request_id(response: Response) -> Optional[str]:
    headers = getattr(response, "headers", None)
    if not isinstance(headers, Mapping):
        return None
    for key, value in headers.items():
        if str(key).lower() == PLATFORM_REQUEST_ID_HEADER and value:
            return str(value)
    return None


def _body_error_code(body: Any) -> Optional[str]:
    """Machine-readable error code, if the body carries one.

    The api-finder speaks `{"code", "message"}` while other platform routes
    speak `{"error", "message"}`; both are accepted.
    """
    if not isinstance(body, dict):
        return None
    code = body.get("code") or body.get("error")
    return str(code) if code else None


class HttpErrorMapper:
    @staticmethod
    def map_to_rfc7807(response: Response) -> Dict[str, Any]:
        """
        Problem Details for HTTP APIs.

        `code` and `request_id` are RFC 7807 extension members kept for
        diagnostics (logs only — never meant for end-user output).
        """
        status = response.status_code
        url = response.url

        error_rfc = {
            "type": "about:blank",
            "title": "External API Error",
            "status": status,
            "detail": "An unexpected error occurred",
            "instance": url,
            "code": None,
            "request_id": _platform_request_id(response),
        }

        try:
            body = response.json()
        except Exception:
            error_rfc["detail"] = response.text or "No content returned"
            return error_rfc

        error_rfc["code"] = _body_error_code(body)
        if not isinstance(body, dict):
            error_rfc["detail"] = str(body)
            return error_rfc

        if status == 404:
            error_rfc["title"] = "Not Found"
            if "errors" in body and isinstance(body["errors"], list) and len(body["errors"]) > 0:
                error_rfc["detail"] = body["errors"][0].get("message", "Unknown 404 error")
            else:
                error_rfc["detail"] = body.get("message", "Resource not found")

        elif status == 401:
            error_rfc["title"] = "Unauthorized"
            error_rfc["detail"] = body.get("message", "Authentication required")

        elif status == 403:
            error_rfc["title"] = "Forbidden"
            error_rfc["detail"] = body.get("message", "Access denied")

        elif status == 415:
            error_rfc["title"] = body.get("error", "Unsupported Media Type")
            error_rfc["detail"] = body.get("message", "Content-Type or Content-Encoding not supported")

        else:
            error_rfc["title"] = body.get("error") or body.get("code") or "Invalid Request"
            error_rfc["detail"] = body.get("message", str(body))

        return error_rfc