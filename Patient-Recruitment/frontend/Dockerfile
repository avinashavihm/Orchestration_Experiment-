# Frontend Dockerfile - Multi-stage build
FROM node:20-alpine AS builder

# Set working directory
WORKDIR /app

# Accept build arguments
ARG VITE_API_URL=/api

# Set environment variable for build
ENV VITE_API_URL=$VITE_API_URL

# Copy package files
COPY package*.json ./

# Install dependencies
# Remove package-lock.json to work around npm bug with optional dependencies
# See: https://github.com/npm/cli/issues/4828
RUN rm -f package-lock.json && npm install

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage - serve with nginx
FROM nginx:alpine

# Copy built files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]

