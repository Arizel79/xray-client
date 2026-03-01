from src.core.config import ConfigManager
from src.core.binary_manager import BinaryManager
from src.core.process_manager import ProcessManager
from src.core.subscription import SubscriptionManager

class BaseService:
    """Base service that holds all managers."""
    def __init__(self):
        self.config_mgr = ConfigManager()
        self.binary_mgr = BinaryManager()
        self.process_mgr = ProcessManager()
        self.sub_mgr = SubscriptionManager()