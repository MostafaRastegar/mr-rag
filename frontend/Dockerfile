# Multi-stage Next.js build for standalone output
FROM docker.arvancloud.ir/node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN npm install --frozen-lockfile

FROM docker.arvancloud.ir/node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_BASE=http://localhost:8080
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
RUN npm run build

FROM docker.arvancloud.ir/node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_PUBLIC_API_BASE=http://localhost:8080
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
