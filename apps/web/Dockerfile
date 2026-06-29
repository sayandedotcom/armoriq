FROM node:20-alpine

WORKDIR /app

COPY apps/web/package.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install

COPY apps/web/src ./src
COPY apps/web/public ./public
COPY apps/web/next.config.js .
COPY apps/web/tailwind.config.js .
COPY apps/web/postcss.config.js .
COPY packages/shared-types ./packages/shared-types

RUN pnpm build

EXPOSE 3000

CMD ["pnpm", "start"]
