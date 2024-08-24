const express = require('express');
const bodyParser = require('body-parser');
const websocket = require('./app/utils/websocket.js')

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