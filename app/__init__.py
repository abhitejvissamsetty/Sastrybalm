import typing
from starlette.templating import Jinja2Templates

_orig_template_response = Jinja2Templates.TemplateResponse

def _patched_template_response(self, *args: typing.Any, **kwargs: typing.Any):
    if args and isinstance(args[0], str):
        name = args[0]
        context = args[1] if len(args) > 1 else kwargs.pop("context", {})
        request = kwargs.pop("request", context.get("request") if isinstance(context, dict) else None)
        status_code = args[2] if len(args) > 2 else kwargs.pop("status_code", 200)
        headers = kwargs.pop("headers", None)
        media_type = kwargs.pop("media_type", None)
        background = kwargs.pop("background", None)
        return _orig_template_response(
            self,
            request=request,
            name=name,
            context=context,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
            **kwargs,
        )
    return _orig_template_response(self, *args, **kwargs)

Jinja2Templates.TemplateResponse = _patched_template_response
