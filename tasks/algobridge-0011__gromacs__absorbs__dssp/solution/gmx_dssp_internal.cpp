/* Native bounded DSSP analysis for GROMACS trajectories. */

#include "gmxpre.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <set>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

int gmx_dssp_internal(int argc, char* argv[]);

namespace
{

constexpr int    c_atomCount          = 4;
constexpr int    c_n                  = 0;
constexpr int    c_ca                 = 1;
constexpr int    c_c                  = 2;
constexpr int    c_o                  = 3;
constexpr double c_maxCaDistance      = 9.0;
constexpr double c_maxPeptideDistance = 2.5;
constexpr double c_minEnergy          = -9.9;
constexpr double c_coupling           = -27.888;

struct Vec3
{
    double x = 0;
    double y = 0;
    double z = 0;
};

struct Residue
{
    char        chain = 0;
    int         number = 0;
    char        insertion = 0;
    std::string name;
};

struct AtomSet
{
    std::array<bool, c_atomCount> present{};
    std::array<Vec3, c_atomCount> position{};
};

struct Frame
{
    double               time = 0;
    Vec3                  box;
    std::vector<AtomSet> atoms;
};

struct Input
{
    double               cutoff = -0.5;
    std::vector<Residue> topology;
    std::vector<Frame>   frames;
};

struct FrameResult
{
    double                                time = 0;
    std::vector<bool>                     complete;
    std::string                           codes;
    std::vector<std::array<int, 2>>       acceptorIndex;
    std::vector<std::array<double, 2>>    acceptorEnergy;
    std::vector<std::array<int, 2>>       donorIndex;
    std::vector<std::array<double, 2>>    donorEnergy;
};

struct Bridge
{
    bool             parallel = false;
    std::vector<int> first;
    std::vector<int> second;
};

[[noreturn]] void inputError(const std::string& message)
{
    throw std::runtime_error("invalid DSSP input: " + message);
}

void expectToken(std::istream& stream, const char* expected)
{
    std::string token;
    if (!(stream >> token) || token != expected)
    {
        inputError(std::string("expected '") + expected + "'");
    }
}

double readFinite(std::istream& stream, const char* label)
{
    double value = 0;
    if (!(stream >> value) || !std::isfinite(value))
    {
        inputError(std::string(label) + " must be finite");
    }
    return value;
}

int readInteger(std::istream& stream, const char* label, int minimum, int maximum)
{
    long long value = 0;
    if (!(stream >> value) || value < minimum || value > maximum)
    {
        inputError(std::string(label) + " is outside its bounded range");
    }
    return static_cast<int>(value);
}

bool standardResidue(const std::string& name)
{
    static const std::set<std::string> names = {
        "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
        "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL"
    };
    return names.count(name) != 0;
}

bool oneAlphanumeric(const std::string& value)
{
    return value.size() == 1
           && std::isalnum(static_cast<unsigned char>(value.front())) != 0;
}

Input readInput(const std::filesystem::path& path)
{
    std::ifstream stream(path);
    if (!stream)
    {
        throw std::runtime_error("cannot open input file: " + path.string());
    }
    expectToken(stream, "DSSP_INTERNAL_V1");
    expectToken(stream, "energy_cutoff");
    const double cutoff = readFinite(stream, "energy_cutoff");
    if (cutoff < -2.0 || cutoff > -0.1)
    {
        inputError("energy_cutoff must be in [-2, -0.1]");
    }
    expectToken(stream, "residues");
    const int residueCount = readInteger(stream, "residue count", 1, 500);
    expectToken(stream, "frames");
    const int frameCount = readInteger(stream, "frame count", 1, 64);
    if (residueCount * frameCount > 10000)
    {
        inputError("frame-residue product exceeds 10000");
    }

    std::vector<Residue> topology;
    topology.reserve(residueCount);
    std::set<std::tuple<char, int, char>> keys;
    for (int index = 0; index < residueCount; ++index)
    {
        expectToken(stream, "residue");
        std::string chain;
        std::string insertion;
        std::string name;
        int number = 0;
        if (!(stream >> chain >> number >> insertion >> name))
        {
            inputError("incomplete residue topology");
        }
        if (!oneAlphanumeric(chain) || number < -999 || number > 9999
            || !(insertion == "_" || oneAlphanumeric(insertion)) || !standardResidue(name))
        {
            inputError("invalid residue topology");
        }
        const char insertionCode = insertion == "_" ? '\0' : insertion.front();
        const auto key = std::make_tuple(chain.front(), number, insertionCode);
        if (!keys.insert(key).second)
        {
            inputError("duplicate residue key");
        }
        topology.push_back({ chain.front(), number, insertionCode, name });
    }

    std::vector<Frame> frames;
    frames.reserve(frameCount);
    for (int frameIndex = 0; frameIndex < frameCount; ++frameIndex)
    {
        expectToken(stream, "frame");
        Frame frame;
        frame.time = readFinite(stream, "frame time");
        expectToken(stream, "box");
        frame.box = { readFinite(stream, "box x"), readFinite(stream, "box y"),
                      readFinite(stream, "box z") };
        const std::array<double, 3> box = { frame.box.x, frame.box.y, frame.box.z };
        const bool allZero = std::all_of(box.begin(), box.end(), [](double value) {
            return value == 0.0;
        });
        const bool allPeriodic = std::all_of(box.begin(), box.end(), [](double value) {
            return value >= 0.4;
        });
        if (!allZero && !allPeriodic)
        {
            inputError("box dimensions must be all zero or all at least 0.4 nm");
        }
        frame.atoms.reserve(residueCount);
        for (int residueIndex = 0; residueIndex < residueCount; ++residueIndex)
        {
            expectToken(stream, "atoms");
            AtomSet group;
            int presentCount = 0;
            for (int atom = 0; atom < c_atomCount; ++atom)
            {
                const int flag = readInteger(stream, "atom presence flag", 0, 1);
                group.present[atom] = flag == 1;
                if (flag == 1)
                {
                    ++presentCount;
                    group.position[atom] = {
                        readFinite(stream, "atom x"), readFinite(stream, "atom y"),
                        readFinite(stream, "atom z")
                    };
                }
            }
            if (presentCount == 0)
            {
                inputError("a residue must contain at least one backbone atom");
            }
            frame.atoms.push_back(group);
        }
        frames.push_back(std::move(frame));
    }
    std::string trailing;
    if (stream >> trailing)
    {
        inputError("unexpected trailing token");
    }
    return { cutoff, std::move(topology), std::move(frames) };
}

Vec3 subtract(const Vec3& first, const Vec3& second)
{
    return { static_cast<float>(first.x) - static_cast<float>(second.x),
             static_cast<float>(first.y) - static_cast<float>(second.y),
             static_cast<float>(first.z) - static_cast<float>(second.z) };
}

Vec3 add(const Vec3& first, const Vec3& second)
{
    return { static_cast<float>(first.x) + static_cast<float>(second.x),
             static_cast<float>(first.y) + static_cast<float>(second.y),
             static_cast<float>(first.z) + static_cast<float>(second.z) };
}

Vec3 scale(const Vec3& value, double factor)
{
    const float multiplier = static_cast<float>(factor);
    return { static_cast<float>(value.x) * multiplier,
             static_cast<float>(value.y) * multiplier,
             static_cast<float>(value.z) * multiplier };
}

float dot(const Vec3& first, const Vec3& second)
{
    return static_cast<float>(first.x) * static_cast<float>(second.x)
           + static_cast<float>(first.y) * static_cast<float>(second.y)
           + static_cast<float>(first.z) * static_cast<float>(second.z);
}

float norm(const Vec3& value)
{
    return std::sqrt(dot(value, value));
}

float distance(const Vec3& first, const Vec3& second)
{
    return norm(subtract(first, second));
}

bool periodic(const Vec3& box)
{
    return box.x > 0;
}

Vec3 nearestImage(const Vec3& value, const Vec3& anchor, const Vec3& box)
{
    if (!periodic(box))
    {
        return value;
    }
    return { value.x + std::round((anchor.x - value.x) / box.x) * box.x,
             value.y + std::round((anchor.y - value.y) / box.y) * box.y,
             value.z + std::round((anchor.z - value.z) / box.z) * box.z };
}

Vec3 legacyCoordinate(const Vec3& value)
{
    // The locked reference receives coordinates through the PDB 8.3 fields.
    // Preserve that observable coordinate precision before doing DSSP geometry.
    return { std::round(value.x * 1000.0) / 1000.0,
             std::round(value.y * 1000.0) / 1000.0,
             std::round(value.z * 1000.0) / 1000.0 };
}

bool isComplete(const AtomSet& atoms)
{
    return std::all_of(atoms.present.begin(), atoms.present.end(), [](bool value) {
        return value;
    });
}

std::vector<AtomSet> unwrap(const std::vector<Residue>& topology, const Frame& frame)
{
    std::vector<AtomSet> output = frame.atoms;
    bool havePrevious = false;
    Vec3 previousCarbon;
    char previousChain = 0;
    for (std::size_t index = 0; index < output.size(); ++index)
    {
        AtomSet& atoms = output[index];
        if (topology[index].chain != previousChain)
        {
            havePrevious = false;
        }
        previousChain = topology[index].chain;
        if (!isComplete(atoms))
        {
            havePrevious = false;
            for (int atom = 0; atom < c_atomCount; ++atom)
            {
                const Vec3& value = atoms.position[atom];
                atoms.position[atom] = legacyCoordinate(
                        { value.x * 10.0, value.y * 10.0, value.z * 10.0 });
            }
            continue;
        }
        Vec3 nitrogen = havePrevious
                                ? nearestImage(atoms.position[c_n], previousCarbon, frame.box)
                                : atoms.position[c_n];
        Vec3 alpha = nearestImage(atoms.position[c_ca], nitrogen, frame.box);
        Vec3 carbon = nearestImage(atoms.position[c_c], alpha, frame.box);
        Vec3 oxygen = nearestImage(atoms.position[c_o], carbon, frame.box);
        atoms.position[c_n]  = legacyCoordinate(
                { nitrogen.x * 10.0, nitrogen.y * 10.0, nitrogen.z * 10.0 });
        atoms.position[c_ca] = legacyCoordinate(
                { alpha.x * 10.0, alpha.y * 10.0, alpha.z * 10.0 });
        atoms.position[c_c]  = legacyCoordinate(
                { carbon.x * 10.0, carbon.y * 10.0, carbon.z * 10.0 });
        atoms.position[c_o]  = legacyCoordinate(
                { oxygen.x * 10.0, oxygen.y * 10.0, oxygen.z * 10.0 });
        previousCarbon = carbon;
        havePrevious = true;
    }
    return output;
}

double roundMilli(double value)
{
    return std::round(value * 1000.0) / 1000.0;
}

void record(std::vector<std::array<int, 2>>& partners,
            std::vector<std::array<double, 2>>& energies,
            int owner,
            int partner,
            double energy)
{
    if (energy < energies[owner][0])
    {
        partners[owner][1] = partners[owner][0];
        energies[owner][1] = energies[owner][0];
        partners[owner][0] = partner;
        energies[owner][0] = energy;
    }
    else if (energy < energies[owner][1])
    {
        partners[owner][1] = partner;
        energies[owner][1] = energy;
    }
}

FrameResult analyzeFrame(const Input& input, const Frame& frame)
{
    const int n = static_cast<int>(input.topology.size());
    const auto atoms = unwrap(input.topology, frame);
    FrameResult result;
    result.time = frame.time;
    result.complete.resize(n, false);
    result.codes.assign(n, 'C');
    result.acceptorIndex.assign(n, { -1, -1 });
    result.acceptorEnergy.assign(n, { 0.0, 0.0 });
    result.donorIndex.assign(n, { -1, -1 });
    result.donorEnergy.assign(n, { 0.0, 0.0 });
    for (int i = 0; i < n; ++i)
    {
        result.complete[i] = isComplete(atoms[i]);
    }
    std::vector<int> compactRank(n, -1);
    std::vector<int> completeOrder;
    std::vector<bool> chainStart(n, false);
    for (int i = 0; i < n; ++i)
    {
        if (result.complete[i])
        {
            completeOrder.push_back(i);
            if (completeOrder.size() > 1)
            {
                const int previous = completeOrder[completeOrder.size() - 2];
                chainStart[i] = input.topology[i].chain != input.topology[previous].chain;
            }
        }
    }
    std::fill(compactRank.begin(), compactRank.end(), -1);
    std::vector<int> analysisOrder;
    for (int i : completeOrder)
    {
        if (!chainStart[i])
        {
            compactRank[i] = static_cast<int>(analysisOrder.size());
            analysisOrder.push_back(i);
        }
    }

    std::vector<int> internal(n, 0);
    int counter = 0;
    for (int i = 0; i < n; ++i)
    {
        ++counter;
        if (i > 0
            && (!result.complete[i - 1] || !result.complete[i]
                || distance(atoms[i - 1].position[c_c], atoms[i].position[c_n])
                           > c_maxPeptideDistance))
        {
            ++counter;
        }
        internal[i] = counter;
    }

    auto uninterrupted = [&](int first, int last) {
        if (first < 0 || last >= n || first > last
            || input.topology[first].chain != input.topology[last].chain)
        {
            return false;
        }
        for (int i = first; i <= last; ++i)
        {
            if (!result.complete[i] || chainStart[i]
                || (i > first && internal[i] - internal[i - 1] != 1))
            {
                return false;
            }
        }
        return true;
    };

    std::vector<Vec3> hydrogen(n);
    std::vector<bool> hasHydrogen(n, false);
    for (std::size_t compact = 1; compact < analysisOrder.size(); ++compact)
    {
        const int i = analysisOrder[compact];
        const int previous = analysisOrder[compact - 1];
        if (input.topology[i].name == "PRO")
        {
            continue;
        }
        const Vec3 direction = subtract(atoms[previous].position[c_c],
                                        atoms[previous].position[c_o]);
        const float length = norm(direction);
        if (!(length > 0))
        {
            throw std::runtime_error("degenerate preceding C-O bond");
        }
        hydrogen[i] = add(atoms[i].position[c_n], scale(direction, 1.0 / length));
        hasHydrogen[i] = true;
    }

    auto calculateBond = [&](int donor, int acceptor) {
        double energy = 0.0;
        if (hasHydrogen[donor])
        {
            const double ho = distance(hydrogen[donor], atoms[acceptor].position[c_o]);
            const double hc = distance(hydrogen[donor], atoms[acceptor].position[c_c]);
            const double nc = distance(atoms[donor].position[c_n], atoms[acceptor].position[c_c]);
            const double no = distance(atoms[donor].position[c_n], atoms[acceptor].position[c_o]);
            if (std::min({ ho, hc, nc, no }) < 0.5)
            {
                energy = c_minEnergy;
            }
            else
            {
                energy = c_coupling / ho - c_coupling / hc
                         + c_coupling / nc - c_coupling / no;
                energy = std::max(c_minEnergy, roundMilli(energy));
            }
        }
        record(result.acceptorIndex, result.acceptorEnergy, donor, acceptor, energy);
        record(result.donorIndex, result.donorEnergy, acceptor, donor, energy);
    };

    std::vector<std::pair<int, int>> nearby;
    for (int i = 0; i < n - 1; ++i)
    {
        if (!result.complete[i] || chainStart[i])
        {
            continue;
        }
        for (int j = i + 1; j < n; ++j)
        {
            if (result.complete[j] && !chainStart[j]
                && distance(atoms[i].position[c_ca], atoms[j].position[c_ca])
                           <= c_maxCaDistance)
            {
                nearby.emplace_back(i, j);
                calculateBond(i, j);
                if (compactRank[j] != compactRank[i] + 1)
                {
                    calculateBond(j, i);
                }
            }
        }
    }

    auto hasBond = [&](int donor, int acceptor) {
        for (int rank = 0; rank < 2; ++rank)
        {
            if (result.acceptorIndex[donor][rank] == acceptor
                && result.acceptorEnergy[donor][rank] < input.cutoff)
            {
                return true;
            }
        }
        return false;
    };

    auto bridgeKind = [&](int i, int j) {
        if (i == 0 || i + 1 >= n || j == 0 || j + 1 >= n
            || !uninterrupted(i - 1, i + 1) || !uninterrupted(j - 1, j + 1))
        {
            return 0;
        }
        if ((hasBond(i + 1, j) && hasBond(j, i - 1))
            || (hasBond(j + 1, i) && hasBond(i, j - 1)))
        {
            return 1;
        }
        if ((hasBond(i + 1, j - 1) && hasBond(j + 1, i - 1))
            || (hasBond(j, i) && hasBond(i, j)))
        {
            return 2;
        }
        return 0;
    };

    std::vector<Bridge> bridges;
    for (const auto& pair : nearby)
    {
        const int i = pair.first;
        const int j = pair.second;
        const int kind = bridgeKind(i, j);
        if (kind == 0)
        {
            continue;
        }
        const bool parallel = kind == 1;
        bool attached = false;
        for (Bridge& bridge : bridges)
        {
            if (bridge.parallel != parallel || i != bridge.first.back() + 1)
            {
                continue;
            }
            if (parallel && j == bridge.second.back() + 1)
            {
                bridge.first.push_back(i);
                bridge.second.push_back(j);
                attached = true;
                break;
            }
            if (!parallel && j == bridge.second.front() - 1)
            {
                bridge.first.push_back(i);
                bridge.second.insert(bridge.second.begin(), j);
                attached = true;
                break;
            }
        }
        if (!attached)
        {
            bridges.push_back({ parallel, { i }, { j } });
        }
    }
    std::sort(bridges.begin(), bridges.end(), [&](const Bridge& left, const Bridge& right) {
        return std::make_pair(input.topology[left.first.front()].chain, left.first.front())
               < std::make_pair(input.topology[right.first.front()].chain,
                                right.first.front());
    });

    for (std::size_t a = 0; a < bridges.size(); ++a)
    {
        for (std::size_t b = a + 1; b < bridges.size();)
        {
            Bridge& left = bridges[a];
            Bridge& right = bridges[b];
            const int ibi = left.first.front();
            const int iei = left.first.back();
            const int jbi = left.second.front();
            const int jei = left.second.back();
            const int ibj = right.first.front();
            const int iej = right.first.back();
            const int jbj = right.second.front();
            const int jej = right.second.back();
            const bool skip = left.parallel != right.parallel
                              || !uninterrupted(std::min(ibi, ibj), std::max(iei, iej))
                              || !uninterrupted(std::min(jbi, jbj), std::max(jei, jej))
                              || ibj < iei || ibj - iei >= 6
                              || (iei >= ibj && ibi <= iej);
            bool bulge = false;
            if (!skip && left.parallel && jbj >= jei)
            {
                bulge = (jbj - jei < 6 && ibj - iei < 3) || jbj - jei < 3;
            }
            else if (!skip && !left.parallel && jbi >= jej)
            {
                bulge = (jbi - jej < 6 && ibj - iei < 3) || jbi - jej < 3;
            }
            if (bulge)
            {
                left.first.insert(left.first.end(), right.first.begin(), right.first.end());
                if (left.parallel)
                {
                    left.second.insert(left.second.end(), right.second.begin(), right.second.end());
                }
                else
                {
                    left.second.insert(left.second.begin(), right.second.begin(), right.second.end());
                }
                bridges.erase(bridges.begin() + static_cast<std::ptrdiff_t>(b));
            }
            else
            {
                ++b;
            }
        }
    }

    for (const Bridge& bridge : bridges)
    {
        const char code = bridge.first.size() > 1 ? 'E' : 'B';
        for (const auto& endpoints : { std::make_pair(bridge.first.front(), bridge.first.back()),
                                       std::make_pair(bridge.second.front(), bridge.second.back()) })
        {
            for (int i = endpoints.first; i <= endpoints.second; ++i)
            {
                if (result.codes[i] != 'E')
                {
                    result.codes[i] = code;
                }
            }
        }
    }

    std::array<std::vector<int>, 3> flags = {
        std::vector<int>(n, 0), std::vector<int>(n, 0), std::vector<int>(n, 0)
    };
    const std::array<int, 3> strides = { 3, 4, 5 };
    for (int helix = 0; helix < 3; ++helix)
    {
        const int stride = strides[helix];
        for (int i = 0; i < n - stride; ++i)
        {
            if (uninterrupted(i, i + stride) && hasBond(i + stride, i))
            {
                flags[helix][i + stride] = 2;
                for (int middle = i + 1; middle < i + stride; ++middle)
                {
                    if (flags[helix][middle] == 0)
                    {
                        flags[helix][middle] = 4;
                    }
                }
                flags[helix][i] = flags[helix][i] == 2 ? 3 : 1;
            }
        }
    }

    std::vector<bool> bend(n, false);
    for (int i = 2; i < n - 2; ++i)
    {
        if (uninterrupted(i - 2, i + 2)
            && input.topology[i - 2].number + 4 == input.topology[i + 2].number)
        {
            const Vec3 first = subtract(atoms[i].position[c_ca], atoms[i - 2].position[c_ca]);
            const Vec3 second = subtract(atoms[i + 2].position[c_ca], atoms[i].position[c_ca]);
            const double denominator = norm(first) * norm(second);
            if (denominator > 0)
            {
                const double cosine = std::clamp(dot(first, second) / denominator, -1.0, 1.0);
                bend[i] = std::acos(cosine) * 180.0 / std::acos(-1.0) > 70.0;
            }
        }
    }
    auto isStart = [](int value) { return value == 1 || value == 3; };
    for (int i = 1; i < n - 4; ++i)
    {
        if (isStart(flags[1][i]) && isStart(flags[1][i - 1]))
        {
            for (int j = i; j < i + 4; ++j)
            {
                result.codes[j] = 'H';
            }
        }
    }
    for (int i = 1; i < n - 3; ++i)
    {
        bool allowed = true;
        for (int j = i; j < i + 3; ++j)
        {
            allowed = allowed && (result.codes[j] == 'C' || result.codes[j] == 'G');
        }
        if (allowed && isStart(flags[0][i]) && isStart(flags[0][i - 1]))
        {
            for (int j = i; j < i + 3; ++j)
            {
                result.codes[j] = 'G';
            }
        }
    }
    for (int i = 1; i < n - 5; ++i)
    {
        bool allowed = true;
        for (int j = i; j < i + 5; ++j)
        {
            allowed = allowed
                      && (result.codes[j] == 'C' || result.codes[j] == 'I'
                          || result.codes[j] == 'H');
        }
        if (allowed && isStart(flags[2][i]) && isStart(flags[2][i - 1]))
        {
            for (int j = i; j < i + 5; ++j)
            {
                result.codes[j] = 'I';
            }
        }
    }
    for (int i = 1; i < n - 1; ++i)
    {
        if (result.codes[i] != 'C' || !result.complete[i])
        {
            continue;
        }
        bool turn = false;
        for (int helix = 0; helix < 3 && !turn; ++helix)
        {
            for (int offset = 1; offset < strides[helix]; ++offset)
            {
                if (i >= offset && isStart(flags[helix][i - offset]))
                {
                    turn = true;
                    break;
                }
            }
        }
        if (turn)
        {
            result.codes[i] = 'T';
        }
        else if (bend[i])
        {
            result.codes[i] = 'S';
        }
    }

    for (int i = 0; i < n; ++i)
    {
        if (!result.complete[i])
        {
            result.codes[i] = 'C';
            result.acceptorIndex[i] = { -1, -1 };
            result.acceptorEnergy[i] = { 0.0, 0.0 };
            result.donorIndex[i] = { -1, -1 };
            result.donorEnergy[i] = { 0.0, 0.0 };
        }
    }
    return result;
}

void writeIntRows(std::ostream& stream, const std::vector<std::array<int, 2>>& rows)
{
    stream << '[';
    for (std::size_t i = 0; i < rows.size(); ++i)
    {
        if (i != 0)
        {
            stream << ',';
        }
        stream << '[' << rows[i][0] << ',' << rows[i][1] << ']';
    }
    stream << ']';
}

void writeEnergyRows(std::ostream& stream, const std::vector<std::array<double, 2>>& rows)
{
    stream << std::fixed << std::setprecision(1);
    stream << '[';
    for (std::size_t i = 0; i < rows.size(); ++i)
    {
        if (i != 0)
        {
            stream << ',';
        }
        stream << '[' << rows[i][0] << ',' << rows[i][1] << ']';
    }
    stream << ']';
    stream << std::defaultfloat << std::setprecision(17);
}

void writeOutput(const std::filesystem::path& path,
                 const Input& input,
                 const std::vector<FrameResult>& results)
{
    const std::filesystem::path temporary = path.string() + ".tmp";
    std::ofstream stream(temporary, std::ios::trunc);
    if (!stream)
    {
        throw std::runtime_error("cannot open output file: " + temporary.string());
    }
    stream << std::setprecision(17)
           << "{\"schema\":\"algobridge-gromacs-dssp-result-v1\","
           << "\"energy_cutoff\":" << input.cutoff << ",\"residue_keys\":[";
    for (std::size_t i = 0; i < input.topology.size(); ++i)
    {
        if (i != 0)
        {
            stream << ',';
        }
        const Residue& residue = input.topology[i];
        stream << '\"' << residue.chain << ':' << residue.number << ':';
        if (residue.insertion != 0)
        {
            stream << residue.insertion;
        }
        stream << '\"';
    }
    stream << "],\"frames\":[";
    for (std::size_t frame = 0; frame < results.size(); ++frame)
    {
        if (frame != 0)
        {
            stream << ',';
        }
        const FrameResult& result = results[frame];
        stream << "{\"time_ps\":" << result.time << ",\"complete_backbone\":[";
        for (std::size_t i = 0; i < result.complete.size(); ++i)
        {
            if (i != 0)
            {
                stream << ',';
            }
            stream << (result.complete[i] ? "true" : "false");
        }
        stream << "],\"secondary_structure\":\"" << result.codes
               << "\",\"acceptor_index\":";
        writeIntRows(stream, result.acceptorIndex);
        stream << ",\"acceptor_energy\":";
        writeEnergyRows(stream, result.acceptorEnergy);
        stream << ",\"donor_index\":";
        writeIntRows(stream, result.donorIndex);
        stream << ",\"donor_energy\":";
        writeEnergyRows(stream, result.donorEnergy);
        stream << '}';
    }
    stream << "]}\n";
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
                 "Usage: gmx dssp-internal -f INPUT.dsspint -o OUTPUT.json\n"
                 "Assign bounded native DSSP secondary structure across frames.\n");
}

} // namespace

int gmx_dssp_internal(int argc, char* argv[])
{
    std::filesystem::path inputPath;
    std::filesystem::path outputPath;
    try
    {
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
        const Input input = readInput(inputPath);
        std::vector<FrameResult> results;
        results.reserve(input.frames.size());
        for (const Frame& frame : input.frames)
        {
            results.push_back(analyzeFrame(input, frame));
        }
        writeOutput(outputPath, input, results);
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
        std::fprintf(stderr, "dssp-internal: %s\n", error.what());
        return 1;
    }
}
