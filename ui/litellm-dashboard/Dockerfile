FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy frontend code
COPY . .

# Build and run
RUN npm run build
EXPOSE 3000

CMD ["npm", "start"]
