/* Clean-room bounded harmonic force-constant reconstruction for
   ALGOBRIDGE-0024. */

#include "fit_harmonic_fc2.h"

#include "comm.h"
#include "error.h"
#include "json.h"
#include "math_eigen_impl.h"
#include "utils.h"

#include <algorithm>
#include <array>
#include <cerrno>
#include <cmath>
#include <complex>
#include <cstdio>
#include <fstream>
#include <limits>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

using namespace LAMMPS_NS;

namespace {

using Vec3 = std::array<double, 3>;
using Mat3 = std::array<std::array<double, 3>, 3>;
using ForceConstants = std::vector<std::vector<Mat3>>;
using Complex = std::complex<double>;
using CMatrix = std::vector<std::vector<Complex>>;

constexpr double TWO_PI = 6.283185307179586476925286766559;

struct Record {
  int atom;
  Vec3 displacement;
  std::vector<Vec3> forces;
};

struct PhaseTerm {
  int force_atom;
  std::vector<Vec3> vectors;
};

struct ParsedInput {
  int n_atoms;
  int n_primitive;
  int iterations;
  double frequency_factor;
  std::vector<double> masses;
  std::vector<int> p2s_map;
  std::vector<std::vector<std::vector<PhaseTerm>>> phase_links;
  std::vector<Record> records;
  std::vector<Vec3> qpoints;
};

bool finite(double value) { return std::isfinite(value); }

Vec3 read_vec3(const json &value, const std::string &name)
{
  if (!value.is_array() || value.size() != 3) throw std::runtime_error(name + " must have length 3");
  Vec3 result{};
  for (int i = 0; i < 3; ++i) {
    if (!value[i].is_number()) throw std::runtime_error(name + " must be numeric");
    result[i] = value[i].get<double>();
    if (!finite(result[i])) throw std::runtime_error(name + " must be finite");
  }
  return result;
}

double norm(const Vec3 &value)
{
  return std::sqrt(value[0] * value[0] + value[1] * value[1] + value[2] * value[2]);
}

ParsedInput parse_input(const json &root)
{
  if (!root.is_object()) throw std::runtime_error("input root must be an object");
  if (root.value("format", std::string()) != "algobridge-fc2-v1")
    throw std::runtime_error("unsupported input format");

  ParsedInput input{};
  if (!root.contains("frequency_factor") || !root["frequency_factor"].is_number())
    throw std::runtime_error("frequency_factor is required");
  input.frequency_factor = root["frequency_factor"].get<double>();
  if (!finite(input.frequency_factor) || input.frequency_factor <= 0.0)
    throw std::runtime_error("frequency_factor must be positive and finite");
  if (!root.contains("symmetrize_iterations") || !root["symmetrize_iterations"].is_number_integer())
    throw std::runtime_error("symmetrize_iterations is required");
  input.iterations = root["symmetrize_iterations"].get<int>();
  if (input.iterations < 1 || input.iterations > 8)
    throw std::runtime_error("symmetrize_iterations is out of range");

  const json &supercell = root.at("supercell");
  if (!supercell.is_object()) throw std::runtime_error("supercell must be an object");
  input.n_atoms = supercell.at("n_atoms").get<int>();
  input.n_primitive = supercell.at("n_primitive").get<int>();
  if (input.n_atoms < 1 || input.n_atoms > 16) throw std::runtime_error("n_atoms is out of range");
  if (input.n_primitive < 1 || input.n_primitive > 4 || input.n_primitive > input.n_atoms)
    throw std::runtime_error("n_primitive is out of range");

  const json &masses = supercell.at("masses");
  if (!masses.is_array() || static_cast<int>(masses.size()) != input.n_primitive)
    throw std::runtime_error("masses has the wrong length");
  for (const auto &value : masses) {
    if (!value.is_number()) throw std::runtime_error("masses must be numeric");
    double mass = value.get<double>();
    if (!finite(mass) || mass <= 0.0) throw std::runtime_error("masses must be positive and finite");
    input.masses.push_back(mass);
  }

  const json &p2s = supercell.at("p2s_map");
  if (!p2s.is_array() || static_cast<int>(p2s.size()) != input.n_primitive)
    throw std::runtime_error("p2s_map has the wrong length");
  std::set<int> mapped;
  for (const auto &value : p2s) {
    if (!value.is_number_integer()) throw std::runtime_error("p2s_map must contain integers");
    int atom = value.get<int>();
    if (atom < 0 || atom >= input.n_atoms || !mapped.insert(atom).second)
      throw std::runtime_error("p2s_map is invalid");
    input.p2s_map.push_back(atom);
  }

  const json &links = supercell.at("phase_links");
  if (!links.is_array() || static_cast<int>(links.size()) != input.n_primitive)
    throw std::runtime_error("phase_links has the wrong first dimension");
  input.phase_links.resize(input.n_primitive);
  for (int i = 0; i < input.n_primitive; ++i) {
    if (!links[i].is_array() || static_cast<int>(links[i].size()) != input.n_primitive)
      throw std::runtime_error("phase_links has the wrong second dimension");
    input.phase_links[i].resize(input.n_primitive);
    for (int j = 0; j < input.n_primitive; ++j) {
      if (!links[i][j].is_array() || links[i][j].empty())
        throw std::runtime_error("phase_links entries must be non-empty arrays");
      std::set<int> force_atoms;
      for (const auto &item : links[i][j]) {
        if (!item.is_object() || !item.contains("force_atom") || !item["force_atom"].is_number_integer())
          throw std::runtime_error("invalid phase term");
        PhaseTerm term{};
        term.force_atom = item["force_atom"].get<int>();
        if (term.force_atom < 0 || term.force_atom >= input.n_atoms ||
            !force_atoms.insert(term.force_atom).second)
          throw std::runtime_error("invalid or duplicate phase force_atom");
        const json &vectors = item.at("vectors");
        if (!vectors.is_array() || vectors.empty() || vectors.size() > 8)
          throw std::runtime_error("phase vectors must be a non-empty bounded array");
        for (const auto &vector : vectors) term.vectors.push_back(read_vec3(vector, "phase vector"));
        input.phase_links[i][j].push_back(std::move(term));
      }
    }
  }

  const json &records = root.at("records");
  if (!records.is_array() || records.empty() || records.size() > static_cast<size_t>(input.n_atoms * 12))
    throw std::runtime_error("records count is out of range");
  std::vector<int> records_per_atom(input.n_atoms, 0);
  for (const auto &item : records) {
    if (!item.is_object() || !item.at("atom").is_number_integer())
      throw std::runtime_error("invalid record");
    Record record{};
    record.atom = item.at("atom").get<int>();
    if (record.atom < 0 || record.atom >= input.n_atoms) throw std::runtime_error("record atom is out of range");
    record.displacement = read_vec3(item.at("displacement"), "displacement");
    double displacement_norm = norm(record.displacement);
    if (!(displacement_norm > 0.0) || displacement_norm > 0.05)
      throw std::runtime_error("displacement norm is out of range");
    const json &forces = item.at("forces");
    if (!forces.is_array() || static_cast<int>(forces.size()) != input.n_atoms)
      throw std::runtime_error("record forces has the wrong shape");
    for (const auto &force : forces) record.forces.push_back(read_vec3(force, "force"));
    ++records_per_atom[record.atom];
    input.records.push_back(std::move(record));
  }
  for (int count : records_per_atom)
    if (count < 3 || count > 12) throw std::runtime_error("each atom requires 3 to 12 records");

  const json &qpoints = root.at("qpoints");
  if (!qpoints.is_array() || qpoints.empty() || qpoints.size() > 8)
    throw std::runtime_error("qpoints count is out of range");
  for (const auto &qpoint : qpoints) input.qpoints.push_back(read_vec3(qpoint, "qpoint"));
  return input;
}

Mat3 invert3(const Mat3 &source)
{
  double augmented[3][6]{};
  double scale = 0.0;
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j) {
      augmented[i][j] = source[i][j];
      scale = std::max(scale, std::abs(source[i][j]));
    }
  for (int i = 0; i < 3; ++i) augmented[i][i + 3] = 1.0;
  if (!(scale > 0.0)) throw std::runtime_error("rank-deficient displacement design");
  for (int col = 0; col < 3; ++col) {
    int pivot = col;
    for (int row = col + 1; row < 3; ++row)
      if (std::abs(augmented[row][col]) > std::abs(augmented[pivot][col])) pivot = row;
    if (std::abs(augmented[pivot][col]) <= scale * 1e-12)
      throw std::runtime_error("rank-deficient displacement design");
    if (pivot != col)
      for (int j = 0; j < 6; ++j) std::swap(augmented[pivot][j], augmented[col][j]);
    double divisor = augmented[col][col];
    for (double &value : augmented[col]) value /= divisor;
    for (int row = 0; row < 3; ++row) {
      if (row == col) continue;
      double factor = augmented[row][col];
      for (int j = 0; j < 6; ++j) augmented[row][j] -= factor * augmented[col][j];
    }
  }
  Mat3 inverse{};
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j) inverse[i][j] = augmented[i][j + 3];
  return inverse;
}

