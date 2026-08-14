// Root-only batch adapter over the locked AutoDock Vina 1.2.7 potentials.
// This file supplies protocol glue only; every raw potential value is obtained
// by calling the donor classes in src/lib/potentials.h.

#include <cmath>
#include <iomanip>
#include <iostream>
#include <stdexcept>

#include "potentials.h"

namespace {

constexpr double kGauss1Weight = -0.035579;
constexpr double kGauss2Weight = -0.005156;
constexpr double kRepulsionWeight = 0.840245;
constexpr double kHydrophobicWeight = -0.035069;
constexpr double kHydrogenWeight = -0.587439;
constexpr double kRotWeight = 0.05846;
constexpr double kStep = 1e-6;

double weighted(Potential& potential, std::size_t first, std::size_t second,
                double distance, double weight) {
  return weight * potential.eval(first, second, distance);
}

double derivative(Potential& potential, std::size_t first, std::size_t second,
                  double distance, double weight) {
  if (distance <= kStep)
    throw std::runtime_error("distance is too small for central difference");
  const double high = potential.eval(first, second, distance + kStep);
  const double low = potential.eval(first, second, distance - kStep);
  return weight * (high - low) / (2.0 * kStep);
}

}  // namespace

int main() {
  std::ios::sync_with_stdio(false);
  std::cin.tie(nullptr);

  unsigned num_torsions = 0;
  std::size_t count = 0;
  if (!(std::cin >> num_torsions >> count))
    return 2;

  vina_gaussian gauss1(0.0, 0.5, 8.0);
  vina_gaussian gauss2(3.0, 2.0, 8.0);
  vina_repulsion repulsion(0.0, 8.0);
  vina_hydrophobic hydrophobic(0.5, 1.5, 8.0);
  vina_non_dir_h_bond hydrogen(-0.7, 0.0, 8.0);
  Potential* potentials[] = {&gauss1, &gauss2, &repulsion,
                             &hydrophobic, &hydrogen};
  const double weights[] = {kGauss1Weight, kGauss2Weight, kRepulsionWeight,
                            kHydrophobicWeight, kHydrogenWeight};

  const double divisor = 1.0 + kRotWeight * num_torsions / 5.0;
  std::cout << std::setprecision(17) << divisor << '\n';
  for (std::size_t row = 0; row < count; ++row) {
    std::size_t first = 0, second = 0;
    double distance = 0;
    if (!(std::cin >> first >> second >> distance))
      return 3;
    if (first >= 19 || second >= 19 || !std::isfinite(distance)
        || distance <= kStep)
      return 4;
    for (std::size_t term = 0; term < 5; ++term) {
      if (term)
        std::cout << ' ';
      std::cout << weighted(*potentials[term], first, second, distance,
                            weights[term]);
    }
    for (std::size_t term = 0; term < 5; ++term)
      std::cout << ' '
                << derivative(*potentials[term], first, second, distance,
                              weights[term]);
    std::cout << '\n';
  }
  return 0;
}

