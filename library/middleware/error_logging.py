import logging

logger = logging.getLogger("errors")

class ErrorLoggingMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        try:
            return self.get_response(request)

        except Exception as e:
            logger.error(
                f"Unhandled Error | "
                f"path={request.path} "
                f"user={request.user} "
                f"error={str(e)}",
                exc_info=True
            )
            raise