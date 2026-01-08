import logging
import sys
import json
from datetime import datetime
from decimal import Decimal

class CustomJsonEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle special types like datetime and Decimal.
    """
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "pathname": record.pathname,
            "lineno": record.lineno,
            "funcName": record.funcName,
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            log_record["stack_info"] = self.formatStack(record.stack_info)
        
        # Add custom fields passed via `extra={'extra_fields': {...}}`
        custom_extra_fields = record.__dict__.get('extra_fields')
        if custom_extra_fields:
            log_record.update(custom_extra_fields)

        return json.dumps(log_record, cls=CustomJsonEncoder)

def setup_logging():
    log_level = logging.INFO

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Set formatter
    formatter = JsonFormatter()
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    # Prevent root logger from adding its own handlers which might duplicate messages
    logger.propagate = False
