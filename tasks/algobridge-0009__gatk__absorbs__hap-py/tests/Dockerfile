FROM docker.io/library/eclipse-temurin@sha256:29467857e8bde40ab1f7befecbda0ea764b95afec1cc7f89aa90f7a766577e19 AS jdk

FROM docker.io/library/python@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

COPY --from=jdk /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk
ENV PATH=/opt/java/openjdk/bin:${PATH}

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin candidate \
    && install -d -m 0700 /tests /opt/reference-happy /opt/donor-source \
      /opt/pristine-host /opt/reference-runner /opt/source-archives \
    && install -d -m 0755 /opt/candidate-runner

COPY --chmod=0700 source-parts/ /opt/source-archives/parts/
COPY --chmod=0700 reference-bin/ /opt/reference-happy/bin/
RUN echo "4d43763f81e850a8b96ef44c7aa691623e87824a69b6737213e237057411d06f  /opt/source-archives/parts/host-source.tar.gz.part-00" | sha256sum --check --strict \
    && echo "cdab4cc3fd50beb3a000a409f97dcf7169cb11477c1b58a3c90a822f5f60e84f  /opt/source-archives/parts/host-source.tar.gz.part-01" | sha256sum --check --strict \
    && echo "433cac9e50d87ee0c9a5d2c00a2b821281a2f5fd5668c1b8abdbaec16652c4b2  /opt/source-archives/parts/donor-source.tar.gz.part-00" | sha256sum --check --strict \
    && echo "4eee42064a7ecc13350c7538d67224cdc7eaa76ebf9eb55ca3c43cc5ae7c67e2  /opt/source-archives/parts/donor-source.tar.gz.part-01" | sha256sum --check --strict \
    && echo "82836775d06cda08d8167f3415001907ac4394a86dadad62ed4ec52b44e46d4a  /opt/reference-happy/bin/xcmp" | sha256sum --check --strict \
    && echo "b95af0eea70c5b6784e40a8711f24c1d921217cfae244d0dad465f2364f6cbb2  /opt/reference-happy/bin/bgzip" | sha256sum --check --strict \
    && echo "65a6de482987e706ba7bf3ba3c99344b4306d5b7f49bf9fe44faa195d3384a3e  /opt/reference-happy/bin/tabix" | sha256sum --check --strict \
    && echo "67a21bb586ad26fab6cdd91bc5e3bbfb5df2b10feeb6ca7633d63ac0eef1f3af  /opt/reference-happy/bin/xcmp-build-compat.patch" | sha256sum --check --strict \
    && cat /opt/source-archives/parts/host-source.tar.gz.part-00 /opt/source-archives/parts/host-source.tar.gz.part-01 > /opt/source-archives/host-source.tar.gz \
    && cat /opt/source-archives/parts/donor-source.tar.gz.part-00 /opt/source-archives/parts/donor-source.tar.gz.part-01 > /opt/source-archives/donor-source.tar.gz \
    && echo "2b237ef65d0c596705f7d53e2e5175101ab5b506b93aea0f5f9d4e825e7ebbe6  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "9b1a105d7614468730ec9a3e6287e2c82df6cbf7a1742abbc37fbc68e5b70a73  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && python -c "import tarfile; tarfile.open('/opt/source-archives/host-source.tar.gz').extractall('/opt/pristine-host', filter='data')" \
    && python -c "import tarfile; tarfile.open('/opt/source-archives/donor-source.tar.gz').extractall('/opt/donor-source', filter='data')" \
    && test "$(find /opt/pristine-host -type f -o -type l | wc -l)" -eq 7063 \
    && test "$(find /opt/donor-source -type f -o -type l | wc -l)" -eq 553 \
    && /opt/reference-happy/bin/xcmp --version | grep 'v0.3.15' \
    && /opt/reference-happy/bin/bgzip --version | grep '1.4.1' \
    && /opt/reference-happy/bin/tabix --version | grep '1.4.1'

COPY --chmod=0555 candidate_runner.py /opt/candidate-runner/candidate_runner.py
COPY --chmod=0400 HaplotypeCompareHarness.java /opt/candidate-runner/HaplotypeCompareHarness.java
COPY --chmod=0700 reference_runner.py /opt/reference-runner/reference_runner.py
COPY --chmod=0700 cases.py grader.py test.sh source-lock.json /tests/

WORKDIR /testbed
