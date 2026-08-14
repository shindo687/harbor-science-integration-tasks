FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --no-deps /opt/wheels/*.whl

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY reference/host-source/ /opt/reference-host/
COPY reference/donor-source/ /opt/reference-donor/
COPY reference/host-source/ /opt/pristine-host/
COPY metadata/ /opt/reference-metadata/
COPY metadata/bilby-2.7.0.dist-info/ /opt/candidate-metadata/bilby-2.7.0.dist-info/
COPY reference_runner.py /opt/reference-runner/reference_runner.py
COPY candidate_runner.py /opt/candidate-runner/candidate_runner.py
COPY cases.py grader.py test.sh source-lock.json \
  reference-host-files.sha256 reference-donor-files.sha256 /tests/

RUN chmod 0755 /tests/test.sh /opt/reference-runner/reference_runner.py \
      /opt/candidate-runner/candidate_runner.py \
    && chown -R root:root /tests /opt/reference-host /opt/reference-donor \
      /opt/pristine-host /opt/reference-runner /opt/reference-metadata \
      /opt/candidate-metadata /opt/candidate-runner \
    && chmod -R go-w /tests /opt/reference-host /opt/reference-donor \
      /opt/pristine-host /opt/reference-runner /opt/reference-metadata \
      /opt/candidate-metadata /opt/candidate-runner \
    && chmod 0700 /tests /opt/reference-host /opt/reference-donor \
      /opt/pristine-host /opt/reference-runner /opt/reference-metadata \
      /opt/candidate-metadata \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
ENV MPLBACKEND=Agg
WORKDIR /testbed
