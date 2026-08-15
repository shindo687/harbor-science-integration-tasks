/* ----------------------------------------------------------------------
   Native bounded Moment Tensor Potential evaluation for LAMMPS.

   This is a clean-room implementation of the mathematical MTP inference
   representation.  It intentionally has no MLIP headers, libraries, or
   runtime dependency.
------------------------------------------------------------------------- */

#include "pair_mtp_bounded.h"

#include "atom.h"
#include "error.h"
#include "force.h"
#include "memory.h"
#include "neigh_list.h"
#include "neighbor.h"
#include "utils.h"

#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <limits>
#include <stdexcept>

using namespace LAMMPS_NS;

namespace {

std::vector<double> numbers(const std::string &text)
{
  std::vector<double> result;
  const char *cursor = text.c_str();
  const char *end = cursor + text.size();
  while (cursor < end) {
    if ((*cursor >= '0' && *cursor <= '9') || *cursor == '-' || *cursor == '+' ||
        *cursor == '.') {
      char *after = nullptr;
      const double value = std::strtod(cursor, &after);
      if (after != cursor) {
        result.push_back(value);
        cursor = after;
        continue;
      }
    }
    ++cursor;
  }
  return result;
}

std::string braced_value(const std::string &text, const std::string &label)
{
  const std::size_t key = text.find(label);
  if (key == std::string::npos) throw std::runtime_error("missing field " + label);
  const std::size_t equal = text.find('=', key + label.size());
  const std::size_t open = text.find('{', equal);
  if (equal == std::string::npos || open == std::string::npos)
    throw std::runtime_error("malformed field " + label);
  int depth = 0;
  for (std::size_t pos = open; pos < text.size(); ++pos) {
    if (text[pos] == '{') ++depth;
    if (text[pos] == '}' && --depth == 0) return text.substr(open, pos - open + 1);
  }
  throw std::runtime_error("unterminated field " + label);
}

double scalar_value(const std::string &text, const std::string &label)
{
  const std::size_t key = text.find(label);
  if (key == std::string::npos) throw std::runtime_error("missing field " + label);
  const std::size_t equal = text.find('=', key + label.size());
  if (equal == std::string::npos) throw std::runtime_error("malformed field " + label);
  const char *begin = text.c_str() + equal + 1;
  char *after = nullptr;
  const double value = std::strtod(begin, &after);
  if (after == begin || !std::isfinite(value))
    throw std::runtime_error("non-numeric field " + label);
  return value;
}

int integer_value(const std::string &text, const std::string &label)
{
  const double value = scalar_value(text, label);
  const int converted = static_cast<int>(value);
  if (value != converted) throw std::runtime_error("non-integral field " + label);
  return converted;
}

double int_power(double value, int exponent)
{
  double result = 1.0;
  for (int i = 0; i < exponent; ++i) result *= value;
  return result;
}

}    // namespace

PairMTPBounded::PairMTPBounded(LAMMPS *lmp) : Pair(lmp)
{
  manybody_flag = 1;
  one_coeff = 1;
  restartinfo = 0;
  single_enable = 0;
  centroidstressflag = CENTROID_NOTAVAIL;
}

PairMTPBounded::~PairMTPBounded()
{
  if (allocated) {
    memory->destroy(setflag);
    memory->destroy(cutsq);
  }
}

void PairMTPBounded::allocate()
{
  allocated = 1;
  const int count = atom->ntypes + 1;
  memory->create(setflag, count, count, "pair:setflag");
  memory->create(cutsq, count, count, "pair:cutsq");
  for (int i = 1; i < count; ++i)
    for (int j = 1; j < count; ++j) setflag[i][j] = 0;
}

void PairMTPBounded::settings(int narg, char **arg)
{
  if (narg != 1) error->all(FLERR, "Pair style mtp_bounded requires one cutoff");
  cut_global_ = utils::numeric(FLERR, arg[0], false, lmp);
  if (!(cut_global_ > 0.0) || !std::isfinite(cut_global_))
    error->all(FLERR, "Pair style mtp_bounded cutoff must be positive and finite");
}

void PairMTPBounded::coeff(int narg, char **arg)
{
  if (narg != 3) error->all(FLERR, "Pair style mtp_bounded requires: * * potential.mtp");
  if (atom->ntypes != 1)
    error->all(FLERR, "Pair style mtp_bounded supports exactly one atom type");
  int ilo, ihi, jlo, jhi;
  utils::bounds(FLERR, arg[0], 1, atom->ntypes, ilo, ihi, error);
  utils::bounds(FLERR, arg[1], 1, atom->ntypes, jlo, jhi, error);
  if (ilo != 1 || ihi != 1 || jlo != 1 || jhi != 1)
    error->all(FLERR, "Pair style mtp_bounded requires coefficients for * *");
  if (!allocated) allocate();
  try {
    load_potential(arg[2]);
  } catch (const std::exception &exception) {
    error->all(FLERR, "Invalid bounded MTP potential: {}", exception.what());
  }
  if (std::fabs(max_dist_ - cut_global_) > 1.0e-12)
    error->all(FLERR, "Pair style mtp_bounded cutoff must equal potential max_dist");
  setflag[1][1] = 1;
}

void PairMTPBounded::init_style()
{
  if (force->newton_pair == 0)
    error->all(FLERR, "Pair style mtp_bounded requires newton pair on");
  neighbor->add_request(this, NeighConst::REQ_FULL);
}

double PairMTPBounded::init_one(int i, int j)
{
  if (!setflag[i][j]) error->all(FLERR, "All pair coefficients are not set");
  return cut_global_;
}

double PairMTPBounded::memory_usage()
{
  return sizeof(double) * (radial_coeffs_.capacity() + regress_coeffs_.capacity()) +
      sizeof(BasicMoment) * basic_.capacity() +
      sizeof(MomentProduct) * products_.capacity() + sizeof(int) * mapping_.capacity();
}

void PairMTPBounded::load_potential(const std::string &filename)
{
  std::ifstream input(filename.c_str(), std::ios::binary);
  if (!input) throw std::runtime_error("cannot open " + filename);
  const std::string text((std::istreambuf_iterator<char>(input)),
                         std::istreambuf_iterator<char>());
  if (text.size() > 65536) throw std::runtime_error("potential file is oversized");
  if (text.find("radial_basis_type = RBChebyshev") == std::string::npos)
    throw std::runtime_error("only RBChebyshev is supported");
  if (integer_value(text, "species_count") != 1)
    throw std::runtime_error("only one species is supported");

  scaling_ = scalar_value(text, "scaling");
  min_dist_ = scalar_value(text, "min_dist");
  max_dist_ = scalar_value(text, "max_dist");
  radial_basis_size_ = integer_value(text, "radial_basis_size");
  radial_funcs_count_ = integer_value(text, "radial_funcs_count");
  moment_count_ = integer_value(text, "alpha_moments_count");
  const int basic_count = integer_value(text, "alpha_index_basic_count");
  const int product_count = integer_value(text, "alpha_index_times_count");
  scalar_count_ = integer_value(text, "alpha_scalar_moments");

  if (!std::isfinite(scaling_) || !(min_dist_ > 0.0) || !(max_dist_ > min_dist_) ||
      radial_basis_size_ != 2 || radial_funcs_count_ != 2 || moment_count_ != 36 ||
      basic_count != 26 || product_count != 39 || scalar_count_ != 9)
    throw std::runtime_error("potential is outside the fixed MTP-9 bounds");

  const std::size_t radial_key = text.find("radial_coeffs");
  const std::size_t row_key = text.find("0-0", radial_key);
  const std::size_t radial_begin = text.find('{', row_key);
  const std::size_t radial_end = text.find("alpha_moments_count", radial_begin);
  if (radial_key == std::string::npos || row_key == std::string::npos ||
      radial_begin == std::string::npos || radial_end == std::string::npos)
    throw std::runtime_error("malformed radial coefficients");
  radial_coeffs_ = numbers(text.substr(radial_begin, radial_end - radial_begin));
  if (radial_coeffs_.size() != 4)
    throw std::runtime_error("wrong radial coefficient count");

  const std::vector<double> basic_values = numbers(braced_value(text, "alpha_index_basic"));
  const std::vector<double> product_values = numbers(braced_value(text, "alpha_index_times"));
  const std::vector<double> mapping_values = numbers(braced_value(text, "alpha_moment_mapping"));
  const std::vector<double> species_values = numbers(braced_value(text, "species_coeffs"));
  const std::vector<double> moment_values = numbers(braced_value(text, "moment_coeffs"));
  if (basic_values.size() != static_cast<std::size_t>(4 * basic_count) ||
      product_values.size() != static_cast<std::size_t>(4 * product_count) ||
      mapping_values.size() != static_cast<std::size_t>(scalar_count_) ||
      species_values.size() != 1 ||
      moment_values.size() != static_cast<std::size_t>(scalar_count_))
    throw std::runtime_error("wrong bounded MTP table size");

  basic_.clear();
  for (int row = 0; row < basic_count; ++row) {
    for (int column = 0; column < 4; ++column)
      if (basic_values[4 * row + column] != static_cast<int>(basic_values[4 * row + column]))
        throw std::runtime_error("non-integral basic moment index");
    BasicMoment item{static_cast<int>(basic_values[4 * row]),
                     static_cast<int>(basic_values[4 * row + 1]),
                     static_cast<int>(basic_values[4 * row + 2]),
                     static_cast<int>(basic_values[4 * row + 3])};
    if (item.radial < 0 || item.radial >= radial_funcs_count_ || item.px < 0 ||
        item.py < 0 || item.pz < 0 || item.px + item.py + item.pz > 4)
      throw std::runtime_error("basic moment index is out of bounds");
    basic_.push_back(item);
  }

  products_.clear();
  for (int row = 0; row < product_count; ++row) {
    for (int column = 0; column < 4; ++column)
      if (product_values[4 * row + column] !=
          static_cast<int>(product_values[4 * row + column]))
        throw std::runtime_error("non-integral moment product index");
    MomentProduct item{static_cast<int>(product_values[4 * row]),
                       static_cast<int>(product_values[4 * row + 1]),
                       static_cast<int>(product_values[4 * row + 2]),
                       static_cast<int>(product_values[4 * row + 3])};
    if (item.left < 0 || item.right < 0 || item.output < 0 ||
        item.left >= moment_count_ || item.right >= moment_count_ ||
        item.output >= moment_count_ || item.output < basic_count ||
        item.multiplicity <= 0)
      throw std::runtime_error("moment product index is out of bounds");
    products_.push_back(item);
  }

  mapping_.clear();
  for (double value : mapping_values) {
    const int index = static_cast<int>(value);
    if (value != index || index < 0 || index >= moment_count_)
      throw std::runtime_error("scalar mapping index is out of bounds");
    mapping_.push_back(index);
  }
  regress_coeffs_.clear();
  regress_coeffs_.push_back(species_values[0]);
  regress_coeffs_.insert(regress_coeffs_.end(), moment_values.begin(), moment_values.end());
  for (double value : radial_coeffs_)
    if (!std::isfinite(value)) throw std::runtime_error("non-finite radial coefficient");
  for (double value : regress_coeffs_)
    if (!std::isfinite(value)) throw std::runtime_error("non-finite regression coefficient");
}

