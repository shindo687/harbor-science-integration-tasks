// Native bounded Potts pseudo-likelihood contact scoring for HH-suite.
// Added for the ALGOBRIDGE-0008 benchmark; no CCMpred code is linked or used.

#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

const int kStates = 21;
const int kResidues = 20;
const char *const kAlphabet = "ARNDCQEGHILKMFPSTWYV";

struct Alignment {
  std::vector<std::string> names;
  std::vector<std::vector<unsigned char> > rows;
  int length;
};

struct Options {
  std::string input;
  std::string output;
  double identity_threshold;
  double pair_factor;
  int max_iterations;
  unsigned long seed;

  Options()
      : identity_threshold(0.8), pair_factor(0.2), max_iterations(50), seed(0) {}
};

struct FitResult {
  std::vector<double> parameters;
  double objective;
  int completed_iterations;
  int evaluations;
  std::string status;
};

bool finite_number(double value) {
  return std::isfinite(value) != 0;
}

std::string trim(const std::string &text) {
  std::string::size_type first = 0;
  while (first < text.size() && (text[first] == ' ' || text[first] == '\t' ||
                                 text[first] == '\r' || text[first] == '\n')) {
    ++first;
  }
  std::string::size_type last = text.size();
  while (last > first && (text[last - 1] == ' ' || text[last - 1] == '\t' ||
                           text[last - 1] == '\r' || text[last - 1] == '\n')) {
    --last;
  }
  return text.substr(first, last - first);
}

bool valid_identifier(const std::string &name) {
  if (name.empty() || name.size() > 200) return false;
  for (std::string::const_iterator it = name.begin(); it != name.end(); ++it) {
    const unsigned char c = static_cast<unsigned char>(*it);
    if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
          (c >= '0' && c <= '9') || c == '_' || c == '.' || c == '-')) {
      return false;
    }
  }
  return true;
}

unsigned char residue_index(char residue) {
  if (residue == '-') return 20;
  const char *hit = std::find(kAlphabet, kAlphabet + kResidues, residue);
  if (hit == kAlphabet + kResidues) {
    throw std::runtime_error(std::string("unsupported aligned residue: ") + residue);
  }
  return static_cast<unsigned char>(hit - kAlphabet);
}

void append_a3m_sequence(const std::string &raw, std::vector<unsigned char> *row) {
  for (std::string::const_iterator it = raw.begin(); it != raw.end(); ++it) {
    const unsigned char c = static_cast<unsigned char>(*it);
    if (c == ' ' || c == '\t' || c == '\r') continue;
    if ((c >= 'a' && c <= 'z') || c == '.') continue;  // A3M insertion state.
    row->push_back(residue_index(static_cast<char>(c)));
  }
}

Alignment read_a3m(const std::string &path) {
  std::ifstream input(path.c_str());
  if (!input) throw std::runtime_error("cannot open input A3M: " + path);

  Alignment result;
  result.length = -1;
  std::set<std::string> seen;
  std::string current_name;
  std::vector<unsigned char> current_row;
  std::string line;

  const auto finish_record = [&]() {
    if (current_name.empty()) return;
    if (current_row.empty()) throw std::runtime_error("empty A3M sequence: " + current_name);
    if (result.length < 0) result.length = static_cast<int>(current_row.size());
    if (static_cast<int>(current_row.size()) != result.length) {
      throw std::runtime_error("A3M match-state rows have unequal lengths");
    }
    result.names.push_back(current_name);
    result.rows.push_back(current_row);
  };

  while (std::getline(input, line)) {
    if (!line.empty() && line[0] == '>') {
      finish_record();
      current_row.clear();
      std::istringstream header(line.substr(1));
      header >> current_name;
      if (!valid_identifier(current_name)) throw std::runtime_error("invalid A3M identifier");
      if (!seen.insert(current_name).second) throw std::runtime_error("duplicate A3M identifier");
    } else {
      if (current_name.empty()) {
        if (!trim(line).empty()) throw std::runtime_error("sequence data precedes first A3M header");
        continue;
      }
      append_a3m_sequence(line, &current_row);
    }
  }
  finish_record();

  if (result.rows.size() < 2 || result.rows.size() > 500) {
    throw std::runtime_error("alignment must contain 2 through 500 sequences");
  }
  if (result.length < 2 || result.length > 80) {
    throw std::runtime_error("alignment match-state length must be 2 through 80");
  }
  return result;
}

long parse_long(const std::string &text, const char *label) {
  errno = 0;
  char *tail = NULL;
  const long value = std::strtol(text.c_str(), &tail, 10);
  if (errno || tail == text.c_str() || *tail != '\0') {
    throw std::runtime_error(std::string("invalid ") + label);
  }
  return value;
}

