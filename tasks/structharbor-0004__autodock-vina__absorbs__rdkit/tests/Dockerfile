FROM python@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
      --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
COPY wheels/ /opt/reference-wheels/
RUN echo "afd33fc6d6df356a2a8adf3041619abb8c39f0dd1d989e6c0122fcf2c2e4634e  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "552ad28a9073021c7cd652ed08a56f20228f8ae2e1de14bd7216e770a923615d  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && echo "04a75a048cd61ef934fd2fd474ff426f40cf22e83fe8cd038d1563d695f7e314  /opt/reference-wheels/rdkit-2026.3.5-cp313-cp313-manylinux_2_28_x86_64.whl" | sha256sum --check --strict \
    && echo "11e06aa0af8c0f05104d56450d6093ee639e15f24ecf62d417329d06e522e017  /opt/reference-wheels/numpy-2.3.5-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl" | sha256sum --check --strict \
    && echo "47b94983da0c642de92ced1702c5b6c292a84bd3a8e1d1702ff923f183594717  /opt/reference-wheels/pillow-12.1.1-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-host /opt/reference-rdkit-source /opt/reference-rdkit/python \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/reference-rdkit-source \
    && python -m pip install --no-index --no-cache-dir \
      --find-links=/opt/reference-wheels --target=/opt/reference-rdkit/python \
      rdkit==2026.3.5 \
    && PYTHONPATH=/opt/reference-rdkit/python python -c \
      "import rdkit; assert rdkit.__version__ == '2026.03.5'"

COPY candidate_runner.py /opt/candidate-runner/candidate_runner.py
COPY reference_runner.py /opt/reference-runner/reference_runner.py
COPY cases.py grader.py test.sh source-lock.json /tests/

RUN chmod 0755 /tests/test.sh /opt/reference-runner/reference_runner.py \
      /opt/candidate-runner/candidate_runner.py \
    && chown -R root:root /tests /opt/reference-rdkit /opt/reference-rdkit-source \
      /opt/reference-wheels /opt/pristine-host /opt/reference-runner \
      /opt/candidate-runner /opt/source-archives \
    && chmod -R go-w /tests /opt/reference-rdkit /opt/reference-rdkit-source \
      /opt/reference-wheels /opt/pristine-host /opt/reference-runner \
      /opt/candidate-runner /opt/source-archives \
    && chmod 0700 /tests /opt/reference-rdkit /opt/reference-rdkit-source \
      /opt/reference-wheels /opt/pristine-host /opt/reference-runner \
      /opt/source-archives \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py

ENV PYTHONNOUSERSITE=1
WORKDIR /testbed
