# Next 16 exige Node >= 20.9 ; l'image epingle la version pour que
# `docker compose up --build` fonctionne quelle que soit la machine.
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev"]
