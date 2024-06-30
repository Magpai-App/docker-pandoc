# syntax=docker/dockerfile:1

ARG BASE_IMAGE_PREFIX=
ARG BASE_IMAGE_NAME=debian
ARG BASE_IMAGE_TAG=bookworm-slim

FROM ${BASE_IMAGE_PREFIX}${BASE_IMAGE_NAME}:${BASE_IMAGE_TAG} AS builder

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y \
        build-essential \
        curl \
        libffi-dev \
        libffi8 \
        libgmp-dev \
        libgmp10 \
        libncurses-dev \
        libncurses5 \
        libtinfo5 \
        zlib1g-dev \
    ;

RUN curl --proto '=https' --tlsv1.2 -sSf https://get-ghcup.haskell.org | \
    BOOTSTRAP_HASKELL_NONINTERACTIVE=1 \
    BOOTSTRAP_HASKELL_GHC_VERSION=9.6 \
    BOOTSTRAP_HASKELL_CABAL_VERSION=latest \
    BOOTSTRAP_HASKELL_INSTALL_STACK=0 \
    BOOTSTRAP_HASKELL_INSTALL_HLS=0 \
    BOOTSTRAP_HASKELL_ADJUST_BASHRC=P \
    bash

SHELL ["/bin/bash", "-c"]
WORKDIR /src/pandoc

ARG PANDOC_VERSION=3.2.1
ADD https://github.com/jgm/pandoc/archive/refs/tags/${PANDOC_VERSION}.tar.gz /src/pandoc.tar.gz
RUN tar -xzf ../pandoc.tar.gz --strip-components=1
RUN source ~/.ghcup/env \
    && cabal update \
    && cabal configure \
        --prefix=/opt \
        --flags="embed_data_files lua server" \
    && cabal build \
        pandoc-cli \
    && cabal install \
        --installdir=/opt/bin \
        --install-method=copy \
        pandoc-cli \
    ;

FROM ${BASE_IMAGE_PREFIX}${BASE_IMAGE_NAME}:${BASE_IMAGE_TAG}

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y \
        libgmp10 \
    ;

COPY --from=builder /opt /opt

ENTRYPOINT [ "/opt/bin/pandoc" ]
CMD [ "--help" ]
