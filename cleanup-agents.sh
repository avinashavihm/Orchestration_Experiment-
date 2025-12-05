#!/bin/bash
# Cleanup script for Clinical Operations Agents
# Stops and removes all Docker containers, networks, and cleans up files

set -e

echo "======================================"
echo "Cleaning Up Clinical Operations Agents"
echo "======================================"
echo ""

# Stop and remove containers
echo "Stopping and removing Docker containers..."
docker ps -a | grep -E "patient-recruitment|clin-supply" | awk '{print $1}' | xargs -r docker stop 2>/dev/null || true
docker ps -a | grep -E "patient-recruitment|clin-supply" | awk '{print $1}' | xargs -r docker rm 2>/dev/null || true

# Remove Docker images (optional, comment out if you want to keep images)
# echo "Removing Docker images..."
# docker rmi patient-recruitment-backend patient-recruitment-frontend 2>/dev/null || true
# docker rmi clin-supply-backend clin-supply-frontend 2>/dev/null || true

# Clean up networks
echo "Cleaning up Docker networks..."
docker network prune -f

# Clean up volumes (optional, comment out if you want to keep data)
# echo "Cleaning up Docker volumes..."
# docker volume prune -f

# Clean up Python cache files
echo "Cleaning up Python cache files..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# Clean up system files
echo "Cleaning up system files..."
find . -type f -name ".DS_Store" -delete 2>/dev/null || true

# Clean up log files
echo "Cleaning up log files..."
find . -type f -name "*.log" -delete 2>/dev/null || true

# Clean up build artifacts
echo "Cleaning up build artifacts..."
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true

echo ""
echo "======================================"
echo "Cleanup Complete!"
echo "======================================"
echo ""
echo "To restart the agents, run:"
echo "  ./start-agents.sh"
echo ""

