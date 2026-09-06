FROM ubuntu:22.04

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y wine64 curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV WINEDEBUG=-all WINEPREFIX=/root/.wine

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
