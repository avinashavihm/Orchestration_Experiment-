#!/bin/bash
set -e

# Script to start both agents with port conflict handling

echo "======================================"
echo "Starting Clinical Operations Agents"
echo "======================================"
echo ""

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Check for port conflicts
echo "Checking port availability..."
if check_port 3002; then
    echo "⚠️  Warning: Port 3002 is already in use (Patient Recruitment Frontend)"
    echo "   Stopping existing container..."
    docker stop patient-recruitment-frontend 2>/dev/null || true
    docker rm patient-recruitment-frontend 2>/dev/null || true
fi

if check_port 3003; then
    echo "⚠️  Warning: Port 3003 is already in use (Clinical Supply Frontend)"
    echo "   Stopping existing container..."
    docker stop clin-supply-frontend 2>/dev/null || true
    docker rm clin-supply-frontend 2>/dev/null || true
fi

if check_port 8000; then
    echo "⚠️  Warning: Port 8000 is already in use (Patient Recruitment API)"
    echo "   Stopping existing container..."
    docker stop patient-recruitment-backend 2>/dev/null || true
fi

if check_port 8001; then
    echo "⚠️  Warning: Port 8001 is already in use (Clinical Supply API)"
    echo "   Stopping existing container..."
    docker stop clin-supply-backend 2>/dev/null || true
fi

if check_port 4001; then
    echo "⚠️  Warning: Port 4001 is already in use (Patient Recruitment MCP)"
fi

if check_port 4002; then
    echo "⚠️  Warning: Port 4002 is already in use (Clinical Supply MCP)"
fi

echo ""
echo "Starting Patient Recruitment Agent..."
cd Patient-Recruitment
docker-compose up -d --build
cd ..

echo ""
echo "Waiting 5 seconds for services to start..."
sleep 5

echo ""
echo "Starting Clinical Supply Agent..."
cd CLINICAL-SUPPLY
docker-compose up -d --build
cd ..

echo ""
echo "Starting Planner Agent..."
cd Planner-Agent
docker-compose up -d --build
cd ..

echo ""
echo "======================================"
echo "Services Started!"
echo "======================================"
echo ""
echo "Patient Recruitment Agent:"
echo "  - API:      http://localhost:8000"
echo "  - MCP:      ws://localhost:4001"
echo "  - Frontend: http://localhost:3002"
echo ""
echo "Clinical Supply Agent:"
echo "  - API:      http://localhost:8001"
echo "  - MCP:      ws://localhost:4002"
echo "  - Frontend: http://localhost:3003"
echo ""
echo "Planner Agent:"
echo "  - API:      http://localhost:8002"
echo "  - MCP:      ws://localhost:4003"
echo "  - Frontend: http://localhost:3004"
echo ""
echo "View logs:"
echo "  docker logs -f patient-recruitment-backend"
echo "  docker logs -f clin-supply-backend"
echo "  docker logs -f planner-agent-backend"
echo ""
echo "Test A2A Integration:"
echo "  docker exec -it patient-recruitment-backend python call_supply_agent.py"
echo "  docker exec -it clin-supply-backend python call_recruitment_agent.py"

