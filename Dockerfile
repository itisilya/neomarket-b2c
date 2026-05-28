# Stage 1: Build the React Application
FROM node:22-slim AS build-stage

WORKDIR /app

COPY package*.json ./

# Use standard npm install to be robust and bypass package-lock.json mismatch failures
RUN npm install

COPY . .

# Build production assets inside /app/dist
RUN npx vite build

# Stage 2: Serve using Nginx
FROM nginx:alpine

# Copy custom Nginx proxy and routing config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy build files from build stage to Nginx web root
COPY --from=build-stage /app/dist /usr/share/nginx/html

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
