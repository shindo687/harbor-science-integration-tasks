FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --find-links=/opt/wheels \
      scanpy==1.14.0.dev21+gfabadb941 pytest==8.4.1 pooch==1.8.2 \
    && python -m pip install --no-index --no-deps \
      /opt/wheels/scvelo-0.3.3+locked.f63c0e7-py3-none-any.whl

COPY host-source/ /testbed/
COPY host-source/ /opt/pristine-host/
COPY donor-source/ /opt/scvelo-source/
COPY task-tools/ /opt/task-tools/
COPY public-examples/ /examples/
COPY host-source.sha256 donor-source.sha256 /opt/task-locks/

RUN python /opt/task-tools/copy_installed_scanpy.py \
    && chmod 0755 /opt/task-tools/materialize_candidate.py \
      /opt/task-tools/run-public-examples /examples/verify_examples.py \
    && chmod -R go-w /opt/pristine-host /opt/installed-scanpy \
      /opt/scvelo-source /opt/task-tools /opt/task-locks /examples

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
ENV MPLBACKEND=Agg
WORKDIR /testbed
