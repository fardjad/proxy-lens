FROM node:22-slim

WORKDIR /app

COPY package.json /app/package.json
RUN npm install

COPY app.js /app/app.js
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

EXPOSE 9443

ENTRYPOINT ["/app/entrypoint.sh"]
