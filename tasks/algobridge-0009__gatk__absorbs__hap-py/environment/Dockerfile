FROM docker.io/library/eclipse-temurin@sha256:29467857e8bde40ab1f7befecbda0ea764b95afec1cc7f89aa90f7a766577e19 AS jdk

FROM docker.io/library/python@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

COPY --from=jdk /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk
ENV PATH=/opt/java/openjdk/bin:${PATH}

COPY source-parts/ /opt/source-parts/
RUN echo "4d43763f81e850a8b96ef44c7aa691623e87824a69b6737213e237057411d06f  /opt/source-parts/host-source.tar.gz.part-00" | sha256sum --check --strict \
    && echo "cdab4cc3fd50beb3a000a409f97dcf7169cb11477c1b58a3c90a822f5f60e84f  /opt/source-parts/host-source.tar.gz.part-01" | sha256sum --check --strict \
    && echo "433cac9e50d87ee0c9a5d2c00a2b821281a2f5fd5668c1b8abdbaec16652c4b2  /opt/source-parts/donor-source.tar.gz.part-00" | sha256sum --check --strict \
    && echo "4eee42064a7ecc13350c7538d67224cdc7eaa76ebf9eb55ca3c43cc5ae7c67e2  /opt/source-parts/donor-source.tar.gz.part-01" | sha256sum --check --strict \
    && mkdir -p /opt/source-archives /testbed /opt/donor-source \
    && cat /opt/source-parts/host-source.tar.gz.part-00 /opt/source-parts/host-source.tar.gz.part-01 > /opt/source-archives/host-source.tar.gz \
    && cat /opt/source-parts/donor-source.tar.gz.part-00 /opt/source-parts/donor-source.tar.gz.part-01 > /opt/source-archives/donor-source.tar.gz \
    && echo "2b237ef65d0c596705f7d53e2e5175101ab5b506b93aea0f5f9d4e825e7ebbe6  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "9b1a105d7614468730ec9a3e6287e2c82df6cbf7a1742abbc37fbc68e5b70a73  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && python -c "import tarfile; tarfile.open('/opt/source-archives/host-source.tar.gz').extractall('/testbed', filter='data')" \
    && python -c "import tarfile; tarfile.open('/opt/source-archives/donor-source.tar.gz').extractall('/opt/donor-source', filter='data')" \
    && test "$(find /testbed -type f -o -type l | wc -l)" -eq 7063 \
    && test "$(find /opt/donor-source -type f -o -type l | wc -l)" -eq 553 \
    && java -version \
    && javac -version

COPY --chmod=0755 task-tools/ /opt/task-tools/
COPY --chmod=0755 public-examples/ /examples/
COPY --chmod=0644 source-lock.json /opt/task-source-lock.json

WORKDIR /testbed
