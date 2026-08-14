FROM python:3.12.11-bookworm@sha256:13c9584604a99ca134c4f41800f74ffc64ee6ac8cf555cf1e704a6087fc84f12

COPY wheels/ /opt/wheels/
RUN cd /opt/wheels \
    && sha256sum --check --strict SHA256SUMS \
    && python3 -m pip install --no-index --no-deps --find-links=/opt/wheels \
       cmake==3.31.6 ninja==1.11.1.3 \
       numpy==2.3.2 scipy==1.16.1 numexpr==2.14.1

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --no-create-home \
       --shell /usr/sbin/nologin candidate

COPY host-source.tar.gz donor-source.tar.gz /opt/source-archives/
RUN echo "30bbdf6a344cf1958964bbdf9deb9844f64354c7853eb6e03acc1e0f41ceaec1  /opt/source-archives/host-source.tar.gz" | sha256sum --check --strict \
    && echo "d0e815a1bc88912cb0cb9c64bdb2ffc75eaec6f5225e79bd016acd5cbcf60a17  /opt/source-archives/donor-source.tar.gz" | sha256sum --check --strict \
    && mkdir -p /opt/pristine-host /opt/reference-gromacs /opt/reference-donor \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/pristine-host \
    && tar -xzf /opt/source-archives/host-source.tar.gz -C /opt/reference-gromacs \
    && tar -xzf /opt/source-archives/donor-source.tar.gz -C /opt/reference-donor

RUN cmake -S /opt/reference-gromacs -B /opt/reference-gromacs-build -G Ninja \
      -DGMX_FFT_LIBRARY=fftpack -DGMX_SIMD=SSE2 \
      -DGMX_MPI=OFF -DGMX_THREAD_MPI=OFF -DGMX_OPENMP=OFF -DGMX_GPU=OFF \
      -DBUILD_TESTING=OFF -DGMX_BUILD_UNITTESTS=OFF -DGMXAPI=OFF \
      -DGMX_INSTALL_NBLIB_API=OFF -DGMX_BUILD_MANUAL=OFF \
      -DGMX_EXTERNAL_BLAS=OFF -DGMX_EXTERNAL_LAPACK=OFF \
      -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /opt/reference-gromacs-build --target gmx -j8

COPY candidate_runner.py /opt/candidate-runner/candidate_runner.py
COPY reference_runner.py /opt/reference-runner/reference_runner.py
COPY cases.py grader.py test.sh source-lock.json /tests/

RUN chmod 0755 /tests/test.sh /opt/reference-runner/reference_runner.py \
      /opt/candidate-runner/candidate_runner.py \
    && chown -R root:root /tests /opt/pristine-host /opt/reference-gromacs \
      /opt/reference-gromacs-build /opt/reference-donor /opt/reference-runner \
      /opt/candidate-runner /opt/source-archives \
    && chmod -R go-w /tests /opt/pristine-host /opt/reference-gromacs \
      /opt/reference-gromacs-build /opt/reference-donor /opt/reference-runner \
      /opt/candidate-runner /opt/source-archives \
    && chmod 0700 /tests /opt/pristine-host /opt/reference-gromacs \
      /opt/reference-gromacs-build /opt/reference-donor /opt/reference-runner \
      /opt/source-archives \
    && chmod 0755 /opt/candidate-runner \
    && chmod 0444 /opt/candidate-runner/candidate_runner.py

ENV PYTHONNOUSERSITE=1
ENV PYMBAR_DISABLE_JAX=1
ENV OPENBLAS_NUM_THREADS=1
ENV OMP_NUM_THREADS=1
WORKDIR /testbed
