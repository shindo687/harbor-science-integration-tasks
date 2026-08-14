program transport_driver
  use, intrinsic :: iso_fortran_env, only: real64
  use transport_moments_module, only: compute_transport_moments
  implicit none

  integer :: nband, nk, nmu, nt, nbins, status
  integer :: iband, ik, imu, it, i, j
  real(real64) :: volume_a3, spin, reference_electrons, emin_ev, emax_ev
  real(real64), allocatable :: energies(:,:), velocities(:,:,:), weights(:)
  real(real64), allocatable :: mus(:), temperatures(:)
  real(real64), allocatable :: electron_count(:,:), carrier_density(:,:)
  real(real64), allocatable :: l0(:,:,:,:), l1(:,:,:,:), l2(:,:,:,:)
  real(real64), allocatable :: conductivity(:,:,:,:), seebeck(:,:,:,:), kappa(:,:,:,:)

  read (*, *) nband, nk, nmu, nt, nbins
  if (nband < 1 .or. nk < 1 .or. nmu < 1 .or. nt < 1) error stop 90
  allocate(energies(nband, nk), velocities(3, nband, nk), weights(nk))
  allocate(mus(nmu), temperatures(nt))
  allocate(electron_count(nt, nmu), carrier_density(nt, nmu))
  allocate(l0(3, 3, nt, nmu), l1(3, 3, nt, nmu), l2(3, 3, nt, nmu))
  allocate(conductivity(3, 3, nt, nmu), seebeck(3, 3, nt, nmu))
  allocate(kappa(3, 3, nt, nmu))

  read (*, *) volume_a3, spin, reference_electrons, emin_ev, emax_ev
  read (*, *) (weights(ik), ik = 1, nk)
  read (*, *) (mus(imu), imu = 1, nmu)
  read (*, *) (temperatures(it), it = 1, nt)
  do iband = 1, nband
    do ik = 1, nk
      read (*, *) energies(iband, ik), (velocities(i, iband, ik), i = 1, 3)
    end do
  end do

  call compute_transport_moments( &
      energies, velocities, weights, volume_a3, mus, temperatures, spin, &
      reference_electrons, emin_ev, emax_ev, nbins, electron_count, &
      carrier_density, l0, l1, l2, conductivity, seebeck, kappa, status)

  write (*, '(A,3(1X,I0))') 'TMV1', status, nt, nmu
  if (status /= 0) stop 2
  do it = 1, nt
    do imu = 1, nmu
      write (*, '(ES26.17E3)') electron_count(it, imu)
    end do
  end do
  do it = 1, nt
    do imu = 1, nmu
      write (*, '(ES26.17E3)') carrier_density(it, imu)
    end do
  end do
  do it = 1, nt
    do imu = 1, nmu
      do i = 1, 3
        do j = 1, 3
          write (*, '(ES26.17E3)') l0(i, j, it, imu)
        end do
      end do
    end do
  end do
  do it = 1, nt
    do imu = 1, nmu
      do i = 1, 3
        do j = 1, 3
          write (*, '(ES26.17E3)') l1(i, j, it, imu)
        end do
      end do
    end do
  end do
  do it = 1, nt
    do imu = 1, nmu
      do i = 1, 3
        do j = 1, 3
          write (*, '(ES26.17E3)') l2(i, j, it, imu)
        end do
      end do
    end do
  end do
  do it = 1, nt
    do imu = 1, nmu
      do i = 1, 3
        do j = 1, 3
          write (*, '(ES26.17E3)') conductivity(i, j, it, imu)
        end do
      end do
    end do
  end do
  do it = 1, nt
    do imu = 1, nmu
      do i = 1, 3
        do j = 1, 3
          write (*, '(ES26.17E3)') seebeck(i, j, it, imu)
        end do
      end do
    end do
  end do
  do it = 1, nt
    do imu = 1, nmu
      do i = 1, 3
        do j = 1, 3
          write (*, '(ES26.17E3)') kappa(i, j, it, imu)
        end do
      end do
    end do
  end do
end program transport_driver

