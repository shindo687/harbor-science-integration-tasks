FROM python@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
COPY wheels/ /opt/reference-wheels/
RUN echo "b4038953e6d7703905229c3b83935b85f283d4c5bdef9dafcc6a373225307bbb  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "93b5db948d66f45f25dc6f3089e87c3a0b551971aadd6c35eed79864b2b139d2  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && echo "11e06aa0af8c0f05104d56450d6093ee639e15f24ecf62d417329d06e522e017  /opt/reference-wheels/numpy-2.3.5-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/donor-source /opt/candidate-python \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /testbed \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/donor-source \
    && python -m pip install --no-index --no-cache-dir --find-links=/opt/reference-wheels \
      --target=/opt/candidate-python numpy==2.3.5 \
    && chown -R root:root /opt/donor-source /opt/source-archives \
      /opt/reference-wheels /opt/candidate-python \
    && chmod -R go-w /opt/donor-source /opt/source-archives \
      /opt/reference-wheels /opt/candidate-python

COPY task-tools/ /opt/task-tools/
COPY public-examples/ /examples/
COPY source-lock.json /opt/task-source-lock.json
RUN chmod 0755 /opt/task-tools/run-public-examples /examples/verify_examples.py \
    && chown -R root:root /opt/task-tools /examples /opt/task-source-lock.json \
    && chmod -R go-w /opt/task-tools /examples /opt/task-source-lock.json

ENV PYTHONPATH=/opt/candidate-python
ENV PYTHONNOUSERSITE=1
WORKDIR /testbed