double parse_double(const std::string &text, const char *label) {
  errno = 0;
  char *tail = NULL;
  const double value = std::strtod(text.c_str(), &tail);
  if (errno || tail == text.c_str() || *tail != '\0' || !finite_number(value)) {
    throw std::runtime_error(std::string("invalid ") + label);
  }
  return value;
}

void usage(std::ostream &out) {
  out << "Usage: hhcontacts --input ALIGNMENT.a3m --output RESULT.json "
      << "[--reweight-threshold FLOAT] [--l2 FLOAT] "
      << "[--iterations INT] [--seed INT]\n";
}

Options parse_options(int argc, char **argv) {
  Options options;
  std::set<std::string> supplied;
  for (int i = 1; i < argc; ++i) {
    const std::string key(argv[i]);
    if (key == "--help" || key == "-h") {
      usage(std::cout);
      std::exit(0);
    }
    if (key != "--input" && key != "--output" && key != "--reweight-threshold" &&
        key != "--l2" && key != "--iterations" && key != "--seed") {
      throw std::runtime_error("unknown option: " + key);
    }
    if (i + 1 >= argc) throw std::runtime_error("missing value for " + key);
    if (!supplied.insert(key).second) throw std::runtime_error("duplicate option: " + key);
    const std::string value(argv[++i]);
    if (key == "--input") options.input = value;
    else if (key == "--output") options.output = value;
    else if (key == "--reweight-threshold") options.identity_threshold = parse_double(value, "threshold");
    else if (key == "--l2") options.pair_factor = parse_double(value, "L2 factor");
    else if (key == "--iterations") {
      const long parsed = parse_long(value, "iteration count");
      if (parsed < 1 || parsed > 250) throw std::runtime_error("iterations must be in [1,250]");
      options.max_iterations = static_cast<int>(parsed);
    } else {
      const long parsed = parse_long(value, "seed");
      if (parsed < 0) throw std::runtime_error("seed must be non-negative");
      options.seed = static_cast<unsigned long>(parsed);
    }
  }
  if (options.input.empty() || options.output.empty()) throw std::runtime_error("--input and --output are required");
  if (!(options.identity_threshold > 0.0 && options.identity_threshold <= 1.0)) {
    throw std::runtime_error("reweight threshold must be in (0,1]");
  }
  if (!(options.pair_factor > 0.0 && options.pair_factor <= 10.0)) {
    throw std::runtime_error("L2 factor must be in (0,10]");
  }
  return options;
}

class PottsProblem {
 public:
  PottsProblem(const Alignment &alignment, double threshold, double pair_factor)
      : alignment_(alignment), length_(alignment.length),
        field_count_(length_ * kResidues),
        pair_offset_(field_count_ + kStates - (field_count_ % kStates)),
        pair_count_(static_cast<std::size_t>(length_) * length_ * kStates * kStates),
        weights_(alignment.rows.size(), 1.0), pair_accumulator_(pair_count_, 0.0),
        probabilities_(static_cast<std::size_t>(length_) * kStates, 0.0),
        pair_lambda_(pair_factor * (length_ - 1)), evaluations_(0) {
    calculate_weights(threshold);
  }

  std::size_t dimension() const { return static_cast<std::size_t>(pair_offset_) + pair_count_; }
  int pair_offset() const { return pair_offset_; }
  double effective_sequences() const {
    double total = 0.0;
    for (std::size_t i = 0; i < weights_.size(); ++i) total += weights_[i];
    return total;
  }
  int evaluations() const { return evaluations_; }

  std::size_t pair_index(int left_state, int left_position,
                         int right_state, int right_position) const {
    const std::size_t local =
        ((static_cast<std::size_t>(left_state) * length_ + left_position) * kStates +
         right_state) * length_ + right_position;
    return static_cast<std::size_t>(pair_offset_) + local;
  }

  std::vector<double> initial_parameters() const {
    std::vector<double> values(dimension(), 0.0);
    for (int column = 0; column < length_; ++column) {
      int count[kStates];
      std::fill(count, count + kStates, 1);
      for (std::size_t sequence = 0; sequence < alignment_.rows.size(); ++sequence) {
        ++count[alignment_.rows[sequence][column]];
      }
      const double denominator = static_cast<double>(alignment_.rows.size() + kStates);
      const double gap_log_frequency = std::log(count[kStates - 1] / denominator);
      for (int state = 0; state < kResidues; ++state) {
        values[column * kResidues + state] =
            std::log(count[state] / denominator) - gap_log_frequency;
      }
    }
    return values;
  }

