FROM python:3.12.11-slim-bookworm

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --find-links=/opt/wheels \
      scanpy==1.14.0.dev21+gfabadb941 pytest==8.4.1 pooch==1.8.2

COPY host-source/ /testbed/
COPY host-source/ /opt/pristine-host/
COPY donor-source/ /opt/scib-source/
COPY task-tools/ /opt/task-tools/
COPY public-examples/ /examples/

RUN python /opt/task-tools/copy_installed_scanpy.py \
    && chmod 0755 /opt/task-tools/materialize_candidate.py \
      /opt/task-tools/run-public-examples \
    && chmod -R go-w /opt/pristine-host /opt/installed-scanpy /opt/scib-source \
      /opt/task-tools /examples

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed
