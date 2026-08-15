FROM python:3.12.11-bookworm@sha256:13c9584604a99ca134c4f41800f74ffc64ee6ac8cf555cf1e704a6087fc84f12

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin candidate \
    && install -d -m 0700 /tests /opt/pristine-host /opt/source-archives /opt/reference-runner \
    && install -d -m 0755 /testbed /opt/candidate-runner

COPY --chmod=0400 source/ /opt/source-archives/
RUN echo "e9eeb0d1936a1459c69e077b454f0af8f4d63d311a48576a14209f4b792c76f7  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host --strip-components=1 \
    && test "$(find /opt/pristine-host \( -type f -o -type l \) | wc -l)" -eq 201 \
    && chmod 0400 /opt/source-archives/host-source.tar.gz

COPY --chmod=0444 candidate_runner.py /opt/candidate-runner/candidate_runner.py
COPY --chmod=0400 reference_runner.py reference_impl.py /opt/reference-runner/
COPY --chmod=0400 cases.py grader.py source-lock.json rosetta-calibration.json /tests/
COPY --chmod=0500 test.sh /tests/test.sh

RUN chmod 0700 /tests /opt/pristine-host /opt/source-archives /opt/reference-runner \
    && chmod 0755 /opt/candidate-runner \
    && test ! -e /opt/rosetta \
    && test ! -e /opt/donor-source

WORKDIR /testbed
