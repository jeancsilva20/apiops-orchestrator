import uuid
import logging
import json
import threading
import sys
import os
import time
from datetime import datetime, timezone
from contextlib import contextmanager

from apiops_orchestrator.infrastructure.observability.logging_level_enum import Level
from apiops_orchestrator.infrastructure.observability.logging_status_enum import Status

# Stores data that is local (private) to each thread.
_log_context = threading.local()

def setup_logging():
    """
    Configures the root logger to use JSON format. This function should be called ONLY ONCE at the application's entry point (e.g., main.py).
    """
    # Reads the log level from an environment variable, defaults to 'INFO'
    # For using DEBUG, define the variable as follows: LOG_LEVEL=DEBUG
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format_type = os.environ.get("LOG_FORMAT", "BOTH").upper()

    logger = logging.getLogger()

    # Prevents duplicate logs if this function is accidentally called more than once
    if logger.hasHandlers():
        logger.handlers.clear()

    try:
        logger.setLevel(log_level)
    except ValueError:
        logger.setLevel(logging.INFO)
        sys.stderr.write(f"Warning: LOG_LEVEL '{log_level}' invalid. Using INFO.\n")

    context_filter = ContextFilter()

    ## Configuration for console handler
    if log_format_type in ["SIMPLE", "BOTH"]:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.addFilter(context_filter)
        console_handler.setFormatter(SimpleFormatter())
        logger.addHandler(console_handler)

    if log_format_type in ["FILE", "BOTH"]:
        setup_file_handler(logger, context_filter)

def setup_file_handler(logger, context_filter):
    """Helper for configuration of FileHandler."""
    log_dir = 'logs'
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError as e:
        # When environment is readonly, do not fail app only warns with stderr
        sys.stderr.write(f"ERROR: Unable to create log folder '{log_dir}'. File logging disabled. Error: {e}\n")
        raise OSError("Unable to create log folder")

    timestamp_str = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')
    filename = os.path.join(log_dir, f".{timestamp_str}.ndjson")

    try:
        file_handler = logging.FileHandler(filename, mode='a', encoding='utf-8')
        file_handler.addFilter(context_filter)
        file_handler.setFormatter(JsonFormatter())
        logger.addHandler(file_handler)
    except IOError as e:
        sys.stderr.write(f"ERROR: Unable to create log file '{filename}'. Error: {e}\n")
        raise IOError(f"Unable to create log folder. Error: {e}")

class ContextFilter(logging.Filter):
    """
    Observability filter to automatically inject the 'trace_id' into each log record (LogRecord).
    """
    def filter(self, record):
        """
        Attaches the data to the log's 'record' object.
        """
        record.trace_id = getattr(_log_context, 'trace_id', None)
        record.api_id = getattr(_log_context, 'api_id', None)
        record.customer = getattr(_log_context, 'customer', None)
        record.span_id = getattr(_log_context, 'span_id', None)
        record.duration = getattr(_log_context, 'duration', None)
        record.status = getattr(_log_context, 'status', Status("IN PROGRESS").value)
        return True

class JsonFormatter(logging.Formatter):
    """
    Custom observability formatter to generate logs in JSON format.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Converts a LogRecord into a JSON string."""
        duration_val = getattr(record, "duration", None)
        status_val = getattr(record, "status", Status("IN PROGRESS").value)
        api_id_val = getattr(record, "api_id", None)
        customer_val = getattr(record, "customer", None)

        log_record = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            "trace_id": record.trace_id,
            "level": Level(record.levelname.upper()).value,
            "service": record.name,
            "message": record.getMessage(),
            "duration": duration_val,
            "status": status_val,
            "context":{
                "api_id": api_id_val,
                "customer": customer_val,
                "span_id": record.span_id
            },
            "importador":{
                "exemploCase": record.example_case
            }
        }

        # Add exception traceback, if any
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        elif record.stack_info:
            log_record['stack_info'] = self.formatStack(record.stack_info)
        return json.dumps(log_record, ensure_ascii=False, default=str)

class SimpleFormatter(logging.Formatter):
    """
    Custom formatter to generate simple, human-readable string logs.
    Example: [2025-11-14 10:30:00] WARN: {message} - [trace_id=123]
    """
    # ANSI Colors
    GREY = "\x1b[38;21m"
    BLUE = "\x1b[34;21m"
    GREEN = "\x1b[32;21m"
    YELLOW = "\x1b[33;21m"
    RED = "\x1b[31;21m"
    BOLD_RED = "\x1b[38;5;88;21m"
    RESET = "\x1b[0m"
    RED_BG = "\x1b[41;97;1m"

    def format(self, record: logging.LogRecord) -> str:
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        colors = {
            Level.DEBUG.value: self.BLUE,
            Level.INFO.value: self.GREEN,
            Level.WARN.value: self.YELLOW,
            Level.ERROR.value: self.RED,
            Level.FATAL.value: self.RED_BG
        }

        timestamp_str = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        level = Level(record.levelname.upper()).value
        color = colors.get(level, self.GREY)

        trace_id = getattr(record, 'trace_id', None)
        message = record.getMessage()
        duration = record.duration
        # Add exception data, if it exists
        if record.exc_info and log_level == "DEBUG":
             message += "\n" + self.formatException(record.exc_info)

        # Final format: [TIMESTAMP] LEVEL:[context] Message
        return f"[{timestamp_str}] {color}{level}{self.RESET}: {message} - [trace_id={trace_id}]"

@contextmanager
def log_duration(operation_name: str, extra_data: dict = None):
    """
    Context manager to log the execution time of a code block.
    Example:
    with log_duration("process_payment"):
        do_payment_stuff()
    """
    start_time = time.perf_counter()
    _log_context.duration = None

    try:
        yield
    finally:
        end_time = time.perf_counter()
        duration = (end_time - start_time) * 1000  # Conversion to miliseconds
        _log_context.duration = round(duration, 2)
        logger = logging.getLogger()
        #This line cannot be deleted, it´s needed for context use
        logger.info(f"Execution of {operation_name} finished in {_log_context.duration}ms")
        _log_context.duration = None

def set_span_id():
    _log_context.span_id = uuid.uuid4()

def set_status(status: str):
    _log_context.status = Status(status).value

def set_default_data():
    _log_context.trace_id = uuid.uuid4()

def set_api_info(api_id: int, customer: str):
    _log_context.api_id = api_id
    _log_context.customer = customer

def clear_operation_context():
    """
        Clears span id and status from thread context
    """
    vars_to_clear = ['span_id', 'status']
    for var in vars_to_clear:
        if hasattr(_log_context, var):
            delattr(_log_context, var)

def clear_context():
    """
    Clears all thread context
    """
    vars_to_clear = ['trace_id', 'api_id', 'customer', 'duration']
    for var in vars_to_clear:
        if hasattr(_log_context, var):
            delattr(_log_context, var)




