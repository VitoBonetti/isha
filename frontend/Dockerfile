# Build Stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# 1. Catch the argument passed from docker-compose.prod.yml
ARG VITE_GITHUB_CLIENT_ID

# 2. Set it as an environment variable so Vite can use it during the build
ENV VITE_GITHUB_CLIENT_ID=$VITE_GITHUB_CLIENT_ID

# 3. Build the app (Vite will now bake the ID into the frontend code)
RUN npm run build

# Production Serving Stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]