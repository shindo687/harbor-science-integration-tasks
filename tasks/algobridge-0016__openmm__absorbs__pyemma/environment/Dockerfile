FROM python@sha256:ee0c7d26e2dba416773cb51c042496e9cffacc872459f57726935dd6833f2d96

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --find-links=/opt/wheels \
      numpy==2.2.6 scipy==1.15.3 openmm==8.5.2

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN echo "dfbb5c7b115dc5f5c96358561773a5ed6595f3fc5ff9aed16e06a7682a1b111d  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "acc2045d9be27621069cdb549aa4a6f6531a063eb9027c583c13786cd276677a  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/pristine-host /opt/reference-pyemma-source \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /testbed \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz \
       -C /opt/reference-pyemma-source --strip-components=1 \
    && rm -rf /opt/source-archives

COPY task-tools/ /opt/task-tools/
COPY public-examples/ /examples/
RUN chmod 0755 /opt/task-tools/run-public-examples /examples/verify_examples.py \
    && chown -R root:root /opt/pristine-host /opt/reference-pyemma-source \
      /opt/task-tools /examples \
    && chmod -R go-w /opt/pristine-host /opt/reference-pyemma-source \
      /opt/task-tools /examples

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed

