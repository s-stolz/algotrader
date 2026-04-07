import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main() -> None:
    """Main entry point for the backtester."""
    logging.info("Backtester started.")


if __name__ == "__main__":
    main()