double PairMTPBounded::site_energy_and_derivatives(
    const std::vector<std::array<double, 3>> &vectors,
    std::vector<std::array<double, 3>> &derivatives) const
{
  std::vector<double> moments(moment_count_, 0.0);
  std::vector<double> jacobian(basic_.size() * vectors.size() * 3, 0.0);

  for (std::size_t neighbor_index = 0; neighbor_index < vectors.size(); ++neighbor_index) {
    const auto &v = vectors[neighbor_index];
    const double r2 = v[0] * v[0] + v[1] * v[1] + v[2] * v[2];
    const double r = std::sqrt(r2);
    if (!(r >= min_dist_) || !(r < max_dist_))
      throw std::runtime_error("neighbor distance is outside the bounded potential domain");

    const double delta = r - max_dist_;
    const double transform = (2.0 * r - min_dist_ - max_dist_) / (max_dist_ - min_dist_);
    const double transform_derivative = 2.0 / (max_dist_ - min_dist_);
    const double basis_value[2] = {scaling_ * delta * delta,
                                   scaling_ * transform * delta * delta};
    const double basis_derivative[2] = {
        2.0 * scaling_ * delta,
        scaling_ * (transform_derivative * delta * delta + 2.0 * transform * delta)};
    double radial_value[2] = {0.0, 0.0};
    double radial_derivative[2] = {0.0, 0.0};
    for (int mu = 0; mu < radial_funcs_count_; ++mu)
      for (int basis = 0; basis < radial_basis_size_; ++basis) {
        radial_value[mu] += radial_coeffs_[mu * radial_basis_size_ + basis] *
            basis_value[basis];
        radial_derivative[mu] += radial_coeffs_[mu * radial_basis_size_ + basis] *
            basis_derivative[basis];
      }

    for (std::size_t index = 0; index < basic_.size(); ++index) {
      const BasicMoment &item = basic_[index];
      const int degree = item.px + item.py + item.pz;
      const double monomial = int_power(v[0], item.px) * int_power(v[1], item.py) *
          int_power(v[2], item.pz);
      const double inverse_radius = 1.0 / int_power(r, degree);
      const double angular = monomial * inverse_radius;
      moments[index] += radial_value[item.radial] * angular;

      for (int axis = 0; axis < 3; ++axis) {
        const int exponent = axis == 0 ? item.px : (axis == 1 ? item.py : item.pz);
        double monomial_derivative = 0.0;
        if (exponent > 0) {
          const double dx = axis == 0 ? int_power(v[0], item.px - 1) : int_power(v[0], item.px);
          const double dy = axis == 1 ? int_power(v[1], item.py - 1) : int_power(v[1], item.py);
          const double dz = axis == 2 ? int_power(v[2], item.pz - 1) : int_power(v[2], item.pz);
          monomial_derivative = exponent * dx * dy * dz;
        }
        const double angular_derivative = monomial_derivative * inverse_radius -
            degree * angular * v[axis] / r2;
        jacobian[(index * vectors.size() + neighbor_index) * 3 + axis] =
            radial_derivative[item.radial] * v[axis] / r * angular +
            radial_value[item.radial] * angular_derivative;
      }
    }
  }

  for (const MomentProduct &product : products_)
    moments[product.output] += product.multiplicity * moments[product.left] *
        moments[product.right];

  double energy = regress_coeffs_[0];
  std::vector<double> adjoint(moment_count_, 0.0);
  for (int index = 0; index < scalar_count_; ++index) {
    energy += regress_coeffs_[index + 1] * moments[mapping_[index]];
    adjoint[mapping_[index]] += regress_coeffs_[index + 1];
  }
  for (auto iterator = products_.rbegin(); iterator != products_.rend(); ++iterator) {
    const MomentProduct &product = *iterator;
    const double output_adjoint = adjoint[product.output] * product.multiplicity;
    adjoint[product.left] += output_adjoint * moments[product.right];
    adjoint[product.right] += output_adjoint * moments[product.left];
  }

  derivatives.assign(vectors.size(), {{0.0, 0.0, 0.0}});
  for (std::size_t basic_index = 0; basic_index < basic_.size(); ++basic_index)
    for (std::size_t neighbor_index = 0; neighbor_index < vectors.size(); ++neighbor_index)
      for (int axis = 0; axis < 3; ++axis)
        derivatives[neighbor_index][axis] += adjoint[basic_index] *
            jacobian[(basic_index * vectors.size() + neighbor_index) * 3 + axis];
  return energy;
}

