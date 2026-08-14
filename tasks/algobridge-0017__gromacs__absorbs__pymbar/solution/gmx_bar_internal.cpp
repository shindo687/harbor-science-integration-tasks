/* Native bounded Bennett acceptance-ratio analysis for GROMACS. */

#include "gmxpre.h"

#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

int gmx_bar_internal(int argc, char* argv[]);

namespace
{

struct BarInput
{
    double              tolerance;
    int                 maximumIterations;
    double              initialDelta;
    std::vector<double> forward;
    std::vector<double> reverse;
};

struct BarResult
{
    double delta;
    double uncertainty;
    double overlap;
    int    iterations;
    int    evaluations;
    double residual;
};

[[noreturn]] void inputError(const std::string& message)
{
    throw std::runtime_error("invalid BAR input: " + message);
}

void expectToken(std::istream& stream, const char* expected)
{
    std::string token;
    if (!(stream >> token) || token != expected)
    {
        inputError(std::string("expected '") + expected + "'");
    }
}

double readFinite(std::istream& stream, const char* name)
{
    double value = 0.0;
    if (!(stream >> value) || !std::isfinite(value))
    {
        inputError(std::string(name) + " must be finite");
    }
    return value;
}

int readCount(std::istream& stream, const char* name, int minimum, int maximum)
{
    long long value = 0;
    if (!(stream >> value) || value < minimum || value > maximum)
    {
        inputError(std::string(name) + " is outside the bounded range");
    }
    return static_cast<int>(value);
}

std::vector<double> readWorks(std::istream& stream, int count, const char* name)
{
    std::vector<double> values;
    values.reserve(static_cast<std::size_t>(count));
    for (int index = 0; index < count; ++index)
    {
        values.push_back(readFinite(stream, name));
    }
    return values;
}

BarInput readInput(const std::filesystem::path& path)
{
    std::ifstream stream(path);
    if (!stream)
    {
        throw std::runtime_error("cannot open input file: " + path.string());
    }

    expectToken(stream, "BAR_INTERNAL_V1");
    expectToken(stream, "relative_tolerance");
    const double tolerance = readFinite(stream, "relative_tolerance");
    if (tolerance < 1.0e-15 || tolerance > 1.0e-2)
    {
        inputError("relative_tolerance is outside [1e-15, 1e-2]");
    }

    expectToken(stream, "maximum_iterations");
    const int maximumIterations = readCount(stream, "maximum_iterations", 1, 100000);
    expectToken(stream, "initial_delta_f");
    const double initialDelta = readFinite(stream, "initial_delta_f");

    expectToken(stream, "forward");
    const int forwardCount = readCount(stream, "forward count", 1, 100000);
    auto      forward      = readWorks(stream, forwardCount, "forward work");
    expectToken(stream, "reverse");
    const int reverseCount = readCount(stream, "reverse count", 1, 100000);
    auto      reverse      = readWorks(stream, reverseCount, "reverse work");

    std::string trailing;
    if (stream >> trailing)
    {
        inputError("unexpected trailing token");
    }
    return { tolerance,
             maximumIterations,
             initialDelta,
             std::move(forward),
             std::move(reverse) };
}

double logFermi(double argument)
{
    // log(1 / (1 + exp(argument))) without an overflowing exponential.
    if (argument > 0.0)
    {
        return -argument - std::log1p(std::exp(-argument));
    }
    return -std::log1p(std::exp(argument));
}

double logAdd(double left, double right)
{
    const double high = std::max(left, right);
    const double low  = std::min(left, right);
    return high + std::log1p(std::exp(low - high));
}

double logSum(const std::vector<double>& values)
{
    if (values.empty())
    {
        throw std::runtime_error("internal empty log sum");
    }
    const double high = *std::max_element(values.begin(), values.end());
    double       sum  = 0.0;
    for (double value : values)
    {
        sum += std::exp(value - high);
    }
    return high + std::log(sum);
}

std::vector<double> acceptanceLogs(const std::vector<double>& works,
                                   double                     offset,
                                   double                     sign)
{
    std::vector<double> result;
    result.reserve(works.size());
    for (double work : works)
    {
        result.push_back(logFermi(sign * (offset + work)));
    }
    return result;
}

class BarEquation
{
public:
    explicit BarEquation(const BarInput& input) :
        input_(input),
        countOffset_(std::log(static_cast<double>(input.forward.size())
                              / static_cast<double>(input.reverse.size())))
    {
    }

