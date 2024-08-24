require("dotenv").config();

const express = require('./express.js')

const app = express();

app.listen(8080, () => {
    console.log("Server is running on port 8080");
});