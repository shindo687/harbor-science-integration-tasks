FROM python:3.12.11-bookworm@sha256:13c9584604a99ca134c4f41800f74ffc64ee6ac8cf555cf1e704a6087fc84f12

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz donor-source.tar.gz source-lock.json /opt/task-inputs/
RUN echo "ef088b6b1730cf919de22ff61e93f8a34b8b87ddf322d89fc5483d31379aeea1  /opt/task-inputs/host-source.tar.gz" | sha256sum --check --strict \
    && echo "8e48a00ce32ec8c1c119b0e81fa63ef79b2f6e9b9564b829bf17147b1b561f27  /opt/task-inputs/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-host /opt/reference-mafft-source \
      /opt/reference-mafft-source/binaries /opt/reference-mafft-source/scripts \
      /opt/reference-tools/mafft \
    && tar -xzf /opt/task-inputs/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/task-inputs/donor-source.tar.gz -C /opt/reference-mafft-source \
    && gcc -O3 -std=c99 -o /opt/reference-tools/FastTree \
      /opt/pristine-host/FastTree.c -lm \
    && make -C /opt/reference-mafft-source/core -j"$(nproc)" \
      PREFIX=/opt/reference-tools/mafft \
    && make -C /opt/reference-mafft-source/core install \
      PREFIX=/opt/reference-tools/mafft \
    && /opt/reference-tools/mafft/bin/mafft --version \
    && /opt/reference-tools/FastTree -help >/dev/null 2>&1

COPY common.py cases.py guide_oracle.py reference_runner.py source_policy.py grader.py test.sh /tests/

RUN chmod 0755 /tests/test.sh /tests/grader.py /tests/reference_runner.py \
    && chown -R root:root /tests /opt/pristine-host /opt/reference-mafft-source \
      /opt/reference-tools /opt/task-inputs \
    && chmod -R go-w /tests /opt/pristine-host /opt/reference-mafft-source \
      /opt/reference-tools /opt/task-inputs \
    && chmod 0700 /tests /opt/pristine-host /opt/reference-mafft-source \
      /opt/reference-tools /opt/task-inputs

ENV PYTHONNOUSERSITE=1
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
WORKDIR /testbed
