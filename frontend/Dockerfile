# ── Stage 1: dev ──────────────────────────────────────────────────────────────
# Used by docker-compose for local development with hot-reload
FROM node:lts-alpine AS dev

WORKDIR /app

# Copy package manifests for layer caching
COPY package.json package-lock.json* ./

# Install all dependencies (including devDependencies for ng serve / ng build)
RUN npm ci

# Copy source (overridden at runtime by bind mount in docker-compose)
COPY . .

EXPOSE 4200

# --poll 500 enables file-change detection across Docker bind mounts on all OSes
CMD ["npx", "ng", "serve", "--host", "0.0.0.0", "--port", "4200", "--poll", "500", "--disable-host-check"]


# ── Stage 2: production build ─────────────────────────────────────────────────
# Build target: docker build --target prod -t options-tracker-frontend:latest .
FROM node:lts-alpine AS prod

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --omit=dev

COPY . .

RUN npx ng build --configuration production

# Serve with a lightweight static server
RUN npm install -g serve

EXPOSE 4200

CMD ["serve", "-s", "dist/frontend", "-l", "4200"]
