# Stage 1: React build
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# Stage 2: Caddy serves dist/ + proxies /v1 to the API + automatic HTTPS
FROM caddy:2.8-alpine
COPY --from=build /app/dist /srv
# "deploy" = compose ka additional build context (repo root ka deploy/ folder)
COPY --from=deploy Caddyfile /etc/caddy/Caddyfile
