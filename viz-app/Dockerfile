# Knowledge Graph Visualizer - Multi-stage Docker Build
#
# This Dockerfile will be referenced from the main docker-compose.yml
# when the viz-app service is added (similar to how postgres uses apache/age image)
#
# Runtime environment variables (no rebuild required):
#   - VITE_API_URL
#   - VITE_OAUTH_CLIENT_ID
#   - VITE_OAUTH_REDIRECT_URI
#   - VITE_APP_NAME
#
# The app uses runtime configuration (config.js) instead of build-time env vars,
# enabling CDN deployment and Docker deployment with the same build artifacts.

# Stage 1: Build the Vite React app
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the app (no env vars needed - uses runtime config.js)
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

# Copy built static files from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration for SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy entrypoint script that generates config.js from env vars
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose port 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

# Entrypoint generates config.js, then starts nginx
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
