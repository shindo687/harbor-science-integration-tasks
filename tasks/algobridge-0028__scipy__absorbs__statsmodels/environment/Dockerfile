FROM python:3.12.11-slim-bookworm

COPY system-debs/ /opt/system-debs/
RUN cd /opt/system-debs \
    && sha256sum --check --strict SHA256SUMS \
    && dpkg -i ./*.deb \
    && rm -rf /opt/system-debs

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --find-links=/opt/wheels \
      numpy pytest hypothesis \
    && python -m pip install --no-index --no-deps \
      /opt/wheels/scipy-2.0.0.dev0-*.whl

COPY host-source/ /testbed/
COPY host-source/ /opt/pristine-host/
COPY donor-source/ /opt/statsmodels-source/
COPY task-tools/ /opt/task-tools/
COPY public-examples/ /examples/

RUN python /opt/task-tools/install_host_extensions.py \
    && chmod 0755 /opt/task-tools/materialize_candidate.py \
      /opt/task-tools/run-public-examples

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed

