const {Client} = require('pg');

const client = new Client({
    host: process.env.POSTGRES_HOST || 'localhost',
    port: process.env.POSTGRES_PORT || 5432,
    database: 'finance_data',
    user: process.env.POSTGRES_USER,
    password: process.env.POSTGRES_PASSWORD
});

client.connect();

module.exports = client;