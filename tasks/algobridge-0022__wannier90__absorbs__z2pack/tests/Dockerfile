FROM docker.io/library/gcc@sha256:1dc2dc4d3fe9e181b0472342a7af1885f3d0f757fb241f815b617f470770f660

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin candidate

COPY wheels/ /opt/wheels/
RUN set -eu; cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && mkdir -p /opt/python-site \
    && for wheel in ./*.whl; do python3 -m zipfile -e "$wheel" /opt/python-site; done \
    && PYTHONPATH=/opt/python-site python3 -c 'import numpy, scipy; assert numpy.__version__ == "1.26.4"; assert scipy.__version__ == "1.15.3"' \
    && chown -R root:root /opt/python-site /opt/wheels \
    && chmod 0700 /opt/python-site /opt/wheels

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN set -eu; cd /opt/source-archives \
    && echo "bf67074beb05da75a8b13ecf6f66d7a349a7c779ca25a9adfe834f04dfad0d0d  host-source.tar.gz" | sha256sum --check --strict \
    && echo "3c718b2a700ca0df87f7467ef7ae24ab030ae7e64ee50896f0dd5d0f1f85bd2d  donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-host /opt/reference-z2pack \
    && tar --no-same-owner --no-same-permissions -xzf host-source.tar.gz -C /opt/pristine-host \
    && tar --no-same-owner --no-same-permissions -xzf donor-source.tar.gz \
       -C /opt/reference-z2pack --strip-components=1 \
    && test "$(find /opt/pristine-host \( -type f -o -type l \) | wc -l)" = 102 \
    && test "$(find /opt/reference-z2pack \( -type f -o -type l \) | wc -l)" = 76 \
    && test -r /opt/reference-z2pack/z2pack/hm.py \
    && chown -R root:root /opt/pristine-host /opt/reference-z2pack /opt/source-archives \
    && chmod 0700 /opt/pristine-host /opt/reference-z2pack /opt/source-archives

RUN mkdir -p /opt/candidate-runner /tests \
    && chown -R root:root /opt/candidate-runner /tests \
    && chmod 0555 /opt/candidate-runner \
    && chmod 0700 /tests

COPY candidate_runner.py z2_wilson_driver.f90 /opt/candidate-runner/
COPY cases.py reference_runner.py grader.py test.sh source-lock.json /tests/
COPY public-examples/ /tests/public-examples/
RUN chmod 0444 /opt/candidate-runner/candidate_runner.py \
      /opt/candidate-runner/z2_wilson_driver.f90 \
    && chmod 0755 /opt/candidate-runner/candidate_runner.py \
    && chown -R root:root /opt/candidate-runner /tests \
    && chmod 0700 /tests /tests/* \
    && chmod 0755 /tests/test.sh

ENV PYTHONPATH=/tests:/opt/candidate-runner:/opt/reference-z2pack:/opt/python-site
ENV PYTHONNOUSERSITE=1
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /testbed

