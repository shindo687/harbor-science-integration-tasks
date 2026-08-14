program liechtenstein_driver
  use, intrinsic :: iso_fortran_env, only : real64
  use w90_liechtenstein_exchange, only : liechtenstein_exchange
  implicit none

  complex(real64) :: h0_up(2, 2), h1_up(2, 2)
  complex(real64) :: h0_down(2, 2), h1_down(2, 2)
  complex(real64) :: matrices(2, 2, 4)
  real(real64), allocatable :: exchange(:, :, :)
  real(real64) :: moments(2), emin, re_part, im_part, reversal_error
  real(real64) :: efermi, smearing
  integer :: nk, nz, status, ios, i, j, k, r, reverse_index

  read(*, *, iostat=ios) nk, nz, efermi, smearing
  if (ios /= 0 .or. nk <= 0) then
    write(*, '(a)') '{"status":"invalid_input"}'
    stop
  end if
  do k = 1, 4
    do i = 1, 2
      do j = 1, 2
        read(*, *, iostat=ios) re_part, im_part
        if (ios /= 0) then
          write(*, '(a)') '{"status":"invalid_input"}'
          stop
        end if
        matrices(i, j, k) = cmplx(re_part, im_part, real64)
      end do
    end do
  end do
  h0_up = matrices(:, :, 1)
  h1_up = matrices(:, :, 2)
  h0_down = matrices(:, :, 3)
  h1_down = matrices(:, :, 4)

  allocate(exchange(2, 2, nk))
  call liechtenstein_exchange(h0_up, h1_up, h0_down, h1_down, nk, nz, &
                              efermi, smearing, exchange, moments, emin, status)
  if (status == 3) then
    write(*, '(a)') '{"status":"spin_degenerate"}'
    stop
  else if (status /= 0) then
    write(*, '(a)') '{"status":"invalid_input"}'
    stop
  end if

  reversal_error = 0.0_real64
  do k = 1, nk
    reverse_index = nk + 1 - k
    do i = 1, 2
      do j = 1, 2
        reversal_error = max(reversal_error, &
                             abs(exchange(i, j, k) - exchange(j, i, reverse_index)))
      end do
    end do
  end do

  write(*, '(a)', advance='no') '{"status":"ok","kmesh":'
  write(*, '(i0)', advance='no') nk
  write(*, '(a)', advance='no') ',"contour_points":'
  write(*, '(i0)', advance='no') nz
  write(*, '(a)', advance='no') ',"integration_emin":'
  call write_real(emin)
  write(*, '(a)', advance='no') ',"r_values":['
  do k = 1, nk
    if (k > 1) write(*, '(a)', advance='no') ','
    r = k - 1 - nk / 2
    write(*, '(i0)', advance='no') r
  end do
  write(*, '(a)', advance='no') '],"moments_z":['
  call write_real(moments(1))
  write(*, '(a)', advance='no') ','
  call write_real(moments(2))
  write(*, '(a)', advance='no') '],"exchange_ev":['
  do k = 1, nk
    if (k > 1) write(*, '(a)', advance='no') ','
    write(*, '(a)', advance='no') '[['
    call write_real(exchange(1, 1, k))
    write(*, '(a)', advance='no') ','
    call write_real(exchange(1, 2, k))
    write(*, '(a)', advance='no') '],['
    call write_real(exchange(2, 1, k))
    write(*, '(a)', advance='no') ','
    call write_real(exchange(2, 2, k))
    write(*, '(a)', advance='no') ']]'
  end do
  write(*, '(a)', advance='no') '],"pair_reversal_max_error":'
  call write_real(reversal_error)
  write(*, '(a)') '}'

contains

  subroutine write_real(value)
    real(real64), intent(in) :: value
    write(*, '(es25.17e3)', advance='no') value
  end subroutine write_real

end program liechtenstein_driver
