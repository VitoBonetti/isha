# frontend/Dockerfile
FROM node:20-alpine

WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm install

# Copy the rest of the application
COPY . .

# Expose the Vite default port
EXPOSE 5173

# Start Vite, binding to all network interfaces so it's accessible outside the container
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]