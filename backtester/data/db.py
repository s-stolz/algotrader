import psycopg2
from psycopg2 import sql
from decouple import config
import logging
import traceback
import pandas as pd

log = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.host = config('POSTGRES_HOST')
        self.port = config('POSTGRES_PORT')
        self.database = 'finance_data'
        self.user = config('POSTGRES_USER')
        self.password = config('POSTGRES_PASSWORD')
        self.connection = None
        self.connect()

    def connect(self) -> None:
        """
        Connect to the PostgreSQL database.
        """

        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            log.info("Connected to the database successfully!")
        except (Exception, psycopg2.Error) as error:
            log.error("Error while connecting to PostgreSQL:", error)
            traceback.print_exc()

    def disconnect(self) -> None:
        """
        Disconnect from the PostgreSQL database.
        """

        if self.connection:
            self.connection.close()
            log.info("Disconnected from the database.")

    def market_exists(self, symbol: str, exchange: str) -> bool:
        """
        Check if the market already exists in the database.

        Parameters:
            symbol (str): Symbol name.
            exchange (str): Exchange name.

        Returns:
            bool: True if the market exists, False otherwise.
        """

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT * FROM markets
            WHERE symbol = %s AND exchange = %s;
            """,
            (symbol, exchange)
        )
        market = cursor.fetchone()

        if market:
            return True
        else:
            return False
        
    def insert_market(self, symbol: str, exchange: str, market_type: str, min_move: float) -> None:
        """
        Insert a market into the database.

        Parameters:
            symbol (str): Symbol name.
            exchange (str): Exchange name.
            market_type (str): Market type.
            min_move (float): Minimum move.

        Returns:
            None
        """

        if self.market_exists(symbol, exchange):
            log.warning("Market already exists in the database!")
            return
        
        cursor = self.connection.cursor()

        cursor.execute(
            """
            INSERT INTO markets (symbol, exchange, market_type, min_move)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (symbol_id) DO NOTHING;
            """,
            (symbol, exchange, market_type, min_move)
        )
        self.connection.commit()
        log.info("Market inserted into PostgreSQL database!")

    def get_symbol(self, symbol_id: int) -> tuple[str, str]:
        """
        Get the symbol and exchange from the database.

        Parameters:
            symbol_id (int): Symbol ID.

        Returns:
            tuple: Symbol and exchange.
        """

        cursor = self.connection.cursor()
        query = sql.SQL(
            """
            SELECT symbol, exchange FROM markets
            WHERE symbol_id = %s;
            """
        )

        cursor.execute(
            query,
            (str(symbol_id),)
        )

        symbols = cursor.fetchone()

        return symbols
    
    def get_symbol_id(self, symbol, exchange='%') -> int:
        """
        Get the symbol_id from the database.

        Parameters:
            symbol (str): Symbol name.
            exchange (str): Exchange name.

        Returns:
            int: The symbol_id from the database.
        """
        cursor = self.connection.cursor()
        query = sql.SQL(
            """
            SELECT symbol_id FROM markets
            WHERE symbol = %s AND exchange LIKE %s;
            """
        )

        cursor.execute(
            query,
            (symbol, exchange)
        )

        symbol_id = cursor.fetchall()

        if len(symbol_id) == 0:
            return None
        
        if len(symbol_id) > 1:
            log.warning("Multiple symbol_ids found! Returning the first one.", symbol_id)

        return symbol_id[0][0]
        
    def insert_candles(self, df: pd.DataFrame, symbol: str, exchange: str = '%') -> None:
        """
        Insert candle data into the database.

        Parameters:
            df (pd.DataFrame): OHLCV data for the symbol.
            symbol (str): Symbol name.
            exchange (str): Exchange name.

        Returns:
            None
        """

        symbol_id = self.get_symbol_id(symbol, exchange)
        if not symbol_id:
            log.warning(f"Symbol {symbol} not found in the database!")
            return
        
        try:
            cursor = self.connection.cursor()

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

            self.connection.commit()
        
        except psycopg2.DatabaseError as error:
            log.error("Database Error", error)
            traceback.print_exc()
            if self.connection:
                self.connection.rollback()
                log.info("Transaction rolled back!")

        except Exception as error:
            log.error("Error", error)
            traceback.print_exc()

        finally:
            if cursor:
                cursor.close()

    def get_candles(self, symbol_id: int, timeframe: int, start_date: str = None, end_date: str = None) -> list:
        """
        Get candle data from the database.

        Parameters:
            symbol_id (int): Symbol ID.
            timeframe (int): Timeframe in minutes.
            start_date (str): Start date in 'YYYY-MM-DD' format.
            end_date (str): End date in 'YYYY-MM-DD' format.

        Returns:
            list: List of candles.
        """

        try:
            cursor = self.connection.cursor()
            
            # SQL query with conditional date filters
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

            # Execute the query with the timeframe, symbol_id, start_date, and end_date parameters
            cursor.execute(
                query,
                (timeframe, timeframe, timeframe, symbol_id, start_date, start_date, end_date, end_date)
            )

            candles = cursor.fetchall()

            return candles

        except psycopg2.DatabaseError as error:
            log.error("Database Error", error)
            traceback.print_exc()

        finally:
            if cursor:
                cursor.close()
