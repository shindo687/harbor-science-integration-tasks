FROM python@sha256:13c9584604a99ca134c4f41800f74ffc64ee6ac8cf555cf1e704a6087fc84f12

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --no-deps --find-links=/opt/wheels \
      numpy==2.3.2 scipy==1.16.1 joblib==1.5.1 \
      threadpoolctl==3.6.0 narwhals==2.1.2 \
    && python -m pip install --no-index --no-deps \
      /opt/wheels/scikit_learn-1.10.dev0-cp312-cp312-linux_x86_64.whl

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN echo "5a07940f6efdf9dc79d92c625c46cf9b266ab47417bfee8f41dbf164f9ad9802  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "16540bd4551d0d0d521fef3399ace68499a654f21846d79056791707c476d70f  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/pristine-host /opt/reference-xgboost-source \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /testbed \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz \
      -C /opt/reference-xgboost-source --strip-components=1 \
    && rm -rf /opt/source-archives \
    && chown -R root:root /opt/pristine-host /opt/reference-xgboost-source \
    && chmod -R go-w /opt/pristine-host /opt/reference-xgboost-source

COPY task-tools/ /opt/task-tools/
COPY public-examples/ /examples/
RUN python /opt/task-tools/install_host_extensions.py \
    && chmod 0755 /opt/task-tools/materialize-candidate \
      /opt/task-tools/materialize_candidate.py \
      /opt/task-tools/install_host_extensions.py \
    && if [ -f /opt/task-tools/run-public-examples ]; then \
         chmod 0755 /opt/task-tools/run-public-examples; \
       fi \
    && chown -R root:root /opt/task-tools /examples \
    && chmod -R go-w /opt/task-tools /examples

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed
