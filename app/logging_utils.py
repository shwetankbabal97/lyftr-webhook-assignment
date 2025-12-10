import logging
import json
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    """
    Custom formatter to output logs as JSON lines.
    """
    def format(self, record):
        # Basic log data
        log_obj = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        if hasattr(record, "extra_data"):
            log_obj.update(record.extra_data)

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)

def setup_logging(level: str = "INFO"):
    """
    Configures the root logger to use our JSON Formatter.
    """
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Create a handler that writes to Console (Standard Output)
    handler = logging.StreamHandler()
    
    # Attach our JSON Formatter to the handler
    formatter = JSONFormatter()
    handler.setFormatter(formatter)

    # Clear existing handlers (to avoid duplicate logs) and add ours
    logger.handlers = []
    logger.addHandler(handler)