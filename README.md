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
2. Create local secrets from the example:
   ```sh
   cp config/.env.secrets.example config/.env.secrets.local
   ```
3. Generate the root `.env` from the tracked topology + local secrets:
   ```sh
   python scripts/generate_env.py
   ```
4. Edit `config/topology.yaml` for shared non-secret settings (ports, hosts, tuning), and edit `config/.env.secrets.local` for credentials/secrets.
5. Run the project and explore.

## Running with Docker Compose

Default workflow (auto-regenerates `.env` before Compose):
   ```sh
   make up
   ```

Direct Docker Compose usage:
   ```sh
   python scripts/generate_env.py --force
   docker compose up --build
   ```
This will build and start all necessary services as defined in the `docker-compose.yml` file.

## Central Configuration Model

- Tracked shared topology: `config/topology.yaml`
- Gitignored secrets: `config/.env.secrets.local`
- Generated runtime env files: `config/.env.shared`, `config/.env.secrets.db`, `config/.env.secrets.runtime`, `config/.env.secrets.broker`
- Generator script: `scripts/generate_env.py`

### Validation and overwrite

```sh
python scripts/generate_env.py --validate
python scripts/generate_env.py --force
```

### Make targets

```sh
make config
make validate-config
make up
make build
make down
make restart
make logs
make ps
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

This project makes use of third-party software so please check the [ATTRIBUTIONS.md](ATTRIBUTIONS.md) file for more information.
