import logging
import signal
import sys
import time

import keyboard

logging.basicConfig(level=logging.INFO)  # Hide debug logs from other modules
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

running = True


def handle_volume_keys(event):
    global running
    logger.info(f"Key: {event.name}, Scan: {event.scan_code}, Event type: {event.event_type}")
    if event.event_type == "down" and event.name == "esc":
        running = False
    return True


def cleanup():
    global running
    if running:  # Prevent duplicate cleanup
        running = False
        try:
            keyboard.unhook_all()
        except Exception as e:
            logger.info(f"Cleanup error: {e}")


def signal_handler(signum, frame):
    logger.info("Force exit, cleaning up...")
    cleanup()
    sys.exit(0)


def main():
    global running
    signal.signal(signal.SIGINT, signal_handler)

    try:
        keyboard.hook(handle_volume_keys, suppress=True)
        logger.info("Press any key to see its code. Press 'esc' to exit.")

        while running:
            time.sleep(0.1)  # Sleep to reduce CPU usage

    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        keyboard.unhook_all()
        cleanup()


if __name__ == "__main__":
    main()
