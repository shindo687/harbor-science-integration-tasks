module w90_z2_wilson_loop
  !! Clean-room, fixed-mesh Wilson-loop implementation for a four-band,
  !! two-occupied-band time-reversal-symmetric Hamiltonian mesh.
  use, intrinsic :: iso_fortran_env, only : real64
  implicit none
  private
  public :: z2_wilson_loop

  real(real64), parameter :: pi = acos(-1.0_real64)

contains

  subroutine z2_wilson_loop(norb, nocc, nlines, nk, hmesh, gap_tol, &
                            wcc, gap_pos, gap_size, z2, min_gap, status)
    integer, intent(in) :: norb, nocc, nlines, nk
    complex(real64), intent(in) :: hmesh(norb, norb, nk, nlines)
    real(real64), intent(in) :: gap_tol
    real(real64), intent(out) :: wcc(nocc, nlines)
    real(real64), intent(out) :: gap_pos(nlines), gap_size(nlines)
    integer, intent(out) :: z2, status
    real(real64), intent(out) :: min_gap

    complex(real64), allocatable :: occupied(:, :, :)
    complex(real64) :: vectors(4, 4), overlap(2, 2), wilson(2, 2)
    real(real64) :: values(4), gap_left, gap_right
    integer :: line, k, kp, a, ierr, parity

    wcc = 0.0_real64
    gap_pos = 0.0_real64
    gap_size = 0.0_real64
    z2 = 0
    min_gap = huge(1.0_real64)
    status = 0
    if (norb /= 4 .or. nocc /= 2 .or. nlines < 3 .or. nk < 6) then
      status = 1
      return
    end if
    if (gap_tol <= 0.0_real64) then
      status = 1
      return
    end if

    allocate(occupied(4, 2, nk))
    do line = 1, nlines
      do k = 1, nk
        call hermitian_eigensystem4(hmesh(:, :, k, line), values, vectors, ierr)
        if (ierr /= 0) then
          status = 3
          return
        end if
        min_gap = min(min_gap, values(3) - values(2))
        occupied(:, :, k) = vectors(:, 1:2)
      end do
      if (min_gap <= gap_tol) then
        status = 2
        return
      end if

      wilson = cmplx(0.0_real64, 0.0_real64, kind=real64)
      wilson(1, 1) = cmplx(1.0_real64, 0.0_real64, kind=real64)
      wilson(2, 2) = cmplx(1.0_real64, 0.0_real64, kind=real64)
      do k = 1, nk
        kp = modulo(k, nk) + 1
        overlap = matmul(conjg(transpose(occupied(:, :, k))), occupied(:, :, kp))
        wilson = matmul(wilson, overlap)
      end do
      call two_by_two_wcc(wilson, wcc(:, line), ierr)
      if (ierr /= 0) then
        status = 4
        return
      end if
      call largest_gap(wcc(:, line), gap_pos(line), gap_size(line))
    end do

    ! Enforce endpoint Kramers-pair validity before defining the invariant.
    if (circle_distance(wcc(1, 1), wcc(2, 1)) >= 1.0e-3_real64 .or. &
        circle_distance(wcc(1, nlines), wcc(2, nlines)) >= 1.0e-3_real64) then
      status = 5
      return
    end if

    parity = 1
    do line = 2, nlines
      gap_left = gap_pos(line - 1)
      gap_right = gap_pos(line)
      do a = 1, nocc
        if (min(gap_left, gap_right) < wcc(a, line) .and. &
            wcc(a, line) < max(gap_left, gap_right)) parity = -parity
      end do
    end do
    if (parity == -1) z2 = 1
  end subroutine z2_wilson_loop


  subroutine hermitian_eigensystem4(input, values, vectors, ierr)
    complex(real64), intent(in) :: input(4, 4)
    real(real64), intent(out) :: values(4)
    complex(real64), intent(out) :: vectors(4, 4)
    integer, intent(out) :: ierr

    complex(real64) :: a(4, 4), rotation(4, 4), phase
    real(real64) :: largest, scale, app, aqq, magnitude, phi, tau, tangent, cosine, sine
    integer :: sweep, p, q, i, j, best
    complex(real64) :: tmp_column(4)
    real(real64) :: tmp_value

    a = 0.5_real64 * (input + conjg(transpose(input)))
    vectors = cmplx(0.0_real64, 0.0_real64, kind=real64)
    do i = 1, 4
      vectors(i, i) = cmplx(1.0_real64, 0.0_real64, kind=real64)
    end do
    scale = max(1.0_real64, maxval(abs(a)))
    ierr = 0

    do sweep = 1, 120
      largest = 0.0_real64
      p = 1
      q = 2
      do i = 1, 3
        do j = i + 1, 4
          if (abs(a(i, j)) > largest) then
            largest = abs(a(i, j))
            p = i
            q = j
          end if
        end do
      end do
      if (largest <= 2.0e-14_real64 * scale) exit

      app = real(a(p, p), real64)
      aqq = real(a(q, q), real64)
      magnitude = abs(a(p, q))
      phi = atan2(aimag(a(p, q)), real(a(p, q), real64))
      tau = (aqq - app) / (2.0_real64 * magnitude)
      if (tau >= 0.0_real64) then
        tangent = 1.0_real64 / (tau + sqrt(1.0_real64 + tau * tau))
      else
        tangent = -1.0_real64 / (-tau + sqrt(1.0_real64 + tau * tau))
      end if
      cosine = 1.0_real64 / sqrt(1.0_real64 + tangent * tangent)
      sine = tangent * cosine
      phase = cmplx(cos(phi), -sin(phi), kind=real64)

      rotation = cmplx(0.0_real64, 0.0_real64, kind=real64)
      do i = 1, 4
        rotation(i, i) = cmplx(1.0_real64, 0.0_real64, kind=real64)
      end do
      rotation(p, p) = cmplx(cosine, 0.0_real64, kind=real64)
      rotation(p, q) = cmplx(sine, 0.0_real64, kind=real64)
      rotation(q, p) = -phase * sine
      rotation(q, q) = phase * cosine
      a = matmul(conjg(transpose(rotation)), matmul(a, rotation))
      a = 0.5_real64 * (a + conjg(transpose(a)))
      vectors = matmul(vectors, rotation)
    end do
    if (largest > 2.0e-11_real64 * scale) then
      ierr = 1
      return
    end if

    do i = 1, 4
      values(i) = real(a(i, i), real64)
    end do
    do i = 1, 3
      best = i
      do j = i + 1, 4
        if (values(j) < values(best)) best = j
      end do
      if (best /= i) then
        tmp_value = values(i)
        values(i) = values(best)
        values(best) = tmp_value
        tmp_column = vectors(:, i)
        vectors(:, i) = vectors(:, best)
        vectors(:, best) = tmp_column
      end if
    end do
  end subroutine hermitian_eigensystem4


  subroutine two_by_two_wcc(wilson, centers, ierr)
    complex(real64), intent(in) :: wilson(2, 2)
    real(real64), intent(out) :: centers(2)
    integer, intent(out) :: ierr
    complex(real64) :: trace, determinant, root, eig(2)
    real(real64) :: tmp

    trace = wilson(1, 1) + wilson(2, 2)
    determinant = wilson(1, 1) * wilson(2, 2) - wilson(1, 2) * wilson(2, 1)
    root = sqrt(trace * trace - 4.0_real64 * determinant)
    eig(1) = 0.5_real64 * (trace + root)
    eig(2) = 0.5_real64 * (trace - root)
    if (min(abs(eig(1)), abs(eig(2))) <= tiny(1.0_real64)) then
      ierr = 1
      centers = 0.0_real64
      return
    end if
    centers(1) = modulo(atan2(aimag(eig(1)), real(eig(1), real64)) / (2.0_real64 * pi), &
                        1.0_real64)
    centers(2) = modulo(atan2(aimag(eig(2)), real(eig(2), real64)) / (2.0_real64 * pi), &
                        1.0_real64)
    if (centers(2) < centers(1)) then
      tmp = centers(1)
      centers(1) = centers(2)
      centers(2) = tmp
    end if
    ierr = 0
  end subroutine two_by_two_wcc


  subroutine largest_gap(centers, position, size)
    real(real64), intent(in) :: centers(2)
    real(real64), intent(out) :: position, size
    real(real64) :: candidate

    size = centers(2) - centers(1)
    position = modulo(centers(1) + 0.5_real64 * size, 1.0_real64)
    candidate = centers(1) - centers(2) + 1.0_real64
    if (candidate > size) then
      size = candidate
      position = modulo(centers(2) + 0.5_real64 * size, 1.0_real64)
    end if
  end subroutine largest_gap


  pure real(real64) function circle_distance(x, y)
    real(real64), intent(in) :: x, y
    circle_distance = min(modulo(x - y, 1.0_real64), modulo(y - x, 1.0_real64))
  end function circle_distance

end module w90_z2_wilson_loop
