module transport_moments_module
  use, intrinsic :: iso_fortran_env, only: real64
  use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
  implicit none
  private
  integer, parameter :: dp = real64
  real(dp), parameter :: boltzmann_si = 1.38064852e-23_dp
  real(dp), parameter :: fine_structure = 7.2973525664e-3_dp
  real(dp), parameter :: avogadro = 6.022140857e23_dp
  real(dp), parameter :: clight_si = 299792458.0_dp
  real(dp), parameter :: bohr_si = 5.2917721067e-11_dp
  real(dp), parameter :: electron_mass_si = 9.10938356e-31_dp
  real(dp), parameter :: electron_charge_si = 1.6021766208e-19_dp
  real(dp), parameter :: fd_cutoff = 18.420680733952366_dp
  public :: compute_transport_moments

contains

  subroutine compute_transport_moments( &
      energies_ev, velocities_mps, weights, volume_a3, mus_ev, temperatures_k, &
      spin, reference_electrons, emin_ev, emax_ev, nbins, electron_count, &
      carrier_density, l0, l1, l2, conductivity, seebeck, kappa, status)
    real(dp), intent(in) :: energies_ev(:,:), velocities_mps(:,:,:), weights(:)
    real(dp), intent(in) :: volume_a3, mus_ev(:), temperatures_k(:), spin
    real(dp), intent(in) :: reference_electrons, emin_ev, emax_ev
    integer, intent(in) :: nbins
    real(dp), intent(out) :: electron_count(:,:), carrier_density(:,:)
    real(dp), intent(out) :: l0(:,:,:,:), l1(:,:,:,:), l2(:,:,:,:)
    real(dp), intent(out) :: conductivity(:,:,:,:), seebeck(:,:,:,:), kappa(:,:,:,:)
    integer, intent(out) :: status

    integer :: nband, nk, nmu, nt, iband, ik, ibin, imu, it, i, j
    real(dp) :: clight, meter, kilogram, coulomb, second, joule, volt
    real(dp) :: ampere, siemens, angstrom, boltzmann, velocity_unit
    real(dp) :: de, eha, vuc, kbt, muha, delta, x, occupation, derivative
    real(dp) :: factor, weight_sum, cond_unit, thermo_unit, thermal_unit
    real(dp) :: l12(3,3), l22(3,3), pinv(3,3), work(3,3)
    real(dp), allocatable :: epsilon(:), dos(:), sigma_dos(:,:,:)

    status = 0
    electron_count = 0.0_dp
    carrier_density = 0.0_dp
    l0 = 0.0_dp
    l1 = 0.0_dp
    l2 = 0.0_dp
    conductivity = 0.0_dp
    seebeck = 0.0_dp
    kappa = 0.0_dp

    nband = size(energies_ev, 1)
    nk = size(energies_ev, 2)
    nmu = size(mus_ev)
    nt = size(temperatures_k)
    if (nband < 1 .or. nband > 8 .or. nk < 1 .or. nk > 128) then
      status = 1
      return
    end if
    if (size(velocities_mps, 1) /= 3 .or. &
        size(velocities_mps, 2) /= nband .or. &
        size(velocities_mps, 3) /= nk .or. size(weights) /= nk) then
      status = 2
      return
    end if
    if (nmu < 1 .or. nmu > 9 .or. nt < 1 .or. nt > 6 .or. &
        nbins < 32 .or. nbins > 512) then
      status = 3
      return
    end if
    if (size(electron_count, 1) /= nt .or. size(electron_count, 2) /= nmu .or. &
        size(carrier_density, 1) /= nt .or. size(carrier_density, 2) /= nmu) then
      status = 4
      return
    end if
    if (any(shape(l0) /= [3, 3, nt, nmu]) .or. &
        any(shape(l1) /= [3, 3, nt, nmu]) .or. &
        any(shape(l2) /= [3, 3, nt, nmu]) .or. &
        any(shape(conductivity) /= [3, 3, nt, nmu]) .or. &
        any(shape(seebeck) /= [3, 3, nt, nmu]) .or. &
        any(shape(kappa) /= [3, 3, nt, nmu])) then
      status = 5
      return
    end if
    if (.not. all(ieee_is_finite(energies_ev)) .or. &
        .not. all(ieee_is_finite(velocities_mps)) .or. &
        .not. all(ieee_is_finite(weights)) .or. &
        .not. all(ieee_is_finite(mus_ev)) .or. &
        .not. all(ieee_is_finite(temperatures_k)) .or. &
        .not. ieee_is_finite(volume_a3) .or. .not. ieee_is_finite(spin) .or. &
        .not. ieee_is_finite(reference_electrons) .or. &
        .not. ieee_is_finite(emin_ev) .or. .not. ieee_is_finite(emax_ev)) then
      status = 6
      return
    end if
    weight_sum = sum(weights)
    if (any(weights <= 0.0_dp) .or. abs(weight_sum - 1.0_dp) > 1.0e-12_dp) then
      status = 7
      return
    end if
    if (volume_a3 <= 0.0_dp .or. spin <= 0.0_dp .or. &
        reference_electrons < 0.0_dp .or. any(temperatures_k <= 0.0_dp) .or. &
        emin_ev >= emax_ev) then
      status = 8
      return
    end if
    if (minval(energies_ev) < emin_ev .or. maxval(energies_ev) > emax_ev) then
      status = 9
      return
    end if

    clight = 1.0_dp / fine_structure
    meter = 1.0_dp / bohr_si
    kilogram = 1.0_dp / electron_mass_si
    coulomb = 1.0_dp / electron_charge_si
    second = clight_si / clight * meter
    joule = kilogram * meter**2 / second**2
    volt = joule / coulomb
    ampere = coulomb / second
    siemens = ampere / volt
    angstrom = meter * 1.0e-10_dp
    boltzmann = boltzmann_si * joule
    velocity_unit = meter / second

    allocate(epsilon(nbins), dos(nbins), sigma_dos(3, 3, nbins))
    dos = 0.0_dp
    sigma_dos = 0.0_dp
    de = (emax_ev - emin_ev) * volt / real(nbins, dp)
    do ibin = 1, nbins
      epsilon(ibin) = emin_ev * volt + (real(ibin, dp) - 0.5_dp) * de
    end do
    do iband = 1, nband
      do ik = 1, nk
        if (energies_ev(iband, ik) == emax_ev) then
          ibin = nbins
        else
          ibin = int(floor((energies_ev(iband, ik) - emin_ev) / &
                     (emax_ev - emin_ev) * real(nbins, dp))) + 1
        end if
        if (ibin < 1 .or. ibin > nbins) then
          status = 10
          return
        end if
        dos(ibin) = dos(ibin) + weights(ik) / de
        do i = 1, 3
          do j = 1, 3
            sigma_dos(i, j, ibin) = sigma_dos(i, j, ibin) + weights(ik) * &
                velocities_mps(i, iband, ik) * velocity_unit * &
                velocities_mps(j, iband, ik) * velocity_unit / de
          end do
        end do
      end do
    end do

    do it = 1, nt
      kbt = temperatures_k(it) * boltzmann
      do imu = 1, nmu
        muha = mus_ev(imu) * volt
        do ibin = 1, nbins
          delta = epsilon(ibin) - muha
          x = delta / kbt
          if (x <= -fd_cutoff) then
            occupation = 1.0_dp
            derivative = 0.0_dp
          else if (x >= fd_cutoff) then
            occupation = 0.0_dp
            derivative = 0.0_dp
          else
            occupation = 1.0_dp / (exp(x) + 1.0_dp)
            derivative = -0.25_dp / (cosh(0.5_dp * x)**2) / kbt
          end if
          electron_count(it, imu) = electron_count(it, imu) + &
              spin * dos(ibin) * occupation * de
          factor = -spin * derivative * de
          do i = 1, 3
            do j = 1, 3
              l0(i, j, it, imu) = l0(i, j, it, imu) + &
                  factor * sigma_dos(i, j, ibin)
              l1(i, j, it, imu) = l1(i, j, it, imu) - &
                  factor * sigma_dos(i, j, ibin) * delta
              l2(i, j, it, imu) = l2(i, j, it, imu) + &
                  factor * sigma_dos(i, j, ibin) * delta * delta
            end do
          end do
        end do
        carrier_density(it, imu) = (electron_count(it, imu) - &
            reference_electrons) / (volume_a3 * 1.0e-24_dp)
      end do
    end do

    vuc = volume_a3 * angstrom**3
    cond_unit = siemens / (meter * second)
    thermo_unit = volt * siemens / (meter * second)
    thermal_unit = volt * joule * siemens / (meter * second * coulomb)
    do it = 1, nt
      do imu = 1, nmu
        conductivity(:, :, it, imu) = l0(:, :, it, imu) / cond_unit / vuc
        l12 = l1(:, :, it, imu) / temperatures_k(it) / thermo_unit / vuc
        l22 = l2(:, :, it, imu) / temperatures_k(it) / thermal_unit / vuc
        call symmetric_pseudoinverse(conductivity(:, :, it, imu), pinv)
        seebeck(:, :, it, imu) = matmul(pinv, l12)
        work = matmul(conductivity(:, :, it, imu), seebeck(:, :, it, imu))
        kappa(:, :, it, imu) = l22 - temperatures_k(it) * &
            matmul(work, seebeck(:, :, it, imu))
      end do
    end do
    if (.not. all(ieee_is_finite(electron_count)) .or. &
        .not. all(ieee_is_finite(carrier_density)) .or. &
        .not. all(ieee_is_finite(l0)) .or. .not. all(ieee_is_finite(l1)) .or. &
        .not. all(ieee_is_finite(l2)) .or. &
        .not. all(ieee_is_finite(conductivity)) .or. &
        .not. all(ieee_is_finite(seebeck)) .or. &
        .not. all(ieee_is_finite(kappa))) status = 11
  end subroutine compute_transport_moments


  subroutine symmetric_pseudoinverse(input, inverse)
    real(dp), intent(in) :: input(3,3)
    real(dp), intent(out) :: inverse(3,3)
    real(dp) :: a(3,3), vectors(3,3), app, aqq, apq, arp, arq
    real(dp) :: tau, tangent, cosine, sine, vrp, vrq, scale, offdiag
    integer :: iteration, p, q, r, i

    a = 0.5_dp * (input + transpose(input))
    vectors = 0.0_dp
    do i = 1, 3
      vectors(i, i) = 1.0_dp
    end do
    do iteration = 1, 80
      p = 1
      q = 2
      offdiag = abs(a(1, 2))
      if (abs(a(1, 3)) > offdiag) then
        p = 1
        q = 3
        offdiag = abs(a(1, 3))
      end if
      if (abs(a(2, 3)) > offdiag) then
        p = 2
        q = 3
        offdiag = abs(a(2, 3))
      end if
      scale = max(1.0_dp, maxval(abs(a)))
      if (offdiag <= 4.0_dp * epsilon(1.0_dp) * scale) exit
      app = a(p, p)
      aqq = a(q, q)
      apq = a(p, q)
      tau = (aqq - app) / (2.0_dp * apq)
      if (tau >= 0.0_dp) then
        tangent = 1.0_dp / (tau + sqrt(1.0_dp + tau * tau))
      else
        tangent = -1.0_dp / (-tau + sqrt(1.0_dp + tau * tau))
      end if
      cosine = 1.0_dp / sqrt(1.0_dp + tangent * tangent)
      sine = tangent * cosine
      do r = 1, 3
        if (r /= p .and. r /= q) then
          arp = a(r, p)
          arq = a(r, q)
          a(r, p) = cosine * arp - sine * arq
          a(p, r) = a(r, p)
          a(r, q) = sine * arp + cosine * arq
          a(q, r) = a(r, q)
        end if
      end do
      a(p, p) = cosine * cosine * app - 2.0_dp * sine * cosine * apq + &
          sine * sine * aqq
      a(q, q) = sine * sine * app + 2.0_dp * sine * cosine * apq + &
          cosine * cosine * aqq
      a(p, q) = 0.0_dp
      a(q, p) = 0.0_dp
      do r = 1, 3
        vrp = vectors(r, p)
        vrq = vectors(r, q)
        vectors(r, p) = cosine * vrp - sine * vrq
        vectors(r, q) = sine * vrp + cosine * vrq
      end do
    end do

    inverse = 0.0_dp
    scale = maxval(abs([a(1,1), a(2,2), a(3,3)]))
    if (scale == 0.0_dp) return
    do i = 1, 3
      if (abs(a(i, i)) > 1.0e-15_dp * scale) then
        do p = 1, 3
          do q = 1, 3
            inverse(p, q) = inverse(p, q) + &
                vectors(p, i) * vectors(q, i) / a(i, i)
          end do
        end do
      end if
    end do
  end subroutine symmetric_pseudoinverse

end module transport_moments_module

