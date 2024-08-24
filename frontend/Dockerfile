FROM node:20.11 AS build
WORKDIR /app

COPY package*.json ./
RUN npm install
COPY . .

# Copy and set the entrypoint script
COPY ./entrypoint-frontend.sh /entrypoint-frontend.sh
RUN chmod +x /entrypoint-frontend.sh
ENTRYPOINT ["/entrypoint-frontend.sh"]