ForceConstants fit_force_constants(const ParsedInput &input)
{
  std::vector<Mat3> gram(input.n_atoms);
  std::vector<std::vector<Mat3>> cross(input.n_atoms, std::vector<Mat3>(input.n_atoms));
  for (const Record &record : input.records) {
    int displaced = record.atom;
    for (int a = 0; a < 3; ++a)
      for (int b = 0; b < 3; ++b) gram[displaced][a][b] += record.displacement[a] * record.displacement[b];
    for (int atom = 0; atom < input.n_atoms; ++atom)
      for (int a = 0; a < 3; ++a)
        for (int b = 0; b < 3; ++b)
          cross[displaced][atom][a][b] += record.displacement[a] * record.forces[atom][b];
  }
  ForceConstants fc(input.n_atoms, std::vector<Mat3>(input.n_atoms));
  for (int displaced = 0; displaced < input.n_atoms; ++displaced) {
    Mat3 inverse = invert3(gram[displaced]);
    for (int atom = 0; atom < input.n_atoms; ++atom)
      for (int a = 0; a < 3; ++a)
        for (int b = 0; b < 3; ++b)
          for (int k = 0; k < 3; ++k)
            fc[displaced][atom][a][b] -= inverse[a][k] * cross[displaced][atom][k][b];
  }
  return fc;
}

