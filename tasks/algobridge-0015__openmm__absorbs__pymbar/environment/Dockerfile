FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --find-links=/opt/wheels \
      numpy==2.3.2 scipy==1.16.1 numexpr==2.14.1 openmm==8.5.2

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN echo "dfbb5c7b115dc5f5c96358561773a5ed6595f3fc5ff9aed16e06a7682a1b111d  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "d0e815a1bc88912cb0cb9c64bdb2ffc75eaec6f5225e79bd016acd5cbcf60a17  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/pristine-host /opt/pymbar-source \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /testbed \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/pymbar-source \
    && rm -rf /opt/source-archives
COPY task-tools/ /opt/task-tools/
COPY public-examples/ /examples/

RUN chmod 0755 /opt/task-tools/run-public-examples /examples/verify_examples.py \
    && chown -R root:root /opt/pristine-host /opt/pymbar-source /opt/task-tools /examples \
    && chmod -R go-w /opt/pristine-host /opt/pymbar-source /opt/task-tools /examples

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed
