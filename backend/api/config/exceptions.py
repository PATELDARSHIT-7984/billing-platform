class AppException(Exception):
    def __init__(self, status_code: int, message: str, details: list = None):
        self.status_code = status_code
        self.message = message
        self.details = details