void translational_projection(ForceConstants &fc)
{
  int n = static_cast<int>(fc.size());
  for (int second = 0; second < n; ++second)
    for (int a = 0; a < 3; ++a)
      for (int b = 0; b < 3; ++b) {
        double drift = 0.0;
        for (int first = 0; first < n; ++first) drift += fc[first][second][a][b];
        drift /= n;
        for (int first = 0; first < n; ++first) fc[first][second][a][b] -= drift;
      }
  for (int first = 0; first < n; ++first)
    for (int a = 0; a < 3; ++a)
      for (int b = 0; b < 3; ++b) {
        double drift = 0.0;
        for (int second = 0; second < n; ++second) drift += fc[first][second][a][b];
        drift /= n;
        for (int second = 0; second < n; ++second) fc[first][second][a][b] -= drift;
      }
}

void permutation_projection(ForceConstants &fc)
{
  ForceConstants copy = fc;
  int n = static_cast<int>(fc.size());
  for (int i = 0; i < n; ++i)
    for (int j = 0; j < n; ++j)
      for (int a = 0; a < 3; ++a)
        for (int b = 0; b < 3; ++b) fc[i][j][a][b] = 0.5 * (copy[i][j][a][b] + copy[j][i][b][a]);
}

void symmetrize(ForceConstants &fc, int iterations)
{
  for (int iteration = 0; iteration < iterations; ++iteration) {
    translational_projection(fc);
    permutation_projection(fc);
  }
  translational_projection(fc);
}

CMatrix dynamical_matrix(const ParsedInput &input, const ForceConstants &fc, const Vec3 &qpoint)
{
  int dim = 3 * input.n_primitive;
  CMatrix dm(dim, std::vector<Complex>(dim, Complex(0.0, 0.0)));
  for (int i = 0; i < input.n_primitive; ++i)
    for (int j = 0; j < input.n_primitive; ++j) {
      double normalization = std::sqrt(input.masses[i] * input.masses[j]);
      for (const PhaseTerm &term : input.phase_links[i][j]) {
        Complex phase(0.0, 0.0);
        for (const Vec3 &vector : term.vectors) {
          double angle = TWO_PI * (vector[0] * qpoint[0] + vector[1] * qpoint[1] + vector[2] * qpoint[2]);
          phase += std::exp(Complex(0.0, angle));
        }
        phase /= static_cast<double>(term.vectors.size());
        const Mat3 &block = fc[input.p2s_map[i]][term.force_atom];
        for (int a = 0; a < 3; ++a)
          for (int b = 0; b < 3; ++b) dm[3 * i + a][3 * j + b] += block[a][b] * phase / normalization;
      }
    }
  for (int i = 0; i < dim; ++i)
    for (int j = i; j < dim; ++j) {
      Complex value = 0.5 * (dm[i][j] + std::conj(dm[j][i]));
      dm[i][j] = value;
      dm[j][i] = std::conj(value);
    }
  return dm;
}