  double evaluate(const std::vector<double> &values, std::vector<double> *gradient) {
    ++evaluations_;
    gradient->assign(dimension(), 0.0);
    std::fill(pair_accumulator_.begin(), pair_accumulator_.end(), 0.0);
    double objective = 0.0;

    for (std::size_t sequence = 0; sequence < alignment_.rows.size(); ++sequence) {
      const std::vector<unsigned char> &observed = alignment_.rows[sequence];
      const double sequence_weight = weights_[sequence];

      for (int state = 0; state < kStates; ++state) {
        for (int target = 0; target < length_; ++target) {
          double logit = state < kResidues ? values[target * kResidues + state] : 0.0;
          for (int context = 0; context < length_; ++context) {
            logit += values[pair_index(observed[context], context, state, target)];
          }
          probabilities_[static_cast<std::size_t>(state) * length_ + target] = logit;
        }
      }

      for (int target = 0; target < length_; ++target) {
        double partition = 0.0;
        for (int state = 0; state < kStates; ++state) {
          partition += std::exp(probabilities_[static_cast<std::size_t>(state) * length_ + target]);
        }
        const double log_partition = std::log(partition);
        const int observed_state = observed[target];
        objective += sequence_weight *
            (-probabilities_[static_cast<std::size_t>(observed_state) * length_ + target] + log_partition);
        for (int state = 0; state < kStates; ++state) {
          probabilities_[static_cast<std::size_t>(state) * length_ + target] =
              std::exp(probabilities_[static_cast<std::size_t>(state) * length_ + target] - log_partition);
        }
        for (int state = 0; state < kResidues; ++state) {
          (*gradient)[target * kResidues + state] += sequence_weight *
              (probabilities_[static_cast<std::size_t>(state) * length_ + target] -
               (state == observed_state ? 1.0 : 0.0));
        }
      }

      for (int context = 0; context < length_; ++context) {
        const int context_state = observed[context];
        for (int target = 0; target < length_; ++target) {
          const int target_state = observed[target];
          for (int state = 0; state < kStates; ++state) {
            const std::size_t global = pair_index(context_state, context, state, target);
            pair_accumulator_[global - pair_offset_] += sequence_weight *
                probabilities_[static_cast<std::size_t>(state) * length_ + target];
          }
          const std::size_t observed_global =
              pair_index(context_state, context, target_state, target);
          pair_accumulator_[observed_global - pair_offset_] -= sequence_weight;
        }
      }
    }

    for (int left_state = 0; left_state < kStates; ++left_state) {
      for (int left = 0; left < length_; ++left) {
        for (int right_state = 0; right_state < kStates; ++right_state) {
          for (int right = 0; right < length_; ++right) {
            const std::size_t direct = pair_index(left_state, left, right_state, right);
            if (left != right) {
              const std::size_t transpose = pair_index(right_state, right, left_state, left);
              (*gradient)[direct] = pair_accumulator_[direct - pair_offset_] +
                                    pair_accumulator_[transpose - pair_offset_];
            }
          }
        }
      }
    }

    for (int i = 0; i < field_count_; ++i) {
      objective += 0.01 * values[i] * values[i];
      (*gradient)[i] += 0.02 * values[i];
    }
    for (std::size_t i = pair_offset_; i < values.size(); ++i) {
      objective += 0.5 * pair_lambda_ * values[i] * values[i];
      (*gradient)[i] += 2.0 * pair_lambda_ * values[i];
    }
    if (!finite_number(objective)) throw std::runtime_error("non-finite pseudo-likelihood objective");
    return objective;
  }

 private:
  void calculate_weights(double threshold) {
    if (threshold == 1.0) return;
    std::vector<int> neighbors(alignment_.rows.size(), 0);
    const int required = static_cast<int>(std::ceil(threshold * length_));
    for (std::size_t first = 0; first < alignment_.rows.size(); ++first) {
      for (std::size_t second = first; second < alignment_.rows.size(); ++second) {
        int matches = 0;
        for (int column = 0; column < length_; ++column) {
          if (alignment_.rows[first][column] == alignment_.rows[second][column]) ++matches;
        }
        if (matches > required) {
          ++neighbors[first];
          ++neighbors[second];
        }
      }
    }
    for (std::size_t i = 0; i < weights_.size(); ++i) {
      weights_[i] = 1.0 / static_cast<double>(neighbors[i] - 1);
    }
  }

  const Alignment &alignment_;
  int length_;
  int field_count_;
  int pair_offset_;
  std::size_t pair_count_;
  std::vector<double> weights_;
  std::vector<double> pair_accumulator_;
  std::vector<double> probabilities_;
  double pair_lambda_;
  int evaluations_;
};