    double operator()(double delta) const
    {
        std::vector<double> forwardLogs;
        std::vector<double> reverseLogs;
        forwardLogs.reserve(input_.forward.size());
        reverseLogs.reserve(input_.reverse.size());
        for (double work : input_.forward)
        {
            forwardLogs.push_back(logFermi(countOffset_ + work - delta));
        }
        for (double work : input_.reverse)
        {
            reverseLogs.push_back(logFermi(-countOffset_ + work + delta));
        }
        return logSum(forwardLogs) - logSum(reverseLogs);
    }

    double countOffset() const { return countOffset_; }

private:
    const BarInput& input_;
    double          countOffset_;
};

std::pair<double, double> initialBracket(const BarInput& input,
                                         const BarEquation& equation,
                                         int*               evaluations)
{
    double scale = 1.0 + std::abs(equation.countOffset());
    for (double value : input.forward)
    {
        scale = std::max(scale, std::abs(value) + 2.0);
    }
    for (double value : input.reverse)
    {
        scale = std::max(scale, std::abs(value) + 2.0);
    }
    double center = std::clamp(input.initialDelta, -scale, scale);
    double width  = 1.0;
    for (int expansion = 0; expansion < 64; ++expansion)
    {
        const double lower      = center - width;
        const double upper      = center + width;
        const double lowerValue = equation(lower);
        const double upperValue = equation(upper);
        *evaluations += 2;
        if (lowerValue <= 0.0 && upperValue >= 0.0)
        {
            return { lower, upper };
        }
        width *= 2.0;
        if (!std::isfinite(width))
        {
            break;
        }
    }
    throw std::runtime_error("failed to bracket the BAR root");
}

double squaredMeanLog(const std::vector<double>& logs)
{
    std::vector<double> doubled;
    doubled.reserve(logs.size());
    for (double value : logs)
    {
        doubled.push_back(2.0 * value);
    }
    return logSum(doubled) - std::log(static_cast<double>(logs.size()));
}

double barUncertainty(const BarInput& input, double delta, double countOffset)
{
    const auto forwardLogs = acceptanceLogs(input.forward, countOffset - delta, 1.0);
    const auto reverseLogs = acceptanceLogs(input.reverse, -countOffset + delta, 1.0);
    const double logNf = std::log(static_cast<double>(input.forward.size()));
    const double logNr = std::log(static_cast<double>(input.reverse.size()));
    const double logMeanF  = logSum(forwardLogs) - logNf;
    const double logMeanR  = logSum(reverseLogs) - logNr;
    const double logSquareF = squaredMeanLog(forwardLogs);
    const double logSquareR = squaredMeanLog(reverseLogs);

    const double termF = std::exp(logSquareF - 2.0 * logMeanF) / input.forward.size();
    const double termR = std::exp(logSquareR - 2.0 * logMeanR) / input.reverse.size();
    double variance = termF + termR - 1.0 / input.forward.size() - 1.0 / input.reverse.size();
    const double roundoff = 128.0 * std::numeric_limits<double>::epsilon()
                            * std::max(1.0, std::abs(termF) + std::abs(termR));
    if (variance < -roundoff)
    {
        throw std::runtime_error("negative BAR variance");
    }
    variance = std::max(0.0, variance);
    return std::sqrt(variance);
}

double barOverlap(const BarInput& input, double delta)
{
    const double logNf = std::log(static_cast<double>(input.forward.size()));
    const double logNr = std::log(static_cast<double>(input.reverse.size()));
    std::vector<double> crossLogs;
    crossLogs.reserve(input.forward.size() + input.reverse.size());

    for (double work : input.forward)
    {
        const double denominator = logAdd(logNf, logNr + delta - work);
        const double logWeight0  = -denominator;
        const double logWeight1  = delta - work - denominator;
        crossLogs.push_back(logWeight0 + logWeight1);
    }
    for (double work : input.reverse)
    {
        const double denominator = logAdd(logNf - work, logNr + delta);
        const double logWeight0  = -work - denominator;
        const double logWeight1  = delta - denominator;
        crossLogs.push_back(logWeight0 + logWeight1);
    }
    const double cross = std::exp(logSum(crossLogs));
    const double scalar = (input.forward.size() + input.reverse.size()) * cross;
    return std::clamp(scalar, 0.0, 1.0);
}

BarResult solve(const BarInput& input)
{
    const BarEquation equation(input);
    int               evaluations = 0;
    auto [lower, upper] = initialBracket(input, equation, &evaluations);
    double lowerValue = equation(lower);
    double upperValue = equation(upper);
    evaluations += 2;
    double delta = 0.5 * (lower + upper);
    double value = equation(delta);
    ++evaluations;
    int iterations = 0;
    bool converged = false;
    for (iterations = 1; iterations <= input.maximumIterations; ++iterations)
    {
        delta = 0.5 * (lower + upper);
        value = equation(delta);
        ++evaluations;
        const double widthTolerance = input.tolerance * std::max(1.0, std::abs(delta));
        if (std::abs(value) <= input.tolerance || 0.5 * (upper - lower) <= widthTolerance)
        {
            converged = true;
            break;
        }
        if (value < 0.0)
        {
            lower      = delta;
            lowerValue = value;
        }
        else
        {
            upper      = delta;
            upperValue = value;
        }
    }
    (void)lowerValue;
    (void)upperValue;
    if (!converged)
    {
        throw std::runtime_error("BAR solve did not converge within maximum_iterations");
    }
    return { delta,
             barUncertainty(input, delta, equation.countOffset()),
             barOverlap(input, delta),
             iterations,
             evaluations,
             std::abs(value) };
}

void writeOutput(const std::filesystem::path& path, const BarInput& input, const BarResult& result)
{
    const std::filesystem::path temporary = path.string() + ".tmp";
    std::ofstream               stream(temporary, std::ios::trunc);
    if (!stream)
    {
        throw std::runtime_error("cannot open output file: " + temporary.string());
    }
    stream << std::setprecision(17)
           << "{\n"
           << "  \"delta_f\": " << result.delta << ",\n"
           << "  \"uncertainty\": " << result.uncertainty << ",\n"
           << "  \"overlap\": " << result.overlap << ",\n"
           << "  \"iterations\": " << result.iterations << ",\n"
           << "  \"function_evaluations\": " << result.evaluations << ",\n"
           << "  \"residual\": " << result.residual << ",\n"
           << "  \"converged\": true,\n"
           << "  \"n_forward\": " << input.forward.size() << ",\n"
           << "  \"n_reverse\": " << input.reverse.size() << "\n"
           << "}\n";
    stream.close();
    if (!stream)
    {
        std::filesystem::remove(temporary);
        throw std::runtime_error("failed while writing output file");
    }
    std::error_code error;
    std::filesystem::rename(temporary, path, error);
    if (error)
    {
        std::filesystem::remove(path, error);
        error.clear();
        std::filesystem::rename(temporary, path, error);
    }
    if (error)
    {
        std::filesystem::remove(temporary);
        throw std::runtime_error("cannot finalize output file: " + error.message());
    }
}

void printHelp()
{
    std::fprintf(stdout,
                 "Usage: gmx bar-internal -f INPUT.bar -o OUTPUT.json\n"
                 "Solve a bounded two-state Bennett acceptance-ratio problem.\n");
}

} // namespace

