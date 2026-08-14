/* -*- c++ -*-
   Clean-room Oracle for ALGOBRIDGE-0024. */

#ifdef COMMAND_CLASS
// clang-format off
CommandStyle(fit_harmonic_fc2,FitHarmonicFC2);
// clang-format on
#else

#ifndef LMP_FIT_HARMONIC_FC2_H
#define LMP_FIT_HARMONIC_FC2_H

#include "command.h"

namespace LAMMPS_NS {

class FitHarmonicFC2 : public Command {
 public:
  FitHarmonicFC2(class LAMMPS *lmp) : Command(lmp) {}
  void command(int, char **) override;
};

}    // namespace LAMMPS_NS

#endif
#endif
