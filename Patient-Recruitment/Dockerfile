# Backend Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
# Note: app/ includes all services including a2a_integration.py
COPY app/ ./app/
COPY main.py .
COPY server_recruitment.py .
COPY call_supply_agent.py .

# Create directories for uploads and outputs
RUN mkdir -p /app/data/uploads /app/data/outputs

# Expose ports (API and MCP server)
EXPOSE 8000 4001

# Run both API and MCP server using a startup script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

CMD ["/docker-entrypoint.sh"]

