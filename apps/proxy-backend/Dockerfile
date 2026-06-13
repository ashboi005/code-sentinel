# syntax=docker/dockerfile:1.7

FROM oven/bun:1.3.10-alpine AS base
WORKDIR /app

FROM base AS deps
COPY package.json bun.lock ./
COPY apps/proxy-backend/package.json apps/proxy-backend/package.json
RUN bun install --frozen-lockfile

FROM base AS runner
ENV NODE_ENV=production
ENV PORT=8787

COPY --from=deps /app/node_modules ./node_modules
COPY package.json bun.lock ./
COPY apps/proxy-backend/package.json apps/proxy-backend/package.json
COPY apps/proxy-backend/src ./apps/proxy-backend/src

EXPOSE 8787
CMD ["bun", "run", "--cwd", "apps/proxy-backend", "start"]
