/* -*- c++ -*- ----------------------------------------------------------
   Bounded, single-element Moment Tensor Potential pair style for LAMMPS.
------------------------------------------------------------------------- */

#ifdef PAIR_CLASS
// clang-format off
PairStyle(mtp_bounded,PairMTPBounded);
// clang-format on
#else

#ifndef LMP_PAIR_MTP_BOUNDED_H
#define LMP_PAIR_MTP_BOUNDED_H

#include "pair.h"

#include <array>
#include <string>
#include <vector>

namespace LAMMPS_NS {

class PairMTPBounded : public Pair {
 public:
  PairMTPBounded(class LAMMPS *);
  ~PairMTPBounded() override;

  void compute(int, int) override;
  void settings(int, char **) override;
  void coeff(int, char **) override;
  void init_style() override;
  double init_one(int, int) override;
  double memory_usage() override;

 protected:
  struct BasicMoment {
    int radial, px, py, pz;
  };

  struct MomentProduct {
    int left, right, multiplicity, output;
  };

  double cut_global_ = 0.0;
  double min_dist_ = 0.0;
  double max_dist_ = 0.0;
  double scaling_ = 1.0;
  int radial_basis_size_ = 0;
  int radial_funcs_count_ = 0;
  int moment_count_ = 0;
  int scalar_count_ = 0;

  std::vector<double> radial_coeffs_;
  std::vector<BasicMoment> basic_;
  std::vector<MomentProduct> products_;
  std::vector<int> mapping_;
  std::vector<double> regress_coeffs_;

  void allocate();
  void load_potential(const std::string &);
  double site_energy_and_derivatives(
      const std::vector<std::array<double, 3>> &,
      std::vector<std::array<double, 3>> &) const;
};

}    // namespace LAMMPS_NS

#endif
#endif
