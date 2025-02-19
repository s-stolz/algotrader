# AlgoTrader

AlgoTrader is an experimental trading project that uses the [Lightweight Charts](https://tradingview.github.io/lightweight-charts/) library to visualize historical market data.

## Disclaimer

This project is in active development and may undergo significant changes. **Backward compatibility is not guaranteed**—things might break! Please use this repository **for reference only** and not as a stable library.

## Follow the Development

I'm sharing the development process on YouTube! Check it out here:

[Trading Nerd on YouTube](https://youtube.com/playlist?list=PLaqitSpR8hexOLbvtjkdOt_FRcu2mmwY1&si=ygHgsfvDMnBwl8rV)

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
   ```
   Edit the `.env` files to set up the necessary configurations.
3. Run the project and explore!  

## Running with Docker Compose

To start the project using Docker Compose, navigate to the project directory and run:
   ```sh
   docker compose up --build
   ```
This will build and start all necessary services as defined in the `docker-compose.yml` file.