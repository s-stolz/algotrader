import psycopg2
from psycopg2 import sql
from decouple import config
import logging
import traceback
import pandas as pd

log = logging.getLogger(__name__)

class Database:
    connection = None  # Class-level connection

    @staticmethod
    def connect():
        """
        Connect to the PostgreSQL database.
        """
        if Database.connection is None:
            try:
                Database.connection = psycopg2.connect(
                    host=config('POSTGRES_HOST'),
                    port=config('POSTGRES_PORT'),
                    database='finance_data',
                    user=config('POSTGRES_USER'),
                    password=config('POSTGRES_PASSWORD')
                )
                log.info("Connected to the database successfully!")
            except (Exception, psycopg2.Error) as error:
                log.error("Error while connecting to PostgreSQL:", error)
                traceback.print_exc()

    @staticmethod
    def disconnect():
        """
        Disconnect from the PostgreSQL database.
        """
        if Database.connection:
            Database.connection.close()
            Database.connection = None
            log.info("Disconnected from the database.")

    @staticmethod
    def market_exists(symbol: str, exchange: str) -> bool:
        Database.connect()
        cursor = Database.connection.cursor()

        cursor.execute(
            """
            SELECT * FROM markets
            WHERE symbol = %s AND exchange = %s;
            """,
            (symbol, exchange)
        )
        market = cursor.fetchone()
        cursor.close()

        return bool(market)

    @staticmethod
    def insert_market(symbol: str, exchange: str, market_type: str, min_move: float):
        Database.connect()

        if Database.market_exists(symbol, exchange):
            log.warning("Market already exists in the database!")
            return
        
        cursor = Database.connection.cursor()

        cursor.execute(
            """
            INSERT INTO markets (symbol, exchange, market_type, min_move)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (symbol_id) DO NOTHING;
            """,
            (symbol, exchange, market_type, min_move)
        )
        Database.connection.commit()
        cursor.close()
        log.info("Market inserted into PostgreSQL database!")

    @staticmethod
    def get_symbol(symbol_id: int) -> tuple[str, str]:
        Database.connect()
        cursor = Database.connection.cursor()

        query = sql.SQL(
            """
            SELECT symbol, exchange FROM markets
            WHERE symbol_id = %s;
            """
        )
        cursor.execute(query, (str(symbol_id),))
        symbols = cursor.fetchone()
        cursor.close()

        return symbols

    @staticmethod
    def get_symbol_id(symbol, exchange='%') -> int:
        Database.connect()
        cursor = Database.connection.cursor()

        query = sql.SQL(
            """
            SELECT symbol_id FROM markets
            WHERE symbol = %s AND exchange LIKE %s;
            """
        )
        cursor.execute(query, (symbol, exchange))
        symbol_id = cursor.fetchall()
        cursor.close()

        if len(symbol_id) == 0:
            return None
        
        if len(symbol_id) > 1:
            log.warning("Multiple symbol_ids found! Returning the first one.", symbol_id)

        return symbol_id[0][0]

    @staticmethod
    def insert_candles(df: pd.DataFrame, symbol: str, exchange: str = '%'):
        Database.connect()
        symbol_id = Database.get_symbol_id(symbol, exchange)
        if not symbol_id:
            log.warning(f"Symbol {symbol} not found in the database!")
            return
        
        try:
            cursor = Database.connection.cursor()
            insert_query = sql.SQL(
                """
                INSERT INTO candles (symbol_id, timestamp, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol_id, timestamp) DO NOTHING;
                """
            )

            for index, row in df.iterrows():
                cursor.execute(
                    insert_query,
                    (symbol_id, index, row["open"], row["high"], row["low"], row["close"], row["volume"])
                )

            Database.connection.commit()
            cursor.close()
        
        except psycopg2.DatabaseError as error:
            log.error("Database Error", error)
            traceback.print_exc()
            if Database.connection:
                Database.connection.rollback()
                log.info("Transaction rolled back!")

    @staticmethod
    def get_candles(symbol_id: int, timeframe: int, start_date: str = None, end_date: str = None) -> list:
        Database.connect()
        
        try:
            cursor = Database.connection.cursor()
            query = sql.SQL(
                """
                WITH RoundedCandles AS (
                    SELECT
                        date_trunc('day', timestamp) + INTERVAL '1 minute' * (
                            ((EXTRACT(HOUR FROM timestamp)::integer * 60) + EXTRACT(MINUTE FROM timestamp)::integer) - 
                            ((EXTRACT(HOUR FROM timestamp)::integer * 60 + EXTRACT(MINUTE FROM timestamp)::integer) %% %s)
                        ) AS rounded_timestamp,
                        open,
                        high,
                        low,
                        close,
                        volume,
                        ROW_NUMBER() OVER (
                            PARTITION BY symbol_id, date_trunc('day', timestamp) + INTERVAL '1 minute' * (
                                ((EXTRACT(HOUR FROM timestamp)::integer * 60) + EXTRACT(MINUTE FROM timestamp)::integer) - 
                                ((EXTRACT(HOUR FROM timestamp)::integer * 60 + EXTRACT(MINUTE FROM timestamp)::integer) %% %s)
                            )
                            ORDER BY timestamp ASC
                        ) AS rn_asc,
                        ROW_NUMBER() OVER (
                            PARTITION BY symbol_id, date_trunc('day', timestamp) + INTERVAL '1 minute' * (
                                ((EXTRACT(HOUR FROM timestamp)::integer * 60) + EXTRACT(MINUTE FROM timestamp)::integer) - 
                                ((EXTRACT(HOUR FROM timestamp)::integer * 60 + EXTRACT(MINUTE FROM timestamp)::integer) %% %s)
                            )
                            ORDER BY timestamp DESC
                        ) AS rn_desc
                    FROM candles
                    WHERE symbol_id = %s
                    AND (timestamp >= %s OR %s IS NULL)
                    AND (timestamp <= %s OR %s IS NULL)
                )
                SELECT
                    rounded_timestamp AS timestamp,
                    MAX(open) FILTER (WHERE rn_asc = 1) AS open,
                    MAX(high) AS high,
                    MIN(low) AS low,
                    MAX(close) FILTER (WHERE rn_desc = 1) AS close,
                    SUM(volume) AS volume
                FROM RoundedCandles
                GROUP BY timestamp
                ORDER BY timestamp;
                """
            )

            cursor.execute(
                query,
                (timeframe, timeframe, timeframe, symbol_id, start_date, start_date, end_date, end_date)
            )

            candles = cursor.fetchall()
            cursor.close()

            return candles

        except psycopg2.DatabaseError as error:
            log.error("Database Error", error)
            traceback.print_exc()
