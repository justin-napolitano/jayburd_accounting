FROM postgres:16
WORKDIR /app
COPY backup.sh /app/backup.sh
RUN chmod +x /app/backup.sh
ENV TZ=${TZ:-America/New_York}
CMD ["/app/backup.sh"]
