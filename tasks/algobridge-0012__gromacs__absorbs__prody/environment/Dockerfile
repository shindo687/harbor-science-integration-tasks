FROM python@sha256:ee0c7d26e2dba416773cb51c042496e9cffacc872459f57726935dd6833f2d96

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --no-deps --find-links=/opt/wheels \
      numpy==1.24.3

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN echo "d9c09e9f2338d87e8bd7d6546d819194a305880a909479552398bf55c42f56bb  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "07ba18e9fbddba5ab43e450c7182809c0a222e3b4bc15048c32d6e38435bf01f  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/pristine-host /opt/reference-prody-source \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /testbed \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz \
       -C /opt/reference-prody-source --strip-components=1 \
    && rm -rf /opt/source-archives \
    && chown -R root:root /opt/pristine-host /opt/reference-prody-source \
    && chmod -R go-w /opt/pristine-host /opt/reference-prody-source

COPY public-examples/ /examples/
COPY task-tools/ /opt/task-tools/
RUN chmod 0755 /examples/verify_examples.py /opt/task-tools/run-public-examples \
    && chown -R root:root /examples /opt/task-tools \
    && chmod -R go-w /examples /opt/task-tools

ENV PYTHONNOUSERSITE=1
ENV PYTHONPATH=/testbed/python_packaging/gmxapi/src
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed
