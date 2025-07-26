import threading
import logging
from websocket_client import WebSocketClient

logging.basicConfig(level=logging.INFO, format="%(threadName)s: %(message)s")


def main():
    """Main entry point for the backtester."""
    client = WebSocketClient()

    client_thread = threading.Thread(
        target=client.run_in_thread,
        name="WebSocketThread",
    )
    client_thread.start()
    client_thread.join()
    logging.info("Exiting main thread")


if __name__ == "__main__":
    main()
