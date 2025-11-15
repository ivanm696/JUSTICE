// routes/index.js
const express = require('express');
const authRoutes = require('./auth');
const userRoutes = require('./users');

const router = express.Router();

router.use('/auth', authRoutes);
router.use('/users', userRoutes);

module.exports = router;
