FROM node:20.11 AS build
WORKDIR /app


RUN mkdir -p /app/backend
RUN mkdir -p /app/frontend
WORKDIR /app/backend

COPY package*.json ./
RUN npm install
RUN npm install -g nodemon

COPY . .

# Copy wait-for-it.sh script to the image
COPY wait-for-it.sh ./wait-for-it.sh
RUN chmod +x ./wait-for-it.sh

# Copy and set the entrypoint script
COPY ./entrypoint-backend.sh /entrypoint-backend.sh
RUN chmod +x /entrypoint-backend.sh
ENTRYPOINT ["/entrypoint-backend.sh"]