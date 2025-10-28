# Knowledge Graph Visualization Server
# Status: TODO - Not yet implemented
#
# Multi-stage build for React/Vue frontend + Nginx
#

# Build stage
FROM node:18-alpine as builder

WORKDIR /app

# Copy package files
COPY visualization/package*.json ./
RUN npm ci

# Copy source and build
COPY visualization/ .
RUN npm run build

# Runtime stage
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY build/docker/nginx.conf /etc/nginx/conf.d/default.conf

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD wget -q -O /dev/null http://localhost/ || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
