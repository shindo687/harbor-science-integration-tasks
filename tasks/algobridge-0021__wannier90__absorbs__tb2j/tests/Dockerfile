FROM docker.io/library/gcc@sha256:1dc2dc4d3fe9e181b0472342a7af1885f3d0f757fb241f815b617f470770f660

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin candidate

COPY wheels/ /opt/wheels/
RUN set -eu; cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && mkdir -p /opt/python-site \
    && for wheel in ./*.whl; do python3 -m zipfile -e "$wheel" /opt/python-site; done \
    && PYTHONPATH=/opt/python-site python3 -c 'import ase, HamiltonIO, matplotlib, netCDF4, numpy, scipy, spglib; assert numpy.__version__ == "1.26.4"; assert scipy.__version__ == "1.15.3"' \
    && chown -R root:root /opt/python-site /opt/wheels \
    && chmod 0700 /opt/python-site /opt/wheels

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN set -eu; cd /opt/source-archives \
    && echo "bf67074beb05da75a8b13ecf6f66d7a349a7c779ca25a9adfe834f04dfad0d0d  host-source.tar.gz" | sha256sum --check --strict \
    && echo "805132ddb7daf6178c817c41a78dc295f884d0258da603c3f21b99219e85f751  donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-host /opt/reference-tb2j \
    && tar --no-same-owner --no-same-permissions -xzf host-source.tar.gz -C /opt/pristine-host \
    && tar --no-same-owner --no-same-permissions -xzf donor-source.tar.gz -C /opt/reference-tb2j \
    && test "$(find /opt/pristine-host \( -type f -o -type l \) | wc -l)" = 102 \
    && test "$(find /opt/reference-tb2j \( -type f -o -type l \) | wc -l)" = 241 \
    && test -r /opt/reference-tb2j/TB2J/exchangeCL2.py \
    && PYTHONPATH=/opt/reference-tb2j:/opt/python-site python3 -c 'import TB2J; from TB2J.exchangeCL2 import ExchangeCL2; assert TB2J.__version__ == "0.9.19"' \
    && chown -R root:root /opt/pristine-host /opt/reference-tb2j /opt/source-archives \
    && chmod 0700 /opt/pristine-host /opt/reference-tb2j /opt/source-archives

RUN mkdir -p /opt/candidate-runner /tests \
    && chown -R root:root /opt/candidate-runner /tests \
    && chmod 0555 /opt/candidate-runner \
    && chmod 0700 /tests

COPY candidate_runner.py liechtenstein_driver.f90 /opt/candidate-runner/
COPY cases.py reference_runner.py grader.py test.sh source-lock.json /tests/
COPY public-examples/ /tests/public-examples/
RUN chmod 0444 /opt/candidate-runner/candidate_runner.py \
      /opt/candidate-runner/liechtenstein_driver.f90 \
    && chmod 0755 /opt/candidate-runner/candidate_runner.py \
    && chown -R root:root /opt/candidate-runner /tests \
    && chmod 0700 /tests /tests/* \
    && chmod 0755 /tests/test.sh

ENV PYTHONPATH=/tests:/opt/candidate-runner:/opt/reference-tb2j:/opt/python-site
ENV PYTHONNOUSERSITE=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /testbed
