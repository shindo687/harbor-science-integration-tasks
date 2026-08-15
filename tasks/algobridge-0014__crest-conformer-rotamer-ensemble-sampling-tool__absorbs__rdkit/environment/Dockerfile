FROM python@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN echo "dbb0ca5d6c904a83d40f1540d5261dfe97c7c1d00ec87cabfc84f1d3df212838  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "552ad28a9073021c7cd652ed08a56f20228f8ae2e1de14bd7216e770a923615d  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /testbed /opt/donor-source \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /testbed \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/donor-source \
    && chown -R root:root /opt/donor-source /opt/source-archives \
    && chmod -R go-w /opt/donor-source /opt/source-archives

COPY task-tools/ /opt/task-tools/
COPY public-examples/ /examples/
COPY source-lock.json /opt/task-source-lock.json
RUN chmod 0755 /opt/task-tools/run-public-examples /examples/verify_examples.py \
    && chown -R root:root /opt/task-tools /examples /opt/task-source-lock.json \
    && chmod -R go-w /opt/task-tools /examples /opt/task-source-lock.json

ENV PYTHONNOUSERSITE=1
WORKDIR /testbed
