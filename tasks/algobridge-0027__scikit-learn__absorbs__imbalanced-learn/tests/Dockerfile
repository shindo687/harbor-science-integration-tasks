FROM python:3.12.11-slim-bookworm

ARG LIBGOMP_URL=https://mirrors.aliyun.com/debian/pool/main/g/gcc-12/libgomp1_12.2.0-14+deb12u1_amd64.deb
RUN python -c 'import os, urllib.request; urllib.request.urlretrieve(os.environ["LIBGOMP_URL"], "/tmp/libgomp1.deb")' \
    && echo '48fec46bda7f5b1638b9e959889bfbc20491247d402d120bb152687eb48143d7  /tmp/libgomp1.deb' \
      | sha256sum --check --strict \
    && dpkg -i /tmp/libgomp1.deb \
    && rm /tmp/libgomp1.deb

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --find-links=/opt/wheels \
      numpy==2.3.2 scipy==1.16.1 pytest==8.4.1 joblib==1.5.1 \
      threadpoolctl==3.6.0 narwhals==2.1.2 \
    && python -m pip install --no-index --no-deps \
      /opt/wheels/scikit_learn-1.10.dev0-cp312-cp312-linux_x86_64.whl \
    && python -m venv /opt/reference-venv \
    && /opt/reference-venv/bin/pip install --no-index --find-links=/opt/wheels \
      numpy==2.3.2 scipy==1.16.1 joblib==1.5.1 \
      threadpoolctl==3.6.0 narwhals==2.1.2 \
    && /opt/reference-venv/bin/pip install --no-index --no-deps \
      /opt/wheels/scikit_learn-1.10.dev0-cp312-cp312-linux_x86_64.whl \
      /opt/wheels/sklearn_compat-0.1.6-py3-none-any.whl

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin candidate

COPY reference/host-source/ /opt/pristine-host/
COPY reference/host-source/ /opt/reference-host/
COPY reference/donor-source/ /opt/reference-donor/
COPY reference_runner.py source-lock.json /opt/reference-runner/
COPY materialize_candidate.py /opt/candidate-tools/materialize_candidate.py
COPY candidate_runner.py /opt/candidate-runner/candidate_runner.py
COPY cases.py grader.py test.sh /tests/
COPY public-examples/ /examples/

RUN chmod 0755 /tests/test.sh /opt/candidate-runner/candidate_runner.py \
    && chown -R root:root /tests /opt/pristine-host /opt/reference-host \
      /opt/reference-donor /opt/reference-runner /opt/candidate-tools \
      /opt/candidate-runner /examples \
    && chmod -R go-w /tests /opt/pristine-host /opt/reference-host \
      /opt/reference-donor /opt/reference-runner /opt/candidate-tools \
      /opt/candidate-runner /examples \
    && chmod 0700 /tests /opt/reference-runner /opt/candidate-tools \
    && chmod 0755 /opt/candidate-runner /examples \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py

ENV PYTHONNOUSERSITE=1
WORKDIR /testbed
