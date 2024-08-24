const data = require('../controllers/data.server.controller.js');

module.exports = function(app) {
    app.get('/api/candles/:symbolID/:timeframe', data.getCandles);
    app.get('/api/markets', data.getMarkets);
    app.put('/api/markets', data.insertMarket);
};