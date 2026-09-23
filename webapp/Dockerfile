FROM node:20-slim AS build

LABEL org.opencontainers.image.source="https://github.com/infn-argus/argus-knowledge-hub"
LABEL org.opencontainers.image.description="ARGUS Knowledge Hub — operator and admin web UI"
LABEL org.opencontainers.image.licenses="INFN"

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
# Which identity provider the "INFN login" button talks to, and where the API is.
# Baked in at build time (this is a static bundle); left unset, the button is
# simply not offered, which is what the production build wants until it is told.
ARG VITE_OIDC_AUTHORITY
ARG VITE_OIDC_CLIENT_ID
ARG VITE_OIDC_LABEL
ARG VITE_API_BASE_URL
ENV VITE_OIDC_AUTHORITY=$VITE_OIDC_AUTHORITY \
    VITE_OIDC_CLIENT_ID=$VITE_OIDC_CLIENT_ID \
    VITE_OIDC_LABEL=$VITE_OIDC_LABEL \
    VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
