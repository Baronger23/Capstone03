FROM --platform=$BUILDPLATFORM docker.io/library/golang:1.26.5-bookworm@sha256:1ecb7edf62a0408027bd5729dfd6b1b8766e578e8df93995b225dfd0944eb651 AS grafana-builder

ARG TARGETOS
ARG TARGETARCH
ARG GRAFANA_SOURCE_COMMIT=5d189285069d02af604bfaeedb21a0b6ec4c4d0a
ARG GRAFANA_BUILD_NUMBER=30056490933

WORKDIR /src
RUN git init \
    && git remote add origin https://github.com/grafana/grafana.git \
    && git fetch --depth 1 origin "${GRAFANA_SOURCE_COMMIT}" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${GRAFANA_SOURCE_COMMIT}"
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go get github.com/getkin/kin-openapi@v0.144.0 \
    && CGO_ENABLED=0 make build-go \
      OS="${TARGETOS}" \
      ARCH="${TARGETARCH}" \
      GO_BUILD_TAGS=oss \
      WIRE_TAGS=oss \
      COMMIT_SHA="${GRAFANA_SOURCE_COMMIT}" \
      BUILD_BRANCH=main \
      BUILD_NUMBER="${GRAFANA_BUILD_NUMBER}"

FROM --platform=$BUILDPLATFORM docker.io/library/golang:1.26.5-bookworm@sha256:1ecb7edf62a0408027bd5729dfd6b1b8766e578e8df93995b225dfd0944eb651 AS opensearch-plugin-builder

ARG TARGETOS
ARG TARGETARCH
ARG OPENSEARCH_PLUGIN_COMMIT=188f6f20d488f771808eff476e8647dccb901dad

WORKDIR /src
RUN git init \
    && git remote add origin https://github.com/grafana/opensearch-datasource.git \
    && git fetch --depth 1 origin "${OPENSEARCH_PLUGIN_COMMIT}" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${OPENSEARCH_PLUGIN_COMMIT}"
COPY src/grafana/patches/opensearch-grpc-1.82.1.patch /tmp/opensearch-grpc-1.82.1.patch
RUN test \
      "$(sha256sum /tmp/opensearch-grpc-1.82.1.patch | cut -d' ' -f1)" \
      = "940f564bba915faa6762cba49eed07599bd70c9677fc8702143f9a98dce60091" \
    && git apply --check /tmp/opensearch-grpc-1.82.1.patch \
    && git apply /tmp/opensearch-grpc-1.82.1.patch \
    && test "$(git diff --name-only)" = "$(printf 'go.mod\ngo.sum')" \
    && git diff --check \
    && grep -Fq 'google.golang.org/grpc v1.82.1' go.mod
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go mod download \
    && go mod verify \
    && CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -trimpath -buildvcs=false -ldflags="-s -w" \
      -o "/out/gpx_opensearch-datasource_linux_${TARGETARCH}" ./pkg

FROM --platform=$BUILDPLATFORM docker.io/library/busybox:1.37.0-musl@sha256:222ad6d973c0d198014546a65cd02c5fdedcc172123c5b4c2bf0af636550bd94 AS opensearch-plugin-archive

ARG TARGETARCH

ADD --checksum=sha256:fcd1bedfccde21ca224139bf409170c194a9a34cdda2f8756b8427b6775ca611 \
    https://storage.googleapis.com/grafana-plugins-catalog/grafana-opensearch-datasource/release/2.34.0/grafana-opensearch-datasource-2.34.0.linux-amd64.zip \
    /tmp/plugin-amd64.zip
ADD --checksum=sha256:8c644c95b3ac39dedf8254cc99d3921b136fe06895f5a8aeb17cfa0a709e7da6 \
    https://storage.googleapis.com/grafana-plugins-catalog/grafana-opensearch-datasource/release/2.34.0/grafana-opensearch-datasource-2.34.0.linux-arm64.zip \
    /tmp/plugin-arm64.zip

RUN case "${TARGETARCH}" in amd64|arm64) ;; *) exit 1 ;; esac \
    && unzip -q "/tmp/plugin-${TARGETARCH}.zip" -d /out \
    && test -f /out/grafana-opensearch-datasource/plugin.json \
    && grep -Fq '"id": "grafana-opensearch-datasource"' \
      /out/grafana-opensearch-datasource/plugin.json \
    && grep -Fq '"version": "2.34.0"' \
      /out/grafana-opensearch-datasource/plugin.json \
    && grep -Fq '"grafanaDependency": ">=10.4.0-0"' \
      /out/grafana-opensearch-datasource/plugin.json \
    && test -f /out/grafana-opensearch-datasource/MANIFEST.txt \
    && test -x \
      "/out/grafana-opensearch-datasource/gpx_opensearch-datasource_linux_${TARGETARCH}"

