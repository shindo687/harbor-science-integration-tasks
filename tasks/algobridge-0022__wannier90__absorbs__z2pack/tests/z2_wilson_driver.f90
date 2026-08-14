program z2_wilson_driver
  use, intrinsic :: iso_fortran_env, only : real64
  use w90_z2_wilson_loop, only : z2_wilson_loop
  implicit none

  integer :: norb, nocc, nlines, nk, i, j, a, b, status, z2
  real(real64) :: gap_tol, re, im, min_gap
  complex(real64), allocatable :: hmesh(:, :, :, :)
  real(real64), allocatable :: wcc(:, :), gap_pos(:), gap_size(:)

  read (*, *) norb, nocc, nlines, nk
  read (*, *) gap_tol
  allocate(hmesh(norb, norb, nk, nlines))
  allocate(wcc(nocc, nlines), gap_pos(nlines), gap_size(nlines))
  do i = 1, nlines
    do j = 1, nk
      do a = 1, norb
        do b = 1, norb
          read (*, *) re, im
          hmesh(a, b, j, i) = cmplx(re, im, kind=real64)
        end do
      end do
    end do
  end do

  call z2_wilson_loop(norb, nocc, nlines, nk, hmesh, gap_tol, &
                      wcc, gap_pos, gap_size, z2, min_gap, status)

  if (status == 2) then
    write (*, '(a,es24.16e3,a,es24.16e3,a)') &
      '{"gap_tolerance":', gap_tol, ',"min_direct_gap":', min_gap, &
      ',"status":"gap_closed"}'
  else if (status /= 0) then
    write (*, '(a,i0,a)') '{"code":', status, ',"status":"numerical_error"}'
  else
    write (*, '(a)', advance='no') '{"converged":true,"largest_gap_path":['
    do i = 1, nlines
      if (i > 1) write (*, '(a)', advance='no') ','
      write (*, '(es24.16e3)', advance='no') gap_pos(i)
    end do
    write (*, '(a)', advance='no') '],"largest_gap_size":['
    do i = 1, nlines
      if (i > 1) write (*, '(a)', advance='no') ','
      write (*, '(es24.16e3)', advance='no') gap_size(i)
    end do
    write (*, '(a)', advance='no') '],"line_positions":['
    do i = 1, nlines
      if (i > 1) write (*, '(a)', advance='no') ','
      write (*, '(es24.16e3)', advance='no') real(i - 1, real64) / real(nlines - 1, real64)
    end do
    write (*, '(a,es24.16e3,a,i0,a,i0,a)', advance='no') &
      '],"min_direct_gap":', min_gap, ',"num_lines":', nlines, &
      ',"loop_points":', nk, ',"status":"ok","wcc":['
    do i = 1, nlines
      if (i > 1) write (*, '(a)', advance='no') ','
      write (*, '(a)', advance='no') '['
      do a = 1, nocc
        if (a > 1) write (*, '(a)', advance='no') ','
        write (*, '(es24.16e3)', advance='no') wcc(a, i)
      end do
      write (*, '(a)', advance='no') ']'
    end do
    write (*, '(a,i0,a)') '],"z2":', z2, '}'
  end if
end program z2_wilson_driver
