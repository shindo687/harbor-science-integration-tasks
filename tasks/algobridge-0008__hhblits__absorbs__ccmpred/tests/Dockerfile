FROM python:3.12.11-bookworm@sha256:13c9584604a99ca134c4f41800f74ffc64ee6ac8cf555cf1e704a6087fc84f12

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin candidate \
    && install -d -m 0700 /tests /opt/reference-ccmpred /opt/donor-source \
       /opt/pristine-host /opt/source-archives \
    && install -d -m 0755 /testbed

COPY --chmod=0400 source/ /opt/source-archives/
RUN echo "76134adb5a9c942e94f6757664c2c9d008608dfe6cf5cdab94ed8c0c175c8fff  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "458c50a70bf21fafecb8bebd934748b5986219e143a56baeaaa5e4905db22b81  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/donor-source \
    && test "$(find /opt/pristine-host/hh-suite -type f -o -type l | wc -l)" -eq 581 \
    && test "$(find /opt/donor-source/CCMpred -type f -o -type l | wc -l)" -eq 57 \
    && chmod 0400 /opt/source-archives/*.tar.gz

COPY --chmod=0700 reference-bin/ccmpred /opt/reference-ccmpred/ccmpred
COPY --chmod=0400 reference-bin/build-compatibility.patch /opt/reference-ccmpred/build-compatibility.patch
RUN /opt/reference-ccmpred/ccmpred -h | grep 'Usage:'

COPY --chmod=0400 source-lock.json /opt/task-source-lock.json
COPY --chmod=0700 cases.py candidate_runner.py reference_runner.py grader.py test.sh source-lock.json /tests/

WORKDIR /testbed
