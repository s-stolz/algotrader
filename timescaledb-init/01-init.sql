-- Create the database
CREATE DATABASE finance_data;

-- Connect to the newly created database
\c finance_data;

-- Create the extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Adjust user privileges as necessary
