FROM python:3.12.11-bookworm@sha256:13c9584604a99ca134c4f41800f74ffc64ee6ac8cf555cf1e704a6087fc84f12

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY source/ /opt/source-archives/
RUN echo "e9eeb0d1936a1459c69e077b454f0af8f4d63d311a48576a14209f4b792c76f7  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /testbed --strip-components=1 \
    && test "$(find /testbed \( -type f -o -type l \) | wc -l)" -eq 201

COPY --chmod=0755 task-tools/ /opt/task-tools/
COPY --chmod=0644 public-examples/ /examples/
COPY --chmod=0644 source-lock.json /opt/task-source-lock.json

WORKDIR /testbed
