# Frontend Dockerfile - Multi-stage Build
FROM node:22-alpine AS builder

WORKDIR /app

# Copy dependency configuration
COPY package.json package-lock.json ./

# Install dependencies including devDependencies (needed to build TypeScript)
RUN npm ci

# Copy configuration files and source code
COPY app/ ./app/
COPY components/ ./components/
COPY lib/ ./lib/
COPY public/ ./public/
COPY tsconfig.json next.config.ts eslint.config.mjs ./

# Build-time environment variable so Next.js hardcodes the backend URL
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Build the production Next.js package
RUN npm run build

# --- Runtime Stage ---
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Copy necessary production artifacts from the builder stage with correct ownership
COPY --from=builder --chown=node:node /app/package.json /app/package-lock.json ./
COPY --from=builder --chown=node:node /app/.next ./.next
COPY --from=builder --chown=node:node /app/public ./public
COPY --from=builder --chown=node:node /app/node_modules ./node_modules

USER node

EXPOSE 3000

# Start production server
CMD ["npm", "run", "start"]