void PairMTPBounded::compute(int eflag, int vflag)
{
  ev_init(eflag, vflag);
  double **x = atom->x;
  double **f = atom->f;
  int *type = atom->type;
  const int nlocal = atom->nlocal;
  const int newton_pair = force->newton_pair;
  int *numneigh = list->numneigh;
  int **firstneigh = list->firstneigh;

  std::vector<std::array<double, 3>> vectors;
  std::vector<std::array<double, 3>> derivatives;
  std::vector<int> indices;
  for (int ii = 0; ii < list->inum; ++ii) {
    const int i = list->ilist[ii];
    vectors.clear();
    indices.clear();
    int *neighbors = firstneigh[i];
    for (int jj = 0; jj < numneigh[i]; ++jj) {
      const int j = neighbors[jj] & NEIGHMASK;
      const double dx = x[j][0] - x[i][0];
      const double dy = x[j][1] - x[i][1];
      const double dz = x[j][2] - x[i][2];
      const double r2 = dx * dx + dy * dy + dz * dz;
      if (r2 < cutsq[type[i]][type[j]] && r2 > 1.0e-20) {
        vectors.push_back({{dx, dy, dz}});
        indices.push_back(j);
      }
    }

    double site_energy = 0.0;
    try {
      site_energy = site_energy_and_derivatives(vectors, derivatives);
    } catch (const std::exception &exception) {
      error->all(FLERR, "Bounded MTP evaluation failed: {}", exception.what());
    }
    for (std::size_t jj = 0; jj < vectors.size(); ++jj) {
      const int j = indices[jj];
      for (int axis = 0; axis < 3; ++axis) {
        f[i][axis] += derivatives[jj][axis];
        f[j][axis] -= derivatives[jj][axis];
      }
      if (vflag)
        ev_tally_xyz(i, j, nlocal, newton_pair, 0.0, 0.0,
                     derivatives[jj][0], derivatives[jj][1], derivatives[jj][2],
                     -vectors[jj][0], -vectors[jj][1], -vectors[jj][2]);
    }
    if (eflag) ev_tally_full(i, 2.0 * site_energy, 0.0, 0.0, 0.0, 0.0, 0.0);
  }
  if (vflag_fdotr) virial_fdotr_compute();
}
