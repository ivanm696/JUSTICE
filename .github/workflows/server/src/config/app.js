// src/app.js
const express = require('express');
const morgan = require('morgan');
const cors = require('cors');

const routes = require('./routes');
const errorHandler = require('./middleware/errorHandler');

const app = express();

app.use(cors());
app.use(express.json());
app.use(morgan('dev'));

// API routes
app.use('/api', routes);

// Global error handler
app.use(errorHandler);

module.exports = app;
