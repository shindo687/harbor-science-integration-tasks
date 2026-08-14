FROM python:3.12.11-bookworm@sha256:13c9584604a99ca134c4f41800f74ffc64ee6ac8cf555cf1e704a6087fc84f12

COPY host-source.tar.gz donor-source.tar.gz source-lock.json /opt/task-inputs/
RUN echo "ef088b6b1730cf919de22ff61e93f8a34b8b87ddf322d89fc5483d31379aeea1  /opt/task-inputs/host-source.tar.gz" | sha256sum --check --strict \
    && echo "8e48a00ce32ec8c1c119b0e81fa63ef79b2f6e9b9564b829bf17147b1b561f27  /opt/task-inputs/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/mafft-source \
    && tar -xzf /opt/task-inputs/host-source.tar.gz -C /testbed \
    && tar -xzf /opt/task-inputs/donor-source.tar.gz -C /opt/mafft-source \
    && gcc -O3 -std=c99 -o /tmp/FastTree-pristine /testbed/FastTree.c -lm \
    && /tmp/FastTree-pristine -help >/dev/null 2>&1 \
    && rm /tmp/FastTree-pristine \
    && chown -R root:root /opt/mafft-source /opt/task-inputs \
    && chmod -R go-w /opt/mafft-source /opt/task-inputs

COPY public-examples/ /examples/
COPY task-tools/ /opt/task-tools/
RUN chmod 0755 /examples/verify_examples.py /opt/task-tools/run-public-examples \
    && chown -R root:root /examples /opt/task-tools \
    && chmod -R go-w /examples /opt/task-tools

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
WORKDIR /testbed
