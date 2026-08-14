FROM python@sha256:13c9584604a99ca134c4f41800f74ffc64ee6ac8cf555cf1e704a6087fc84f12

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --no-deps --find-links=/opt/wheels \
      numpy==2.3.2 scipy==1.16.1 joblib==1.5.1 \
      threadpoolctl==3.6.0 narwhals==2.1.2 \
    && python -m pip install --no-index --no-deps \
      /opt/wheels/scikit_learn-1.10.dev0-cp312-cp312-linux_x86_64.whl

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz donor-source.tar.gz xgboost-runtime.tar.gz /opt/source-archives/
RUN echo "5a07940f6efdf9dc79d92c625c46cf9b266ab47417bfee8f41dbf164f9ad9802  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "16540bd4551d0d0d521fef3399ace68499a654f21846d79056791707c476d70f  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && echo "f95cf5467113eceb9f5ada0f94ec3d84a5b444af0883379a743a25f09ccfd5b3  /opt/source-archives/xgboost-runtime.tar.gz" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-host /opt/reference-xgboost-source \
      /opt/reference-runtime \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz \
      -C /opt/reference-xgboost-source --strip-components=1 \
    && tar -xzf /opt/source-archives/xgboost-runtime.tar.gz \
      -C /opt/reference-runtime \
    && echo "72a74268773454f12f76819ee1338a4eec7573558ee62b6fd9e20a3f5c99ac05  /opt/reference-runtime/xgboost/lib/libxgboost.so" | sha256sum --check --strict \
    && rm -rf /opt/source-archives

COPY materialize_candidate.py /opt/candidate-tools/materialize_candidate.py
COPY candidate_runner.py model.py /opt/candidate-runner/
COPY reference_runner.py model.py /opt/reference-runner/
COPY cases.py model.py grader.py source-lock.json test.sh /tests/

RUN chmod 0755 /tests/test.sh /opt/candidate-runner/candidate_runner.py \
      /opt/reference-runner/reference_runner.py \
      /opt/candidate-tools/materialize_candidate.py \
    && chown -R root:root /tests /opt/pristine-host \
      /opt/reference-xgboost-source /opt/reference-runtime \
      /opt/reference-runner /opt/candidate-runner /opt/candidate-tools \
    && chmod -R go-w /tests /opt/pristine-host \
      /opt/reference-xgboost-source /opt/reference-runtime \
      /opt/reference-runner /opt/candidate-runner /opt/candidate-tools \
    && chmod 0700 /tests /opt/pristine-host \
      /opt/reference-xgboost-source /opt/reference-runtime \
      /opt/reference-runner /opt/candidate-tools \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py \
      /opt/candidate-runner/model.py

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed
