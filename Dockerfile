FROM debian:bookworm-slim AS dwg-builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates build-essential autoconf automake libtool pkg-config \
    gettext texinfo flex bison python3 libxml2-dev zlib1g-dev libreadline-dev libplot-dev \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 https://github.com/LibreDWG/libredwg.git /tmp/libredwg \
    && cd /tmp/libredwg \
    && ./autogen.sh \
    && ./configure --enable-release --disable-bindings --disable-docs --disable-write --disable-json \
    && make -j2 \
    && make install DESTDIR=/opt/libredwg-root

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=dwg-builder /opt/libredwg-root/usr/local/bin/dwg2dxf /usr/local/bin/dwg2dxf
COPY --from=dwg-builder /opt/libredwg-root/usr/local/lib/ /usr/local/lib/
RUN ldconfig
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer libreoffice-calc libreoffice-impress qpdf \
    fonts-dejavu-core fontconfig libgl1 libglib2.0-0 libxml2 libreadline8 zlib1g libplot2c2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port \"$PORT\""]
