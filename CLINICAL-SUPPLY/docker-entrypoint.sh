#!/bin/bash
set -e

# Function to handle shutdown
cleanup() {
    echo "Shutting down services..."
    kill $API_PID $MCP_PID 2>/dev/null || true
    wait
    exit 0
}

trap cleanup SIGTERM SIGINT

# Start API server in background
echo "Starting Clinical Supply API server on port 8000..."
# Increase limit for large file uploads (50MB for CSV files)
# --limit-concurrency: max concurrent requests
# --timeout-keep-alive: keep-alive timeout (15 minutes for long processing)
# --timeout-graceful-shutdown: graceful shutdown timeout
uvicorn app.api:app --host 0.0.0.0 --port 8000 --limit-concurrency 1000 --timeout-keep-alive 900 --timeout-graceful-shutdown 30 &
API_PID=$!

# Wait a moment for API to start
sleep 3

# Start MCP server in background
echo "Starting Clinical Supply MCP server on port 4002..."
python server_supply.py &
MCP_PID=$!

# Wait for both processes
wait $API_PID $MCP_PID

