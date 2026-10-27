FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Static files served by nginx, which also reverse-proxies /api to the backend (same origin, no CORS).
FROM nginx:1.27-alpine
ENV NGINX_RESOLVER=127.0.0.11 API_UPSTREAM=api:8000
# The official image renders /etc/nginx/templates/*.template with env vars at startup.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
