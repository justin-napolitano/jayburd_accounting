FROM alpine:3.20
RUN apk add --no-cache ca-certificates curl bash tzdata docker-cli docker-compose
# supercronic (static binary)
ADD https://github.com/aptible/supercronic/releases/download/v0.2.29/supercronic-linux-amd64 /usr/local/bin/supercronic
RUN chmod +x /usr/local/bin/supercronic
WORKDIR /app
COPY crontab /app/crontab
ENV TZ=${TZ:-America/New_York}
CMD ["/usr/local/bin/supercronic", "-json", "/app/crontab"]