int gmx_bar_internal(int argc, char* argv[])
{
    std::filesystem::path inputPath;
    std::filesystem::path outputPath;
    try
    {
        // The legacy GROMACS dispatcher consumes the global -h option before
        // calling a module, so a help request arrives here with argc == 1.
        if (argc == 1)
        {
            printHelp();
            return 0;
        }
        for (int index = 1; index < argc; ++index)
        {
            const std::string option(argv[index]);
            if (option == "-h" || option == "--help")
            {
                printHelp();
                return 0;
            }
            if ((option == "-f" || option == "-o") && index + 1 < argc)
            {
                const std::filesystem::path value(argv[++index]);
                if (option == "-f")
                {
                    inputPath = value;
                }
                else
                {
                    outputPath = value;
                }
                continue;
            }
            throw std::runtime_error("unknown or incomplete command-line option: " + option);
        }
        if (inputPath.empty() || outputPath.empty())
        {
            throw std::runtime_error("both -f and -o are required");
        }
        const BarInput  input  = readInput(inputPath);
        const BarResult result = solve(input);
        writeOutput(outputPath, input, result);
        return 0;
    }
    catch (const std::exception& error)
    {
        if (!outputPath.empty())
        {
            std::error_code ignored;
            std::filesystem::remove(outputPath, ignored);
            std::filesystem::remove(outputPath.string() + ".tmp", ignored);
        }
        std::fprintf(stderr, "bar-internal: %s\n", error.what());
        return 1;
    }
}
