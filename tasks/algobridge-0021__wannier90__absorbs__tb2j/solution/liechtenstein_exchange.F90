module w90_liechtenstein_exchange
  use, intrinsic :: iso_fortran_env, only : real64
  use, intrinsic :: ieee_arithmetic, only : ieee_is_finite
  implicit none
  private
  public :: liechtenstein_exchange

  real(real64), parameter :: pi = acos(-1.0_real64)

contains

  subroutine liechtenstein_exchange(h0_up, h1_up, h0_down, h1_down, nk, nz, &
                                     efermi, smearing, exchange, moments_z, &
                                     integration_emin, status)
    complex(real64), intent(in) :: h0_up(2, 2), h1_up(2, 2)
    complex(real64), intent(in) :: h0_down(2, 2), h1_down(2, 2)
    integer, intent(in) :: nk, nz
    real(real64), intent(in) :: efermi, smearing
    real(real64), intent(out) :: exchange(2, 2, nk), moments_z(2)
    real(real64), intent(out) :: integration_emin
    integer, intent(out) :: status

    complex(real64), allocatable :: path(:), weights(:)
    complex(real64), allocatable :: gr_up(:, :, :), gr_down(:, :, :)
    complex(real64), allocatable :: accumulated(:, :, :)
    complex(real64) :: h_up(2, 2), h_down(2, 2)
    complex(real64) :: g_up(2, 2), g_down(2, 2), phase
    real(real64) :: delta(2), kval, sign_pair
    integer :: ie, ik, ir, jr, i, j, r
    logical :: ok

    exchange = 0.0_real64
    moments_z = 0.0_real64
    integration_emin = 0.0_real64
    status = 1

    if (nk < 5 .or. mod(nk, 2) == 0 .or. nz < 32) return
    if (.not. ieee_is_finite(efermi) .or. .not. ieee_is_finite(smearing)) return
    if (smearing <= 0.0_real64) return
    if (.not. matrices_are_valid(h0_up, h1_up, h0_down, h1_down)) return

    call moments_and_lower_bound(h0_up, h1_up, h0_down, h1_down, nk, &
                                 efermi, smearing, moments_z, integration_emin)
    if (minval(abs(moments_z)) <= 1.0e-8_real64) then
      status = 3
      return
    end if

    delta(1) = real(h0_up(1, 1) - h0_down(1, 1), real64)
    delta(2) = real(h0_up(2, 2) - h0_down(2, 2), real64)

    allocate(path(nz), weights(nz), gr_up(2, 2, nk), gr_down(2, 2, nk))
    allocate(accumulated(2, 2, nk))
    call build_legendre_contour(integration_emin, 0.0_real64, nz, path)
    call simpson_nonuniform_weights(path, weights)
    accumulated = cmplx(0.0_real64, 0.0_real64, real64)

    do ie = 1, nz
      gr_up = cmplx(0.0_real64, 0.0_real64, real64)
      gr_down = cmplx(0.0_real64, 0.0_real64, real64)
      do ik = 1, nk
        kval = (real(ik, real64) - 0.5_real64) / real(nk, real64) - 0.5_real64
        call bloch_hamiltonian(h0_up, h1_up, kval, h_up)
        call bloch_hamiltonian(h0_down, h1_down, kval, h_down)
        call inverse_green(path(ie) + efermi, h_up, g_up, ok)
        if (.not. ok) then
          status = 2
          return
        end if
        call inverse_green(path(ie) + efermi, h_down, g_down, ok)
        if (.not. ok) then
          status = 2
          return
        end if
        do ir = 1, nk
          r = ir - 1 - nk / 2
          phase = exp(cmplx(0.0_real64, -2.0_real64 * pi * real(r, real64) * kval, real64))
          gr_up(:, :, ir) = gr_up(:, :, ir) + g_up * phase / real(nk, real64)
          gr_down(:, :, ir) = gr_down(:, :, ir) + g_down * phase / real(nk, real64)
        end do
      end do

      do ir = 1, nk
        jr = nk + 1 - ir
        do i = 1, 2
          do j = 1, 2
            accumulated(i, j, ir) = accumulated(i, j, ir) + weights(ie) * &
              delta(i) * gr_up(i, j, ir) * delta(j) * gr_down(j, i, jr) / &
              (4.0_real64 * pi)
          end do
        end do
      end do
    end do

    do ir = 1, nk
      do i = 1, 2
        do j = 1, 2
          if (moments_z(i) * moments_z(j) >= 0.0_real64) then
            sign_pair = 1.0_real64
          else
            sign_pair = -1.0_real64
          end if
          exchange(i, j, ir) = aimag(accumulated(i, j, ir)) / sign_pair
        end do
      end do
    end do
    exchange(1, 1, nk / 2 + 1) = 0.0_real64
    exchange(2, 2, nk / 2 + 1) = 0.0_real64
    status = 0
  end subroutine liechtenstein_exchange


  logical function matrices_are_valid(h0_up, h1_up, h0_down, h1_down)
    complex(real64), intent(in) :: h0_up(2, 2), h1_up(2, 2)
    complex(real64), intent(in) :: h0_down(2, 2), h1_down(2, 2)
    integer :: i, j

    matrices_are_valid = .false.
    do i = 1, 2
      do j = 1, 2
        if (.not. finite_complex(h0_up(i, j))) return
        if (.not. finite_complex(h1_up(i, j))) return
        if (.not. finite_complex(h0_down(i, j))) return
        if (.not. finite_complex(h1_down(i, j))) return
      end do
    end do
    if (maxval(abs(h0_up - transpose(conjg(h0_up)))) > 1.0e-11_real64) return
    if (maxval(abs(h0_down - transpose(conjg(h0_down)))) > 1.0e-11_real64) return
    matrices_are_valid = .true.
  end function matrices_are_valid


  logical function finite_complex(value)
    complex(real64), intent(in) :: value
    finite_complex = ieee_is_finite(real(value, real64)) .and. &
                     ieee_is_finite(aimag(value))
  end function finite_complex


  subroutine bloch_hamiltonian(h0, h1, kval, h)
    complex(real64), intent(in) :: h0(2, 2), h1(2, 2)
    real(real64), intent(in) :: kval
    complex(real64), intent(out) :: h(2, 2)
    complex(real64) :: phase

    phase = exp(cmplx(0.0_real64, 2.0_real64 * pi * kval, real64))
    h = h0 + h1 * phase + transpose(conjg(h1)) * conjg(phase)
  end subroutine bloch_hamiltonian


  subroutine inverse_green(energy, h, g, ok)
    complex(real64), intent(in) :: energy, h(2, 2)
    complex(real64), intent(out) :: g(2, 2)
    logical, intent(out) :: ok
    complex(real64) :: a11, a12, a21, a22, determinant

    a11 = energy - h(1, 1)
    a12 = -h(1, 2)
    a21 = -h(2, 1)
    a22 = energy - h(2, 2)
    determinant = a11 * a22 - a12 * a21
    if (abs(determinant) <= 1.0e-24_real64 .or. .not. finite_complex(determinant)) then
      ok = .false.
      g = cmplx(0.0_real64, 0.0_real64, real64)
      return
    end if
    g(1, 1) = a22 / determinant
    g(1, 2) = -a12 / determinant
    g(2, 1) = -a21 / determinant
    g(2, 2) = a11 / determinant
    ok = .true.
  end subroutine inverse_green


  subroutine moments_and_lower_bound(h0_up, h1_up, h0_down, h1_down, nk, &
                                     efermi, smearing, moments, emin)
    complex(real64), intent(in) :: h0_up(2, 2), h1_up(2, 2)
    complex(real64), intent(in) :: h0_down(2, 2), h1_down(2, 2)
    integer, intent(in) :: nk
    real(real64), intent(in) :: efermi, smearing
    real(real64), intent(out) :: moments(2), emin
    complex(real64) :: h(2, 2)
    real(real64) :: rho_up(2), rho_down(2), eval_min, eval_max, kval
    integer :: ik

    rho_up = 0.0_real64
    rho_down = 0.0_real64
    emin = huge(1.0_real64)
    do ik = 1, nk
      kval = (real(ik, real64) - 0.5_real64) / real(nk, real64) - 0.5_real64
      call bloch_hamiltonian(h0_up, h1_up, kval, h)
      call diagonal_density(h, efermi, smearing, rho_up, eval_min, eval_max)
      emin = min(emin, eval_min)
      call bloch_hamiltonian(h0_down, h1_down, kval, h)
      call diagonal_density(h, efermi, smearing, rho_down, eval_min, eval_max)
      emin = min(emin, eval_min)
    end do
    rho_up = rho_up / real(nk, real64)
    rho_down = rho_down / real(nk, real64)
    moments = rho_up - rho_down
    emin = emin - efermi - 0.5_real64
  end subroutine moments_and_lower_bound


  subroutine diagonal_density(h, efermi, smearing, rho, eval_min, eval_max)
    complex(real64), intent(in) :: h(2, 2)
    real(real64), intent(in) :: efermi, smearing
    real(real64), intent(inout) :: rho(2)
    real(real64), intent(out) :: eval_min, eval_max
    real(real64) :: center, split, radius, lower_weight_1
    real(real64) :: occ_min, occ_max

    center = 0.5_real64 * real(h(1, 1) + h(2, 2), real64)
    split = 0.5_real64 * real(h(1, 1) - h(2, 2), real64)
    radius = sqrt(split * split + abs(h(1, 2))**2)
    eval_min = center - radius
    eval_max = center + radius
    occ_min = fermi_occupation(eval_min, efermi, smearing)
    occ_max = fermi_occupation(eval_max, efermi, smearing)
    if (radius <= 1.0e-15_real64) then
      rho = rho + 0.5_real64 * (occ_min + occ_max)
    else
      lower_weight_1 = 0.5_real64 * (1.0_real64 - split / radius)
      rho(1) = rho(1) + occ_min * lower_weight_1 + &
               occ_max * (1.0_real64 - lower_weight_1)
      rho(2) = rho(2) + occ_min * (1.0_real64 - lower_weight_1) + &
               occ_max * lower_weight_1
    end if
  end subroutine diagonal_density


  real(real64) function fermi_occupation(energy, efermi, smearing)
    real(real64), intent(in) :: energy, efermi, smearing
    real(real64) :: x

    x = (energy - efermi) / smearing
    if (x >= 40.0_real64) then
      fermi_occupation = 0.0_real64
    else if (x <= -40.0_real64) then
      fermi_occupation = 1.0_real64
    else
      fermi_occupation = 1.0_real64 / (1.0_real64 + exp(x))
    end if
  end function fermi_occupation


  subroutine build_legendre_contour(emin, emax, n, path)
    real(real64), intent(in) :: emin, emax
    integer, intent(in) :: n
    complex(real64), intent(out) :: path(n)
    real(real64) :: nodes(n), y1, y, phi, radius, center
    integer :: i

    call legendre_nodes(n, nodes)
    y1 = -log(1.0_real64 + pi * 13.0_real64)
    radius = 0.5_real64 * (emax - emin)
    center = 0.5_real64 * (emin + emax)
    do i = 1, n
      y = -0.5_real64 * y1 * nodes(i) + 0.5_real64 * y1
      phi = (exp(-y) - 1.0_real64) / 13.0_real64
      path(i) = center + radius * exp(cmplx(0.0_real64, phi, real64))
    end do
  end subroutine build_legendre_contour


  subroutine legendre_nodes(n, nodes)
    integer, intent(in) :: n
    real(real64), intent(out) :: nodes(n)
    integer :: i, j, m, iteration
    real(real64) :: z, previous, p1, p2, p3, derivative

    m = (n + 1) / 2
    do i = 1, m
      z = cos(pi * (real(i, real64) - 0.25_real64) / &
              (real(n, real64) + 0.5_real64))
      do iteration = 1, 100
        p1 = 1.0_real64
        p2 = 0.0_real64
        do j = 1, n
          p3 = p2
          p2 = p1
          p1 = ((2.0_real64 * real(j, real64) - 1.0_real64) * z * p2 - &
                (real(j, real64) - 1.0_real64) * p3) / real(j, real64)
        end do
        derivative = real(n, real64) * (z * p1 - p2) / (z * z - 1.0_real64)
        previous = z
        z = previous - p1 / derivative
        if (abs(z - previous) <= 4.0_real64 * epsilon(1.0_real64)) exit
      end do
      nodes(i) = -z
      nodes(n + 1 - i) = z
    end do
  end subroutine legendre_nodes


  subroutine simpson_nonuniform_weights(points, weights)
    complex(real64), intent(in) :: points(:)
    complex(real64), intent(out) :: weights(size(points))
    complex(real64) :: h(size(points) - 1), hph
    integer :: n, idx

    n = size(points)
    weights = cmplx(0.0_real64, 0.0_real64, real64)
    h = points(2:n) - points(1:n-1)
    do idx = 2, n - 1, 2
      hph = h(idx) + h(idx - 1)
      weights(idx) = weights(idx) + &
        (h(idx)**3 + h(idx - 1)**3 + 3.0_real64 * h(idx) * h(idx - 1) * hph) / &
        (6.0_real64 * h(idx) * h(idx - 1))
      weights(idx - 1) = weights(idx - 1) + &
        (2.0_real64 * h(idx - 1)**3 - h(idx)**3 + &
         3.0_real64 * h(idx) * h(idx - 1)**2) / &
        (6.0_real64 * h(idx - 1) * hph)
      weights(idx + 1) = weights(idx + 1) + &
        (2.0_real64 * h(idx)**3 - h(idx - 1)**3 + &
         3.0_real64 * h(idx - 1) * h(idx)**2) / &
        (6.0_real64 * h(idx) * hph)
    end do
    if (mod(n, 2) == 0) then
      weights(n) = weights(n) + &
        (2.0_real64 * h(n - 1)**2 + 3.0_real64 * h(n - 2) * h(n - 1)) / &
        (6.0_real64 * (h(n - 2) + h(n - 1)))
      weights(n - 1) = weights(n - 1) + &
        (h(n - 1)**2 + 3.0_real64 * h(n - 1) * h(n - 2)) / &
        (6.0_real64 * h(n - 2))
      weights(n - 2) = weights(n - 2) - h(n - 1)**3 / &
        (6.0_real64 * h(n - 2) * (h(n - 2) + h(n - 1)))
    end if
  end subroutine simpson_nonuniform_weights

end module w90_liechtenstein_exchange
