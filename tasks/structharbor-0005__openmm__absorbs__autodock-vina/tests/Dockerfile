FROM python@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
COPY vina-potential-reference /opt/reference-vina/vina-potential-reference
RUN echo "83fd59a19a1062c4b11f2a8ec38caecdc10ddeffd6c2577fe520f33bae65627d  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "afd33fc6d6df356a2a8adf3041619abb8c39f0dd1d989e6c0122fcf2c2e4634e  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && echo "4e369cfee5681168ba8db223d4cd46199187878470c87e19ae5d19ccd9248dd2  /opt/reference-vina/vina-potential-reference" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-host /opt/reference-vina-source \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/reference-vina-source \
    && printf '0 0\n' | /opt/reference-vina/vina-potential-reference | grep -Fx 1

COPY candidate_runner.py /opt/candidate-runner/candidate_runner.py
COPY reference_runner.py /opt/reference-runner/reference_runner.py
COPY cases.py grader.py test.sh source-lock.json /tests/

RUN chmod 0755 /tests/test.sh /opt/reference-runner/reference_runner.py \
      /opt/candidate-runner/candidate_runner.py \
    && chown -R root:root /tests /opt/reference-vina /opt/reference-vina-source \
      /opt/pristine-host /opt/reference-runner /opt/candidate-runner \
      /opt/source-archives \
    && chmod -R go-w /tests /opt/reference-vina /opt/reference-vina-source \
      /opt/pristine-host /opt/reference-runner /opt/candidate-runner \
      /opt/source-archives \
    && chmod 0700 /tests /opt/reference-vina /opt/reference-vina-source \
      /opt/pristine-host /opt/reference-runner /opt/source-archives \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py

ENV PYTHONNOUSERSITE=1
WORKDIR /testbed