double dot_product(const std::vector<double> &left, const std::vector<double> &right) {
  double value = 0.0;
  for (std::size_t i = 0; i < left.size(); ++i) value += left[i] * right[i];
  return value;
}

FitResult fit(PottsProblem *problem, int max_iterations) {
  FitResult result;
  result.parameters = problem->initial_parameters();
  std::vector<double> gradient;
  std::vector<double> direction(result.parameters.size(), 0.0);
  result.objective = problem->evaluate(result.parameters, &gradient);
  result.completed_iterations = 0;
  result.status = "maximum_iterations";

  double gradient_norm = dot_product(gradient, gradient);
  const double parameter_norm = dot_product(result.parameters, result.parameters);
  if (gradient_norm <= 1e-8 || gradient_norm / parameter_norm <= 0.01) {
    result.status = "already_minimized";
    result.evaluations = problem->evaluations();
    return result;
  }

  double step = 1.0 / std::sqrt(gradient_norm);
  double previous_step = 0.0;
  double previous_slope = 0.0;
  double previous_gradient_norm = 0.0;
  double history[5] = {0.0, 0.0, 0.0, 0.0, 0.0};

  while (result.completed_iterations < max_iterations) {
    double slope = 0.0;
    if (result.completed_iterations == 0) {
      for (std::size_t i = 0; i < direction.size(); ++i) direction[i] = -gradient[i];
      slope = dot_product(direction, gradient);
    } else {
      const double scale = gradient_norm / previous_gradient_norm;
      for (std::size_t i = 0; i < direction.size(); ++i) {
        direction[i] = scale * direction[i] - gradient[i];
      }
      slope = dot_product(direction, gradient);
      step = previous_step * previous_slope / slope;
    }

    const double initial_slope = dot_product(gradient, direction);
    const double armijo_slope = initial_slope * 1e-4;
    const double initial_objective = result.objective;
    double applied_step = 0.0;
    bool accepted = false;
    for (int line_trial = 0; line_trial < 5; ++line_trial) {
      for (std::size_t i = 0; i < result.parameters.size(); ++i) {
        result.parameters[i] += (step - applied_step) * direction[i];
      }
      applied_step = step;
      const double trial_objective = problem->evaluate(result.parameters, &gradient);
      if (trial_objective <= initial_objective + step * armijo_slope &&
          dot_product(direction, gradient) < 0.2 * initial_slope) {
        result.objective = trial_objective;
        accepted = true;
        break;
      }
      step *= 0.5;
    }

    previous_gradient_norm = gradient_norm;
    gradient_norm = dot_product(gradient, gradient);
    previous_step = step;
    previous_slope = slope;
    if (!accepted) {
      result.status = "line_search_failed";
      break;
    }

    const int slot = result.completed_iterations % 5;
    if (result.completed_iterations >= 5) {
      const double relative_change = (history[slot] - result.objective) / history[slot];
      if (relative_change < 0.01) {
        result.status = "converged";
        break;
      }
    }
    history[slot] = result.objective;
    ++result.completed_iterations;
  }
  result.evaluations = problem->evaluations();
  return result;
}

std::vector<double> raw_scores(const PottsProblem &problem,
                               const std::vector<double> &parameters, int length) {
  std::vector<double> matrix(static_cast<std::size_t>(length) * length, 0.0);
  for (int left = 0; left < length; ++left) {
    for (int right = 0; right < length; ++right) {
      if (left == right) continue;
      double mean = 0.0;
      for (int a = 0; a < kStates; ++a) {
        for (int b = 0; b < kStates; ++b) {
          mean += parameters[problem.pair_index(b, left, a, right)];
        }
      }
      mean /= static_cast<double>(kStates * kStates);
      double squared = 0.0;
      for (int a = 0; a < kResidues; ++a) {
        for (int b = 0; b < kResidues; ++b) {
          const double centered = parameters[problem.pair_index(b, left, a, right)] - mean;
          squared += centered * centered;
        }
      }
      matrix[static_cast<std::size_t>(left) * length + right] = std::sqrt(squared);
    }
  }
  return matrix;
}