FROM docker.io/grafana/grafana:nightly-ubuntu-slim@sha256:7dcef0c66bc3692de69155ed9e229fee733c85e520207dcda26e1f52479dcb30

ARG GRAFANA_PLUGIN_VERSION=2.34.0
ARG TARGETARCH
ARG OPENSEARCH_PLUGIN_COMMIT=188f6f20d488f771808eff476e8647dccb901dad
ENV GF_PATHS_PLUGINS=/opt/grafana/plugins

USER root

COPY --from=opensearch-plugin-archive \
    /out/grafana-opensearch-datasource \
    /tmp/verified-opensearch-plugin

RUN install -d -o 472 -g 0 -m 0755 "${GF_PATHS_PLUGINS}" \
    && grafana cli --pluginsDir "${GF_PATHS_PLUGINS}" plugins install \
      grafana-opensearch-datasource "${GRAFANA_PLUGIN_VERSION}" \
    && test -f "${GF_PATHS_PLUGINS}/grafana-opensearch-datasource/plugin.json" \
    && grep -Fq '"id": "grafana-opensearch-datasource"' \
      "${GF_PATHS_PLUGINS}/grafana-opensearch-datasource/plugin.json" \
    && grep -Fq "\"version\": \"${GRAFANA_PLUGIN_VERSION}\"" \
      "${GF_PATHS_PLUGINS}/grafana-opensearch-datasource/plugin.json" \
    && test -f \
      "${GF_PATHS_PLUGINS}/grafana-opensearch-datasource/MANIFEST.txt" \
    && test -x \
      "${GF_PATHS_PLUGINS}/grafana-opensearch-datasource/gpx_opensearch-datasource_linux_${TARGETARCH}" \
    && diff -qr \
      /tmp/verified-opensearch-plugin \
      "${GF_PATHS_PLUGINS}/grafana-opensearch-datasource" \
    && rm -rf /tmp/verified-opensearch-plugin

COPY --from=grafana-builder \
    "/src/bin/linux/${TARGETARCH}/grafana" \
    "/usr/share/grafana/bin/grafana"
COPY --from=opensearch-plugin-builder \
    "/out/gpx_opensearch-datasource_linux_${TARGETARCH}" \
    "${GF_PATHS_PLUGINS}/grafana-opensearch-datasource/gpx_opensearch-datasource_linux_${TARGETARCH}"

RUN test -x "/usr/share/grafana/bin/grafana" \
    && test -x \
      "${GF_PATHS_PLUGINS}/grafana-opensearch-datasource/gpx_opensearch-datasource_linux_${TARGETARCH}" \
    && rm "${GF_PATHS_PLUGINS}/grafana-opensearch-datasource/MANIFEST.txt" \
    && test ! -e \
      "${GF_PATHS_PLUGINS}/grafana-opensearch-datasource/MANIFEST.txt" \
    && case "${TARGETARCH}" in \
      amd64) archive_sha256=fcd1bedfccde21ca224139bf409170c194a9a34cdda2f8756b8427b6775ca611 ;; \
      arm64) archive_sha256=8c644c95b3ac39dedf8254cc99d3921b136fe06895f5a8aeb17cfa0a709e7da6 ;; \
      *) exit 1 ;; \
    esac \
    && printf '%s\n' \
      "plugin_id=grafana-opensearch-datasource" \
      "plugin_version=${GRAFANA_PLUGIN_VERSION}" \
      "upstream_commit=${OPENSEARCH_PLUGIN_COMMIT}" \
      "upstream_archive_sha256=${archive_sha256}" \
      "go_version=1.26.5" \
      "grpc_version=1.82.1" \
      "trust_model=tf3-derived-unsigned" \
      > "${GF_PATHS_PLUGINS}/grafana-opensearch-datasource/TF3-PROVENANCE" \
    && chown root:0 "/usr/share/grafana/bin/grafana" \
    && chmod a-w "/usr/share/grafana/bin/grafana" \
    && chown -R root:0 "${GF_PATHS_PLUGINS}" \
    && chmod -R a-w "${GF_PATHS_PLUGINS}"

USER 472
