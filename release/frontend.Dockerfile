FROM node:26.13.0-bookworm AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_WS_URL=/ws
RUN npm run build

FROM nginx:1.28-alpine
COPY release/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
