from typing import Dict, Any
from requests import Response


class HttpErrorMapper:
    @staticmethod
    def map_to_rfc7807(response: Response) -> Dict[str, Any]:
        """
        Problem Details for HTTP APIs.
        """
        status = response.status_code
        url = response.url

        error_rfc = {
            "type": "about:blank",
            "title": "External API Error",
            "status": status,
            "detail": "An unexpected error occurred",
            "instance": url
        }

        try:
            body = response.json()
        except Exception:
            error_rfc["detail"] = response.text or "No content returned"
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
            error_rfc["title"] = body.get("error", "Invalid Request")
            error_rfc["detail"] = body.get("message", str(body))

        return error_rfc