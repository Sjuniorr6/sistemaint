class NoIndexMiddleware:
    """Force noindex headers for this internal system."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet, noimageindex"
        return response
