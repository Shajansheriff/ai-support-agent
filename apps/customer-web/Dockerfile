FROM node:22-alpine
WORKDIR /app
COPY apps/customer-web/package*.json ./
RUN npm ci
COPY apps/customer-web/ ./
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 CMD ["node", "-e", "fetch('http://127.0.0.1:3000').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
CMD ["npm", "run", "dev"]
