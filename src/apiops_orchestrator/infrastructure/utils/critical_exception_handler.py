import logging
import sys
import traceback

logger = logging.getLogger(__name__)

def critical_exception_handler(exc_type, exc_value, exc_traceback):

    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical(f"Critical Error: {exc_type} - {exc_value}",exc_info=(exc_type, exc_value, exc_traceback))

    traceback.print_exception(exc_type, exc_value, exc_traceback)

    logging.shutdown()

    sys.exit(1)