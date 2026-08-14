FROM docker.io/library/gcc@sha256:1dc2dc4d3fe9e181b0472342a7af1885f3d0f757fb241f815b617f470770f660

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin candidate

COPY wheels/ /opt/wheels/
RUN set -eu; cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && mkdir -p /opt/python-site \
    && python3 -m zipfile -e numpy-1.26.4-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl /opt/python-site \
    && python3 -m zipfile -e scipy-1.15.3-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl /opt/python-site \
    && PYTHONPATH=/opt/python-site python3 -c 'import numpy, scipy; assert numpy.__version__ == "1.26.4"; assert scipy.__version__ == "1.15.3"' \
    && chown -R root:root /opt/python-site /opt/wheels \
    && chmod 0700 /opt/python-site /opt/wheels

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN set -eu; cd /opt/source-archives \
    && echo "ece7507b819fcf69d46caf31e430565066804e805e8446a0cd37fe83dd7b4c38  host-source.tar.gz" | sha256sum --check --strict \
    && echo "0578bc1c58380ad9ad7d8d47bef7616bbd6c5146ad14ad1af836a4122ac0988b  donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-host /opt/reference-boltztrap2 \
    && tar --no-same-owner --no-same-permissions -xzf host-source.tar.gz -C /opt/pristine-host \
    && tar --no-same-owner --no-same-permissions -xzf donor-source.tar.gz \
       -C /opt/reference-boltztrap2 --strip-components=1 \
    && test "$(find /opt/pristine-host \( -type f -o -type l \) | wc -l)" = 7221 \
    && test "$(find /opt/reference-boltztrap2 \( -type f -o -type l \) | wc -l)" = 2646 \
    && chown -R root:root /opt/pristine-host /opt/reference-boltztrap2 /opt/source-archives \
    && chmod 0700 /opt/pristine-host /opt/reference-boltztrap2 /opt/source-archives

RUN mkdir -p /opt/candidate-runner /tests \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0700 /tests

COPY candidate_runner.py transport_driver.f90 /opt/candidate-runner/
COPY cases.py reference_runner.py grader.py test.sh source-lock.json /tests/
COPY public-examples/ /tests/public-examples/
RUN chmod 0444 /opt/candidate-runner/candidate_runner.py \
      /opt/candidate-runner/transport_driver.f90 \
    && chmod 0755 /opt/candidate-runner/candidate_runner.py \
    && chown -R root:root /opt/candidate-runner /tests \
    && chmod 0700 /tests /tests/* \
    && chmod 0755 /tests/test.sh

ENV PYTHONPATH=/opt/python-site
ENV BTP_DONOR_ROOT=/opt/reference-boltztrap2
ENV PYTHONNOUSERSITE=1
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /testbed
