FROM python:3.12.11-bookworm@sha256:13c9584604a99ca134c4f41800f74ffc64ee6ac8cf555cf1e704a6087fc84f12

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY source/ /opt/source-archives/
RUN echo "76134adb5a9c942e94f6757664c2c9d008608dfe6cf5cdab94ed8c0c175c8fff  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "458c50a70bf21fafecb8bebd934748b5986219e143a56baeaaa5e4905db22b81  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/donor-source \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /testbed --strip-components=1 \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/donor-source \
    && test "$(find /testbed -type f -o -type l | wc -l)" -eq 581 \
    && test "$(find /opt/donor-source/CCMpred -type f -o -type l | wc -l)" -eq 57

COPY --chmod=0755 task-tools/ /opt/task-tools/
COPY --chmod=0644 public-examples/ /examples/
COPY --chmod=0644 source-lock.json /opt/task-source-lock.json

WORKDIR /testbed
