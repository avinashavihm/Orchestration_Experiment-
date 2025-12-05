FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
# Note: app/ includes a2a_integration.py for A2A integration with Recruitment agent
COPY app/ ./app/
COPY server_supply.py .
COPY call_recruitment_agent.py .

# Create data and upload directories with proper permissions
RUN mkdir -p /app/data /tmp/uploads && \
    chmod -R 755 /app/data /tmp/uploads

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /tmp/uploads

# Copy and set permissions for entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh && \
    chown appuser:appuser /docker-entrypoint.sh

USER appuser

# Expose ports (API and MCP server)
EXPOSE 8000 4002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use entrypoint script to run both API and MCP server
CMD ["/docker-entrypoint.sh"]

