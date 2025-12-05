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
echo "Starting Patient Recruitment API server on port 8000..."
# Increase limit for large file uploads (100MB for PDF + Excel files)
# --limit-concurrency: max concurrent requests
# --timeout-keep-alive: keep-alive timeout (15 minutes for long LLM processing)
# --timeout-graceful-shutdown: graceful shutdown timeout
uvicorn app.main:app --host 0.0.0.0 --port 8000 --limit-concurrency 1000 --timeout-keep-alive 900 --timeout-graceful-shutdown 30 &
API_PID=$!

# Wait a moment for API to start
sleep 3

# Start MCP server in background
echo "Starting Patient Recruitment MCP server on port 4001..."
python server_recruitment.py &
MCP_PID=$!

# Wait for both processes
wait $API_PID $MCP_PID

