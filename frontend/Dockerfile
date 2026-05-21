# =============================================================================
# DataLens — React/Vite frontend image
# Targets:
#   dev   — Vite dev server with HMR (default for compose; mounts source)
#   build — produces static assets
#   prod  — nginx-alpine serving built assets (use for production)
# =============================================================================

ARG NODE_VERSION=22-alpine3.23
ARG NGINX_VERSION=1.27-alpine

# ---- deps (shared cache layer) ----------------------------------------------
FROM node:${NODE_VERSION} AS deps
WORKDIR /app
ENV NODE_ENV=development \
    CI=true
COPY package.json package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm \
    if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; \
    else npm install --no-audit --no-fund; fi

# ---- dev (compose default) --------------------------------------------------
FROM node:${NODE_VERSION} AS dev
WORKDIR /app
ENV NODE_ENV=development
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN addgroup -S app && adduser -S -G app app \
 && chown -R app:app /app
USER app
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ---- build ------------------------------------------------------------------
FROM node:${NODE_VERSION} AS build
WORKDIR /app
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---- prod (nginx serving static assets) -------------------------------------
FROM nginx:${NGINX_VERSION} AS prod
RUN rm -rf /usr/share/nginx/html/* /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
RUN printf 'server {\n  listen 3000;\n  root /usr/share/nginx/html;\n  index index.html;\n  location / { try_files $uri /index.html; }\n}\n' \
    > /etc/nginx/conf.d/app.conf
USER nginx
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:3000/ >/dev/null 2>&1 || exit 1
