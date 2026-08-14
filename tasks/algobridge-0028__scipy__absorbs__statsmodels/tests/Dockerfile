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
      /opt/wheels/scipy-2.0.0.dev0-*.whl \
    && python -m venv /opt/reference-venv \
    && /opt/reference-venv/bin/pip install --no-index --find-links=/opt/wheels \
      numpy pandas patsy packaging \
    && /opt/reference-venv/bin/pip install --no-index --no-deps \
      /opt/wheels/scipy-2.0.0.dev0-*.whl \
      /opt/wheels/statsmodels-*.whl

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY pristine-host/ /opt/pristine-host/
COPY reference_runner.py source-lock.json source-hashes.sha256 source-links.txt /opt/reference-runner/
COPY materialize_candidate.py /opt/candidate-tools/materialize_candidate.py
COPY candidate_runner.py /opt/candidate-runner/candidate_runner.py
COPY cases.py grader.py test.sh /tests/
COPY public-examples/ /examples/

RUN chmod 0755 /tests/test.sh /opt/candidate-runner/candidate_runner.py \
    && chown -R root:root /tests /opt/pristine-host /opt/reference-runner \
      /opt/candidate-tools /opt/candidate-runner /examples \
    && chmod -R go-w /tests /opt/pristine-host /opt/reference-runner \
      /opt/candidate-tools /opt/candidate-runner /examples \
    && chmod 0700 /tests /opt/reference-runner /opt/candidate-tools \
    && chmod 0755 /opt/candidate-runner /examples \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed
