# finance-web/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}

# copy manifests first for better caching
COPY package.json ./
# if you have a package-lock.json later, copy it too:
# COPY package-lock.json ./

RUN npm install --no-audit --no-fund

# now copy the rest and build
COPY . .
RUN npm run build

# runtime
FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/package.json ./package.json
RUN npm i next --no-audit --no-fund
EXPOSE 3020
CMD ["npx","next","start","-p","3020"]
