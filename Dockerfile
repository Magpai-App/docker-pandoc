# syntax=docker/dockerfile:1

ARG BASE_IMAGE_PREFIX=
ARG BASE_IMAGE_NAME=python
ARG BASE_IMAGE_TAG=3.12-slim-bookworm

FROM ${BASE_IMAGE_PREFIX}${BASE_IMAGE_NAME}:${BASE_IMAGE_TAG}

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y \
        curl \
        texlive \
        texlive-luatex \
        texlive-xetex \
        texlive-fonts-recommended \
        texlive-fonts-extra \
        latexmk \
        wkhtmltopdf \
        weasyprint \
        librsvg2-bin \
    ;
RUN texhash \
    ;


ARG PANDOC_VERSION=3.2.1
ENV PANDOC_VERSION=${PANDOC_VERSION}
RUN curl \
        -fsSL \
        "https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/pandoc-${PANDOC_VERSION}-1-$(dpkg --print-architecture).deb" \
        -o /tmp/pandoc.deb \
    && dpkg -i /tmp/pandoc.deb \
    && rm /tmp/pandoc.deb \
    ;

WORKDIR /opt/bin
COPY server.py /opt/bin/server

WORKDIR /
COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT [ "/entrypoint.sh" ]
CMD [ "-H", "0.0.0.0", "-p", "8080" ]
