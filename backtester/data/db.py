import psycopg2
from psycopg2 import sql
from decouple import config

class Database:
    def __init__(self):
        self.host = config('POSTGRES_HOST')
        self.port = config('POSTGRES_PORT')
        self.database = 'finance_data'
        self.user = config('POSTGRES_USER')
        self.password = config('POSTGRES_PASSWORD')
        self.connection = None
        self.connect()

    def connect(self):
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            print("Connected to the database successfully!")
        except (Exception, psycopg2.Error) as error:
            print("Error while connecting to PostgreSQL:", error)

    def disconnect(self):
        if self.connection:
            self.connection.close()
            print("Disconnected from the database.")

    def market_exists(self, symbol, exchange):
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
        
    def insert_market(self, symbol, exchange, market_type, min_move):
        if self.market_exists(symbol, exchange):
            print("Market already exists in the database!")
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
        print("Market inserted into PostgreSQL database!")
    
    def get_symbol_id(self, symbol, exchange='%'):
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
            print("WARNING: Multiple symbol_ids found! Returning the first one.")
            print(symbol_id)

        return symbol_id[0][0]
        
    def insert_candles(self, df, symbol, exchange):
        symbol_id = self.get_symbol_id(symbol, exchange)
        if not symbol_id:
            print(f"Symbol {symbol} not found in the database!")
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
            print(f"Error: {error}")
            if self.connection:
                self.connection.rollback()
                print("Transaction rolled back!")

        except Exception as error:
            print(f"Error: {error}")

        finally:
            if cursor:
                cursor.close()
                print("Cursor closed!")

