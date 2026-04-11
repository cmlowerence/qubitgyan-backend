import time
import logging

logger = logging.getLogger("api")

class RequestLoggingMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        start_time = time.time()

        response = self.get_response(request)

        duration = round(
            (time.time() - start_time) * 1000,
            2
        )

        logger.info(
            f"{request.method} {request.path} "
            f"{response.status_code} "
            f"{duration}ms "
            f"user={request.user}"
        )

        return response