void diagonalize(const CMatrix &matrix, std::vector<double> &eigenvalues, CMatrix &eigenvectors)
{
  int n = static_cast<int>(matrix.size());
  int doubled = 2 * n;
  std::vector<std::vector<double>> real_matrix(doubled, std::vector<double>(doubled, 0.0));
  for (int i = 0; i < n; ++i)
    for (int j = 0; j < n; ++j) {
      real_matrix[i][j] = matrix[i][j].real();
      real_matrix[i][j + n] = -matrix[i][j].imag();
      real_matrix[i + n][j] = matrix[i][j].imag();
      real_matrix[i + n][j + n] = matrix[i][j].real();
    }
  std::vector<double> doubled_values(doubled, 0.0);
  std::vector<std::vector<double>> doubled_vectors(doubled, std::vector<double>(doubled, 0.0));
  MathEigen::Jacobi<double, std::vector<double> &, std::vector<std::vector<double>> &,
                    const std::vector<std::vector<double>> &>
      solver(doubled);
  int failed = solver.Diagonalize(real_matrix, doubled_values, doubled_vectors,
                                  decltype(solver)::SORT_INCREASING_EVALS, true, 100);
  if (failed) throw std::runtime_error("Hermitian eigensolver did not converge");

  std::vector<std::vector<Complex>> selected;
  for (int row = 0; row < doubled && static_cast<int>(selected.size()) < n; ++row) {
    std::vector<Complex> candidate(n);
    for (int i = 0; i < n; ++i) candidate[i] = Complex(doubled_vectors[row][i], doubled_vectors[row][i + n]);
    for (const auto &basis : selected) {
      Complex overlap(0.0, 0.0);
      for (int i = 0; i < n; ++i) overlap += std::conj(basis[i]) * candidate[i];
      for (int i = 0; i < n; ++i) candidate[i] -= overlap * basis[i];
    }
    double length2 = 0.0;
    for (const Complex &value : candidate) length2 += std::norm(value);
    if (length2 < 1e-14) continue;
    double inverse_length = 1.0 / std::sqrt(length2);
    for (Complex &value : candidate) value *= inverse_length;
    int pivot = 0;
    for (int i = 1; i < n; ++i)
      if (std::abs(candidate[i]) > std::abs(candidate[pivot])) pivot = i;
    if (std::abs(candidate[pivot]) > 0.0) {
      Complex phase = std::conj(candidate[pivot]) / std::abs(candidate[pivot]);
      for (Complex &value : candidate) value *= phase;
    }
    selected.push_back(std::move(candidate));
    eigenvalues.push_back(doubled_values[row]);
  }
  if (static_cast<int>(selected.size()) != n) throw std::runtime_error("failed to recover complex eigenbasis");
  eigenvectors.assign(n, std::vector<Complex>(n, Complex(0.0, 0.0)));
  for (int mode = 0; mode < n; ++mode)
    for (int component = 0; component < n; ++component) eigenvectors[component][mode] = selected[mode][component];
}

json real_part(const CMatrix &matrix)
{
  json result = json::array();
  for (const auto &row : matrix) {
    json out_row = json::array();
    for (const Complex &value : row) out_row.push_back(value.real());
    result.push_back(std::move(out_row));
  }
  return result;
}

json imaginary_part(const CMatrix &matrix)
{
  json result = json::array();
  for (const auto &row : matrix) {
    json out_row = json::array();
    for (const Complex &value : row) out_row.push_back(value.imag());
    result.push_back(std::move(out_row));
  }
  return result;
}

