FROM ubuntu:22.04@sha256:3b06811b2afd352be909dd088a004166d665dc76d38b13eada33522a9d915c6f

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      build-essential ca-certificates python3 zlib1g-dev \
      bwa=0.7.17-6 freebayes=1.3.6-1 samtools=1.13-4 \
    && rm -rf /var/lib/apt/lists/* \
    && bwa 2>&1 | grep -F "Version: 0.7.17-r1188" \
    && freebayes --version | grep -F "version:  v1.3.6" \
    && samtools --version | head -1 | grep -F "samtools 1.13"

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz donor-source.tar.gz source-lock.json /opt/task-inputs/
RUN echo "0e30b97c3dc7182dbaa489b5599e9c14679b3c68b81006aa994ef00a0573e45a  /opt/task-inputs/host-source.tar.gz" | sha256sum --check --strict \
    && echo "0e12819c649c6b0ba83052182b16ae4588a009c9c4389148e95aaeecce740221  /opt/task-inputs/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-bwa-source /opt/reference-freebayes-source \
    && tar -xzf /opt/task-inputs/host-source.tar.gz -C /opt/pristine-bwa-source \
    && tar -xzf /opt/task-inputs/donor-source.tar.gz -C /opt/reference-freebayes-source \
    && sed -i 's/-O2$/-O2 -fcommon/' /opt/pristine-bwa-source/Makefile \
    && echo "3fb40f4cfeec6f87a5b298b046a9026e93b258bd85914ab1e5830423763fb434  /opt/pristine-bwa-source/Makefile" | sha256sum --check --strict \
    && make -C /opt/pristine-bwa-source -j"$(nproc)"

COPY candidate_runner.py case_specs.json direct_matrix.py fixture_factory.py \
  grader.py reference_runner.py source_policy.py task_io.py test.sh /tests/

RUN chmod 0755 /tests/test.sh /tests/grader.py /tests/reference_runner.py \
      /tests/candidate_runner.py /tests/direct_matrix.py /tests/fixture_factory.py \
    && chown -R root:root /tests /opt/pristine-bwa-source \
      /opt/reference-freebayes-source /opt/task-inputs \
    && chmod -R go-w /tests /opt/pristine-bwa-source \
      /opt/reference-freebayes-source /opt/task-inputs \
    && chmod 0700 /tests /opt/pristine-bwa-source \
      /opt/reference-freebayes-source /opt/task-inputs

ENV PYTHONNOUSERSITE=1
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
WORKDIR /testbed
