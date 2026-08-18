# Build de production : `next dev` recompile chaque page a la demande, ce qui
# rend la navigation lente. `next build` compile une fois, `next start` sert
# des pages deja pretes.
FROM node:22-alpine
WORKDIR /app

COPY package.json ./
RUN npm install

# Les variables NEXT_PUBLIC_* sont inlinees dans le bundle AU MOMENT DU BUILD :
# elles doivent donc arriver en arguments de build, pas seulement a l'execution.
ARG NEXT_PUBLIC_API_URL=http://localhost:8090
ARG NEXT_PUBLIC_DEV_USER_ID=11111111-1111-1111-1111-111111111111
ARG NEXT_PUBLIC_SUPABASE_URL=
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_DEV_USER_ID=$NEXT_PUBLIC_DEV_USER_ID \
    NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY

COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
