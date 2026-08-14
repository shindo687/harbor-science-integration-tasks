FROM python@sha256:ee0c7d26e2dba416773cb51c042496e9cffacc872459f57726935dd6833f2d96

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python -m pip install --no-index --no-deps --find-links=/opt/wheels \
      numpy==1.24.3 scipy==1.15.3 biopython==1.79 pyparsing==3.1.1 \
    && mkdir -p /opt/reference-runtime \
    && python -m pip install --no-index --no-deps --find-links=/opt/wheels \
      --target=/opt/reference-runtime ProDy==2.6.1 \
    && PYTHONPATH=/opt/reference-runtime python -c \
      'import prody; assert prody.__version__ == "2.6.1"'

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN echo "d9c09e9f2338d87e8bd7d6546d819194a305880a909479552398bf55c42f56bb  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "07ba18e9fbddba5ab43e450c7182809c0a222e3b4bc15048c32d6e38435bf01f  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-host /opt/reference-prody-source \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz \
       -C /opt/reference-prody-source --strip-components=1

COPY candidate_runner.py /opt/candidate-runner/candidate_runner.py
COPY reference_runner.py /opt/reference-runner/reference_runner.py
COPY cases.py model.py grader.py test.sh source-lock.json /tests/
RUN chmod 0755 /tests/test.sh /opt/reference-runner/reference_runner.py \
      /opt/candidate-runner/candidate_runner.py \
    && chown -R root:root /tests /opt/reference-runtime \
      /opt/reference-prody-source /opt/pristine-host \
      /opt/reference-runner /opt/candidate-runner /opt/source-archives \
    && chmod -R go-w /tests /opt/reference-runtime \
      /opt/reference-prody-source /opt/pristine-host \
      /opt/reference-runner /opt/candidate-runner /opt/source-archives \
    && chmod 0700 /tests /opt/reference-runtime \
      /opt/reference-prody-source /opt/pristine-host \
      /opt/reference-runner /opt/source-archives \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py

WORKDIR /testbed
