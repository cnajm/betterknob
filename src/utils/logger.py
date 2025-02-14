import sys

from loguru import logger as loguru_logger

# Initialize with default settings immediately
loguru_logger.remove()  # Remove default handler
loguru_logger.add(
    sink=sys.stdout,
    colorize=True,
    format="[{time:HH:mm:ss}] <level>{level}: {message}</level>",
    level="INFO",
)


# loguru doesn't support changing log level at runtime
# after loading settings, we recreate the logger instead
# https://github.com/Delgan/loguru/issues/138
def setup_logger(debug=False):
    """Configure logger with debug settings if needed."""
    loguru_logger.remove()  # Clear existing handlers

    # Add console handler
    loguru_logger.add(
        sink=sys.stdout,
        colorize=True,
        format="[{time:HH:mm:ss}] <level>{level}: {message}</level>",
        level="DEBUG" if debug else "INFO",
    )

    # Add file handler for debug mode
    if debug:
        loguru_logger.add(
            sink="debug.log",
            format="{time} <level>{level}: {message}</level>",
            level="DEBUG",
            rotation="1 day",
        )


# Export the logger directly
logger = loguru_logger
