FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04 AS system

ARG DEBIAN_FRONTEND=noninteractive
RUN sed -i \
      -e 's|http://archive.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
      -e 's|http://security.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' \
      /etc/apt/sources.list \
    && apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
      hmmer kalign patchelf python3 python3-dev python3-pip util-linux \
    && rm -rf /var/lib/apt/lists/*

FROM system AS verifier

COPY wheels/ /opt/wheels/
RUN echo '813cf1fe3e7ca4dbf5327d6e7b4fc8521e92d8bba073ee645ae0d5d036a25750  /opt/wheels/jaxlib-0.4.26+cuda12.cudnn89-cp310-cp310-manylinux2014_x86_64.whl' \
      | sha256sum --check --strict \
    && python3 -m pip install --no-index --find-links=/opt/wheels \
      absl-py==1.0.0 \
      biopython==1.79 \
      chex==0.1.86 \
      dm-haiku==0.0.12 \
      flax==0.8.2 \
      jax==0.4.26 \
      '/opt/wheels/jaxlib-0.4.26+cuda12.cudnn89-cp310-cp310-manylinux2014_x86_64.whl' \
      matplotlib==3.8.0 \
      ml-collections==0.1.0 \
      networkx==3.2.1 \
      numpy==1.24.3 \
      nvidia-cuda-cupti-cu12==12.6.80 \
      nvidia-cuda-nvcc-cu12==12.6.85 \
      openmm==8.2.0 \
      optax==0.2.2 \
      orbax-checkpoint==0.5.9 \
      pdbfixer==1.12.0 \
      scipy==1.15.3 \
      tensorstore==0.1.74 \
      tensorflow-cpu==2.16.1 \
    && ln -s \
      /usr/local/lib/python3.10/dist-packages/nvidia/cuda_nvcc/bin/ptxas \
      /usr/local/bin/ptxas

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin candidate

# CUDA user-space libraries are pinned in the image.  The host's NVIDIA CDI
# implementation injects the selected GPU and its matching driver libraries.
ENV LD_LIBRARY_PATH=/usr/local/nvidia/lib64:/usr/local/cuda/lib64:/usr/local/cuda-12.2/lib64:/usr/local/lib/python3.10/dist-packages/nvidia/cuda_cupti/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cuda_nvcc/nvvm/lib64
ENV XLA_PYTHON_CLIENT_PREALLOCATE=false

COPY test.sh grader.py host-files.sha256 reference-provenance.json \
     real_e2e_runner.py real_e2e_inspect.py /tests/
COPY reference/ /tests/reference/
COPY e2e-data/ /opt/af2-e2e-data/
RUN chmod 0755 /tests/test.sh \
    && chown -R root:root /tests /opt/af2-e2e-data \
    && chmod -R go-w /tests /opt/af2-e2e-data \
    && chmod 0444 /opt/af2-e2e-data/params/params_model_1_multimer_v3.npz \
    && chmod 0444 /opt/af2-e2e-data/obsolete.dat

WORKDIR /testbed
