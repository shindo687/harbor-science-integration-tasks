FROM python@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN echo "83fd59a19a1062c4b11f2a8ec38caecdc10ddeffd6c2577fe520f33bae65627d  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "afd33fc6d6df356a2a8adf3041619abb8c39f0dd1d989e6c0122fcf2c2e4634e  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
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
