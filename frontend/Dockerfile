FROM node:20-bookworm AS build
WORKDIR /app/frontend

COPY package*.json ./
RUN npm ci --include=dev \
  && sha256sum package.json package-lock.json > node_modules/.algotrader-deps-checksum
COPY . .

# Copy and set the entrypoint script
COPY ./entrypoint-frontend.sh /entrypoint-frontend.sh
RUN chmod +x /entrypoint-frontend.sh
ENTRYPOINT ["/entrypoint-frontend.sh"]
