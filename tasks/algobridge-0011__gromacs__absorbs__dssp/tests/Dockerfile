FROM python@sha256:69719dbce933473eb3632ee1c3b25788e71752d615ddee02536475be4d9e310b

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python3 -m pip install --no-index --no-deps --find-links=/opt/wheels \
       cmake==3.31.6 ninja==1.11.1.3

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
       --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz donor-source.tar.gz dssp-runtime.tar.gz \
     dssp-4.4.11-h629725b_0.conda /opt/source-archives/
COPY fixtures/ /opt/fixtures/
RUN echo "30bbdf6a344cf1958964bbdf9deb9844f64354c7853eb6e03acc1e0f41ceaec1  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "cc632a1a67545061a44a5cc0caca995b625b34190623844ba72548eddb67c461  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && echo "174a3c2259313b2d9472b8b33df02d94c9611f0e61ed28b5d9b5ef03e1a95e28  /opt/source-archives/dssp-runtime.tar.gz" | sha256sum --check --strict \
    && echo "5580f0cce0c4a1cee944f25272ba5f729eff4dc88721ebf2196c646891e2190c  /opt/source-archives/dssp-4.4.11-h629725b_0.conda" | sha256sum --check --strict \
    && echo "42199a30a0701864a2a5cc76cd7f35cc544cd0e65fbcf63e03c166543249b811  /opt/fixtures/1CRN.pdb" | sha256sum --check --strict \
    && echo "d9f66e70872ddfc941f11845da945561264cfe7044c7991c701638096acbd539  /opt/fixtures/1ZDD.pdb" | sha256sum --check --strict \
    && echo "5b2165e4e495d05e230c6438a8585966578fc70006ec228ac0a0d8b65d06c73c  /opt/fixtures/1TEN.pdb" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-host /opt/reference-donor /opt/dssp \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/reference-donor \
    && tar -xzf /opt/source-archives/dssp-runtime.tar.gz -C /opt/dssp \
    && test "$(find /opt/pristine-host -type f -o -type l | wc -l)" -eq 8124 \
    && test "$(find /opt/reference-donor -type f -o -type l | wc -l)" -eq 32 \
    && cd /opt/dssp/share/libcifpp \
    && /opt/dssp/bin/mkdssp --version

COPY candidate_runner.py /opt/candidate-runner/candidate_runner.py
COPY reference_runner.py /opt/reference-runner/reference_runner.py
COPY cases.py grader.py test.sh source-lock.json /tests/
COPY fixtures/ /tests/fixtures/

RUN chmod 0755 /tests/test.sh /opt/reference-runner/reference_runner.py \
      /opt/candidate-runner/candidate_runner.py \
    && chown -R root:root /tests /opt/pristine-host /opt/reference-donor \
      /opt/reference-runner /opt/candidate-runner /opt/source-archives \
      /opt/fixtures /opt/dssp \
    && chmod -R go-w /tests /opt/pristine-host /opt/reference-donor \
      /opt/reference-runner /opt/candidate-runner /opt/source-archives \
      /opt/fixtures /opt/dssp \
    && chmod 0700 /tests /opt/pristine-host /opt/reference-donor \
      /opt/reference-runner /opt/source-archives /opt/fixtures /opt/dssp \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0755 /opt/candidate-runner/candidate_runner.py

WORKDIR /tests
