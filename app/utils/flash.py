from fastapi import Request


def get_flash(request: Request) -> dict:
    """Pop flash messages from session and return as template context dict."""
    return {
        "flash_success": request.session.pop("_flash_success", None),
        "flash_error": request.session.pop("_flash_error", None),
    }


def set_flash_success(request: Request, message: str) -> None:
    request.session["_flash_success"] = message


def set_flash_error(request: Request, message: str) -> None:
    request.session["_flash_error"] = message