std::vector<double> apc_scores(const std::vector<double> &raw, int length) {
  std::vector<double> means(length, 0.0);
  double grand_mean = 0.0;
  for (int row = 0; row < length; ++row) {
    for (int column = 0; column < length; ++column) {
      const double value = raw[static_cast<std::size_t>(row) * length + column];
      means[column] += value / length;
      grand_mean += value;
    }
  }
  grand_mean /= static_cast<double>(length * length);
  if (!(grand_mean > 0.0)) throw std::runtime_error("APC is undefined for an all-zero score matrix");

  std::vector<double> corrected(raw.size(), 0.0);
  double minimum = std::numeric_limits<double>::infinity();
  for (int row = 0; row < length; ++row) {
    for (int column = 0; column < length; ++column) {
      corrected[static_cast<std::size_t>(row) * length + column] =
          raw[static_cast<std::size_t>(row) * length + column] -
          means[row] * means[column] / grand_mean;
      if (row < column) minimum = std::min(minimum,
          corrected[static_cast<std::size_t>(row) * length + column]);
    }
  }
  for (int row = 0; row < length; ++row) {
    for (int column = 0; column < length; ++column) {
      const std::size_t index = static_cast<std::size_t>(row) * length + column;
      corrected[index] = row == column ? 0.0 : corrected[index] - minimum;
    }
  }
  return corrected;
}

struct Contact {
  int first;
  int second;
  double score;
};

std::vector<Contact> top_contacts(const std::vector<double> &matrix, int length) {
  std::vector<Contact> contacts;
  for (int first = 0; first < length; ++first) {
    for (int second = first + 5; second < length; ++second) {
      Contact contact = {first + 1, second + 1,
                         matrix[static_cast<std::size_t>(first) * length + second]};
      contacts.push_back(contact);
    }
  }
  std::sort(contacts.begin(), contacts.end(), [](const Contact &left, const Contact &right) {
    if (left.score != right.score) return left.score > right.score;
    if (left.first != right.first) return left.first < right.first;
    return left.second < right.second;
  });
  if (contacts.size() > static_cast<std::size_t>(length)) contacts.resize(length);
  return contacts;
}

void write_matrix(std::ostream &out, const std::vector<double> &matrix, int length) {
  out << '[';
  for (int row = 0; row < length; ++row) {
    if (row) out << ',';
    out << '[';
    for (int column = 0; column < length; ++column) {
      if (column) out << ',';
      out << matrix[static_cast<std::size_t>(row) * length + column];
    }
    out << ']';
  }
  out << ']';
}

void write_result(const Options &options, const Alignment &alignment,
                  double neff, const FitResult &fit_result,
                  const std::vector<double> &raw, const std::vector<double> &apc) {
  std::ofstream out(options.output.c_str());
  if (!out) throw std::runtime_error("cannot open output JSON: " + options.output);
  out << std::setprecision(17);
  out << "{\n  \"schema_version\":1,\n";
  out << "  \"length\":" << alignment.length << ",\n";
  out << "  \"sequence_count\":" << alignment.rows.size() << ",\n";
  out << "  \"effective_sequences\":" << neff << ",\n";
  out << "  \"parameters\":{\"reweight_threshold\":" << options.identity_threshold
      << ",\"l2_factor\":" << options.pair_factor
      << ",\"iterations\":" << options.max_iterations
      << ",\"seed\":" << options.seed << "},\n";
  out << "  \"diagnostics\":{\"objective\":" << fit_result.objective
      << ",\"iterations_completed\":" << fit_result.completed_iterations
      << ",\"evaluations\":" << fit_result.evaluations
      << ",\"status\":\"" << fit_result.status << "\"},\n";
  out << "  \"raw_score\":";
  write_matrix(out, raw, alignment.length);
  out << ",\n  \"apc_score\":";
  write_matrix(out, apc, alignment.length);
  const std::vector<Contact> contacts = top_contacts(apc, alignment.length);
  out << ",\n  \"top_contacts\":[";
  for (std::size_t i = 0; i < contacts.size(); ++i) {
    if (i) out << ',';
    out << "{\"i\":" << contacts[i].first << ",\"j\":" << contacts[i].second
        << ",\"score\":" << contacts[i].score << '}';
  }
  out << "]\n}\n";
  if (!out) throw std::runtime_error("failed while writing output JSON");
}

}  // namespace

int main(int argc, char **argv) {
  try {
    const Options options = parse_options(argc, argv);
    const Alignment alignment = read_a3m(options.input);
    PottsProblem problem(alignment, options.identity_threshold, options.pair_factor);
    const FitResult fitted = fit(&problem, options.max_iterations);
    const std::vector<double> raw = raw_scores(problem, fitted.parameters, alignment.length);
    const std::vector<double> corrected = apc_scores(raw, alignment.length);
    write_result(options, alignment, problem.effective_sequences(), fitted, raw, corrected);
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "hhcontacts: " << error.what() << '\n';
    return 2;
  }
}
