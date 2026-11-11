FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Public build-time settings for hosted Supabase; empty means same-origin /auth/v1.
ARG VITE_SUPABASE_URL=""
ARG VITE_SUPABASE_ANON_KEY=""
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine
# Upstreams are substituted into the template at container start.
ENV API_UPSTREAM=http://api:8080 AUTH_UPSTREAM=http://auth:9999
COPY docker/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
