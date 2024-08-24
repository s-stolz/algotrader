const psqlClient = require("../models/data.server.model.js");

async function marketExists(symbol, exchange) {
    const query = "SELECT * FROM markets WHERE symbol = $1 AND exchange = $2";
    const values = [symbol, exchange];
    const result = await psqlClient.query(query, values);
  return result.rows.length > 0;
}

exports.insertMarket = function (req, res) {
    if (!req.body.symbol || !req.body.exchange) {
        res.status(400).send({error: "Missing required fields"});
        return;
    }
    if (marketExists(req.body.symbol, req.body.exchange)) {
        res.status(400).send({error: "Market already exists"});
        return;
    }

    const market = req.body;
    const query = "INSERT INTO markets (symbol, exchange, market_type, min_move) VALUES ($1, $2) RETURNING *";
    const values = [market.name, market.symbol];
    psqlClient.query(query, values, (err, result) => {
        if (err) {
            console.log(err);
            res.status(500).send;
        }
        res.status(201).json(result.rows[0]);
    });
}

exports.getMarkets = function (req, res) {
    const query = "SELECT * FROM markets";
    psqlClient.query(query, (err, result) => {
        if (err) {
            console.log(err);
            res.status(500).send;
        }
        res.status(200).json(result.rows);
    });
};

exports.getCandles = async function (req, res) {
    const symbolID = req.params.symbolID;
    const timeframe = req.params.timeframe;
    
    const query = `
    WITH RoundedCandles AS (
        SELECT
          symbol_id,
          date_trunc('minute', timestamp) - INTERVAL '1 minute' * (EXTRACT(MINUTE FROM timestamp)::integer % $2) AS rounded_timestamp,
          open,
          high,
          low,
          close,
          volume,
          ROW_NUMBER() OVER(PARTITION BY symbol_id, date_trunc('minute', timestamp) - INTERVAL '1 minute' * (EXTRACT(MINUTE FROM timestamp)::integer % $2) ORDER BY timestamp ASC) AS rn_asc,
          ROW_NUMBER() OVER(PARTITION BY symbol_id, date_trunc('minute', timestamp) - INTERVAL '1 minute' * (EXTRACT(MINUTE FROM timestamp)::integer % $2) ORDER BY timestamp DESC) AS rn_desc
        FROM candles
        WHERE symbol_id = $1
      )
      SELECT
        symbol_id,
        rounded_timestamp AS timestamp,
        MAX(open) FILTER (WHERE rn_asc = 1) AS open,
        MAX(high) AS high,
        MIN(low) AS low,
        MAX(close) FILTER (WHERE rn_desc = 1) AS close,
        SUM(volume) AS volume
      FROM RoundedCandles
      GROUP BY symbol_id, timestamp
      ORDER BY timestamp;
    `;
    const result = await psqlClient.query(query, [symbolID, timeframe]);

    res.json(result.rows);
};
