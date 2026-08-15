FROM python@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
COPY APBS-3.4.1.Linux.zip /opt/reference-apbs/APBS-3.4.1.Linux.zip
COPY wheels/ /opt/reference-wheels/
RUN echo "b4038953e6d7703905229c3b83935b85f283d4c5bdef9dafcc6a373225307bbb  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "93b5db948d66f45f25dc6f3089e87c3a0b551971aadd6c35eed79864b2b139d2  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && echo "750f6a2df7b5a82b69be5c4cb192115c02fa261d0ff52cf1d9632ed1eda8b4f0  /opt/reference-apbs/APBS-3.4.1.Linux.zip" | sha256sum --check --strict \
    && echo "11e06aa0af8c0f05104d56450d6093ee639e15f24ecf62d417329d06e522e017  /opt/reference-wheels/numpy-2.3.5-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-host /opt/reference-apbs-source /opt/candidate-python \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/reference-apbs-source \
    && python -m zipfile -e /opt/reference-apbs/APBS-3.4.1.Linux.zip /opt/reference-apbs \
    && chmod 0755 /opt/reference-apbs/APBS-3.4.1.Linux/bin/apbs \
    && python -m pip install --no-index --no-cache-dir --find-links=/opt/reference-wheels \
      --target=/opt/candidate-python numpy==2.3.5 \
    && (/opt/reference-apbs/APBS-3.4.1.Linux/bin/apbs --version 2>&1 || test $? -eq 13) \
      | grep "APBS 3.4.1"

COPY candidate_runner.py /opt/candidate-runner/candidate_runner.py
COPY reference_runner.py /opt/reference-runner/reference_runner.py
COPY cases.py grader.py test.sh source-lock.json /tests/
RUN chmod 0755 /tests/test.sh /opt/reference-runner/reference_runner.py \
      /opt/candidate-runner/candidate_runner.py \
    && chown -R root:root /tests /opt/reference-apbs /opt/reference-apbs-source \
      /opt/reference-wheels /opt/pristine-host /opt/reference-runner \
      /opt/candidate-runner /opt/candidate-python /opt/source-archives \
    && chmod -R go-w /tests /opt/reference-apbs /opt/reference-apbs-source \
      /opt/reference-wheels /opt/pristine-host /opt/reference-runner \
      /opt/candidate-runner /opt/candidate-python /opt/source-archives \
    && chmod 0700 /tests /opt/reference-apbs /opt/reference-apbs-source \
      /opt/reference-wheels /opt/pristine-host /opt/reference-runner /opt/source-archives \
    && chmod -R a+rX /opt/candidate-python \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py

ENV PYTHONPATH=/opt/candidate-python
ENV PYTHONNOUSERSITE=1
WORKDIR /testbed
