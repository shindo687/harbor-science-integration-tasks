FROM python@sha256:ee0c7d26e2dba416773cb51c042496e9cffacc872459f57726935dd6833f2d96

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --find-links=/opt/wheels \
      numpy==1.24.3 scipy==1.15.3 biopython==1.79

COPY parser-compat/ /opt/parser-compat/
COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN echo "7b6900aa9cafb0bc14e0e6bf25b74faa67fa3133f3e3474f511279f6cf3fab59  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "07ba18e9fbddba5ab43e450c7182809c0a222e3b4bc15048c32d6e38435bf01f  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/pristine-host /opt/reference-prody-source \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /testbed \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz \
       -C /opt/reference-prody-source --strip-components=1 \
    && rm -rf /opt/source-archives

COPY task-tools/ /opt/task-tools/
COPY public-examples/ /examples/
RUN chmod 0755 /opt/task-tools/run-public-examples /examples/verify_examples.py \
    && chown -R root:root /opt/pristine-host /opt/reference-prody-source \
      /opt/parser-compat /opt/task-tools /examples \
    && chmod -R go-w /opt/pristine-host /opt/reference-prody-source \
      /opt/parser-compat /opt/task-tools /examples

ENV PYTHONNOUSERSITE=1
ENV PYTHONPATH=/opt/parser-compat:/testbed
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed

