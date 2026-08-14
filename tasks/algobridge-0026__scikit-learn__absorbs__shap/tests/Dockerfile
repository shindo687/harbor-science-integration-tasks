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
      numpy==2.3.2 scipy==1.16.1 pandas==2.3.2 pytest==8.4.1 \
      joblib==1.5.1 threadpoolctl==3.6.0 narwhals==2.1.2 \
    && python -m pip install --no-index --no-deps \
      /opt/wheels/scikit_learn-1.10.dev0-cp312-cp312-linux_x86_64.whl

COPY reference-wheels/ /opt/reference-wheels/
RUN cd /opt/reference-wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m venv /opt/reference-venv \
    && /opt/reference-venv/bin/pip install --no-index --find-links=/opt/reference-wheels \
      numpy==2.3.2 scipy==1.16.1 pandas==2.3.2 joblib==1.5.1 \
      threadpoolctl==3.6.0 narwhals==2.1.2 tqdm==4.67.1 slicer==0.0.8 \
      numba==0.62.1 llvmlite==0.45.1 cloudpickle==3.1.1 packaging==26.3 \
    && /opt/reference-venv/bin/pip install --no-index --no-deps \
      /opt/reference-wheels/scikit_learn-1.10.dev0-cp312-cp312-linux_x86_64.whl \
      /opt/reference-wheels/shap-0.52.1.dev42-cp312-abi3-linux_x86_64.whl

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY reference/host-source/ /opt/pristine-host/
COPY reference/donor-source/ /opt/reference-donor/
COPY reference_runner.py protocol.py source-lock.json /opt/reference-runner/
COPY materialize_candidate.py /opt/candidate-tools/materialize_candidate.py
COPY candidate_runner.py protocol.py /opt/candidate-runner/
COPY cases.py grader.py test.sh /tests/
COPY public-examples/ /examples/
COPY source-hashes.sha256 /opt/reference-integrity/source-hashes.sha256

RUN chmod 0755 /tests/test.sh /opt/candidate-runner/candidate_runner.py \
      /opt/candidate-tools/materialize_candidate.py \
    && chown -R root:root /tests /opt/pristine-host /opt/reference-donor \
      /opt/reference-runner /opt/candidate-tools /opt/candidate-runner \
      /opt/reference-integrity /examples \
    && chmod -R go-w /tests /opt/pristine-host /opt/reference-donor \
      /opt/reference-runner /opt/candidate-tools /opt/candidate-runner \
      /opt/reference-integrity /examples \
    && chmod 0700 /tests /opt/reference-runner /opt/candidate-tools \
      /opt/reference-integrity \
    && chmod 0755 /opt/candidate-runner /examples \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py \
      /opt/candidate-runner/protocol.py

ENV PYTHONNOUSERSITE=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed
