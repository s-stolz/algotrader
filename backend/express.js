const express = require('express');
const bodyParser = require('body-parser');
const wss = require('./app/utils/websocketserver.js')

module.exports = function() {
    const path =__dirname + '/../frontend/dist';
    const app = express();

    const server = require('http').createServer(app);

    app.use(express.static(path));
    app.use(bodyParser.json());
    app.use(bodyParser.urlencoded({ extended: true }));

    require('./app/routes/data.server.route.js')(app);

    return server;
};