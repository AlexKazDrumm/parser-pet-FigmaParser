from __future__ import annotations


class FigmaExporterError(Exception):
    status_code: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigurationError(FigmaExporterError):
    status_code = 400


class InputValidationError(FigmaExporterError):
    status_code = 400


class UpstreamError(FigmaExporterError):
    status_code = 502


class NotFoundError(FigmaExporterError):
    status_code = 404


class FeatureUnavailableError(FigmaExporterError):
    status_code = 503
