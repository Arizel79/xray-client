from src.services.base import BaseService
from src.services.mixins import ServerMixin, SubscriptionMixin, ProcessMixin, SettingsMixin


class XrayService(BaseService, ServerMixin, SubscriptionMixin, ProcessMixin, SettingsMixin):
    """Unified service for all xray-client operations."""
    pass