void diagnostics(const ParsedInput &input, const ForceConstants &fc, double &fit_rms, double &asr_max,
                 double &permutation_max)
{
  double squared = 0.0;
  size_t count = 0;
  for (const Record &record : input.records)
    for (int atom = 0; atom < input.n_atoms; ++atom)
      for (int b = 0; b < 3; ++b) {
        double predicted = 0.0;
        for (int a = 0; a < 3; ++a) predicted -= record.displacement[a] * fc[record.atom][atom][a][b];
        double difference = predicted - record.forces[atom][b];
        squared += difference * difference;
        ++count;
      }
  fit_rms = std::sqrt(squared / static_cast<double>(count));
  asr_max = 0.0;
  permutation_max = 0.0;
  for (int i = 0; i < input.n_atoms; ++i)
    for (int a = 0; a < 3; ++a)
      for (int b = 0; b < 3; ++b) {
        double drift_first = 0.0;
        double drift_second = 0.0;
        for (int j = 0; j < input.n_atoms; ++j) {
          drift_first += fc[j][i][a][b];
          drift_second += fc[i][j][a][b];
          permutation_max = std::max(permutation_max, std::abs(fc[i][j][a][b] - fc[j][i][b][a]));
        }
        asr_max = std::max(asr_max, std::max(std::abs(drift_first), std::abs(drift_second)));
      }
}

json make_output(const ParsedInput &input)
{
  ForceConstants fc = fit_force_constants(input);
  symmetrize(fc, input.iterations);
  double fit_rms, asr_max, permutation_max;
  diagnostics(input, fc, fit_rms, asr_max, permutation_max);
  json output;
  output["format"] = "algobridge-fc2-result-v1";
  output["force_constants"] = fc;
  output["fit_residual_rms"] = fit_rms;
  output["asr_max"] = asr_max;
  output["permutation_max"] = permutation_max;
  output["qpoint_results"] = json::array();
  for (const Vec3 &qpoint : input.qpoints) {
    CMatrix dm = dynamical_matrix(input, fc, qpoint);
    std::vector<double> eigenvalues;
    CMatrix eigenvectors;
    diagonalize(dm, eigenvalues, eigenvectors);
    std::vector<double> frequencies;
    for (double value : eigenvalues) {
      double sign = value < 0.0 ? -1.0 : (value > 0.0 ? 1.0 : 0.0);
      frequencies.push_back(sign * std::sqrt(std::abs(value)) * input.frequency_factor);
    }
    json item;
    item["qpoint"] = qpoint;
    item["dynamical_matrix_real"] = real_part(dm);
    item["dynamical_matrix_imag"] = imaginary_part(dm);
    item["eigenvalues"] = eigenvalues;
    item["frequencies"] = frequencies;
    item["eigenvectors_real"] = real_part(eigenvectors);
    item["eigenvectors_imag"] = imaginary_part(eigenvectors);
    output["qpoint_results"].push_back(std::move(item));
  }
  return output;
}

}    // namespace

void FitHarmonicFC2::command(int narg, char **arg)
{
  if (narg != 2) utils::missing_cmd_args(FLERR, "fit_harmonic_fc2", error);
  if (comm->nprocs != 1) error->all(FLERR, "fit_harmonic_fc2 requires a serial LAMMPS run");
  if (std::string(arg[0]) == std::string(arg[1]))
    error->all(FLERR, "fit_harmonic_fc2 input and output paths must differ");
  try {
    std::ifstream stream(arg[0]);
    if (!stream) throw std::runtime_error("cannot open input file");
    json root;
    stream >> root;
    ParsedInput input = parse_input(root);
    json output = make_output(input);
    std::string temporary = std::string(arg[1]) + ".algobridge.tmp";
    {
      std::ofstream out(temporary, std::ios::out | std::ios::trunc);
      if (!out) throw std::runtime_error("cannot open temporary output file");
      out << output.dump(2) << '\n';
      if (!out) throw std::runtime_error("failed while writing output file");
    }
    if (std::rename(temporary.c_str(), arg[1]) != 0) {
      std::remove(temporary.c_str());
      throw std::runtime_error("cannot finalize output file");
    }
  } catch (const std::exception &exception) {
    error->all(FLERR, "fit_harmonic_fc2: {}", exception.what());
  }
}
