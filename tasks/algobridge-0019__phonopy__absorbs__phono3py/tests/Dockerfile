FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --no-deps --find-links=/opt/wheels \
      numpy==2.3.2 scipy==1.16.1 PyYAML==6.0.3 spglib==2.7.0 \
      h5py==3.16.0 typing-extensions==4.16.0 phonors==0.3.0 \
    && mkdir -p /opt/reference-runtime \
    && python -m pip install --no-index --no-deps --find-links=/opt/wheels \
      --target=/opt/reference-runtime \
      phonopy==4.4.1.dev85+g4bac50622 \
      phono3py==4.4.1.dev7+g2dc8200a6 symfc==1.7.3 \
    && PYTHONPATH=/opt/reference-runtime python -c \
      'import phonopy, phono3py, symfc; assert phonopy.__version__ == "4.4.1.dev85+g4bac50622"; assert phono3py.__version__ == "4.4.1.dev7+g2dc8200a6"; assert symfc.__version__ == "1.7.3"' \
    && PYTHONPATH=/opt/reference-runtime python -c \
      'import phonopy._phonopy, phono3py._phono3py'

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN echo "932dfdebe9dedee2f6687f86dce8029c4cf6bfd257e2e564ae07417720a6b216  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "7180cf6db46a17051d3da0a33acacf182c7a7412c7e8365fca574c99292cead3  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-host /opt/reference-phono3py-source \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz \
      -C /opt/reference-phono3py-source

COPY candidate_runner.py /opt/candidate-runner/candidate_runner.py
COPY reference_runner.py /opt/reference-runner/reference_runner.py
COPY cases.py model.py grader.py test.sh source-lock.json /tests/

RUN chmod 0755 /tests/test.sh /opt/reference-runner/reference_runner.py \
      /opt/candidate-runner/candidate_runner.py \
    && chown -R root:root /tests /opt/reference-runtime \
      /opt/reference-phono3py-source /opt/pristine-host \
      /opt/reference-runner /opt/candidate-runner /opt/source-archives \
    && chmod -R go-w /tests /opt/reference-runtime \
      /opt/reference-phono3py-source /opt/pristine-host \
      /opt/reference-runner /opt/candidate-runner /opt/source-archives \
    && chmod 0700 /tests /opt/reference-runtime \
      /opt/reference-phono3py-source /opt/pristine-host \
      /opt/reference-runner /opt/source-archives \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py

ENV PYTHONNOUSERSITE=1
ENV PYTHONPATH=/opt/pristine-host
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed
