"""Framework-independent product forecasting domain."""

from .models import ForecastRequest, ForecastResult, ProductSelectionRequest, ProductSpec

__all__ = ["ForecastRequest", "ForecastResult", "ProductSelectionRequest", "ProductSpec"]
