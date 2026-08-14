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
      /opt/wheels/sklearn_compat-0.1.6-py3-none-any.whl

COPY host-source/ /testbed/
COPY host-source/ /opt/pristine-host/
COPY donor-source/ /opt/imbalanced-learn/
COPY task-tools/ /opt/task-tools/
COPY public-examples/ /examples/

RUN python /opt/task-tools/install_host_extensions.py \
    && chmod 0755 /opt/task-tools/run-public-examples \
    && chmod 0755 /opt/task-tools/materialize_candidate.py

ENV PYTHONNOUSERSITE=1
WORKDIR /testbed
