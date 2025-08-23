# AlgoTrader

AlgoTrader is an experimental trading project that uses the [Lightweight Charts](https://tradingview.github.io/lightweight-charts/) library to visualize historical market data.

## Development Disclaimer

This project is in active development and may undergo significant changes. **Backward compatibility is not guaranteed**—things might break! Please use this repository **for reference only** and not as a stable library.

## Trading Risk Disclaimer

Trading in derivative instruments—including futures, options, CFDs, Forex, and
certificates—carries significant risk and may not be appropriate for all
investors. There is a possibility of losing the entire initial investment or even more. **Use this project at your own risk.**

## Support the Project

If AlgoTrader has helped you with your algorithmic trading journey, you can support its continued development by using my [IC Trading affiliate link](https://www.ictrading.com?camp=86158) when opening a trading account. IC Trading offers competitive spreads and reliable execution for algorithmic traders.

[![IC Trading](https://www.ictrading.com/assets/svgs/ICT-white.svg)](https://www.ictrading.com?camp=86158)

*Using this link costs you nothing extra but helps fund the development of new features and improvements.*

## Prerequisites
- [Docker](https://docs.docker.com/get-started/get-docker/) installed on your machine.

Note: Historical market data currently needs to be manually inserted into the database. This is a temporary solution until a more automated data ingestion process is implemented.

## Getting Started

1. Clone the repository:
   ```sh
   git clone https://github.com/iamProud/algotrader.git
   cd algotrader
   ```
2. Rename the environment files and adjust parameters:
   ```sh
   mv backend/sample.env backend/.env
   mv backtester/sample.env backtester/.env
   mv database-accessor-api/sample.env database-accessor-api/.env
   ```
   Edit the `.env` files to set up the necessary configurations.
3. Run the project and explore!  

## Running with Docker Compose

To start the project using Docker Compose, navigate to the project directory and run:
   ```sh
   docker compose up --build
   ```
This will build and start all necessary services as defined in the `docker-compose.yml` file.