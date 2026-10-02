FROM node:22-alpine

WORKDIR /workspace/apps/web

COPY apps/web/package.json ./
RUN npm install --ignore-scripts

COPY apps/web ./
ENV NEXT_TELEMETRY_DISABLED=1
ENV TRADING_API_URL=http://api:8000
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
