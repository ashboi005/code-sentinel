# syntax=docker/dockerfile:1.7

FROM oven/bun:1.3.10-alpine

WORKDIR /app

COPY package.json bun.lock ./
COPY apps/proxy-backend/package.json apps/proxy-backend/package.json
RUN bun install --frozen-lockfile

COPY . .

ENV NODE_ENV=production
ENV PORT=8787

EXPOSE 8787

CMD ["bun", "--cwd", "apps/proxy-backend", "src/index.ts"]
