// Include standard input/output library for console output
#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>
#include <cmath>
#include <stdexcept>

// Include our Dice class declaration so we can create/use Dice objects
#include "Dice.h"

namespace {
    struct CliOptions {
        int rolls = 0;
        int sides = 6;
        bool hasSeed = false;
        int seed = 0;
        std::string format = "text";
        bool parallel = false;
        bool showHelp = false;
    };

    struct SimulationResult {
        int totalRolls;
        int sides;
        std::vector<long long> distribution;
        double mean;
        double variance;
        double stdDev;
    };

    void printHelp() {
        std::cout
            << "Usage: dice-lab --rolls <int> [options]\n"
            << "\n"
            << "Required:\n"
            << "  --rolls <int>      Total number of rolls (must be > 0)\n"
            << "\n"
            << "Optional:\n"
            << "  --sides <int>      Number of die sides (must be >= 2, default: 6)\n"
            << "  --seed <int>       Seed for deterministic RNG\n"
            << "  --format <string>  Output format: text|json|csv (default: text)\n"
            << "  --parallel         Request parallel mode (unsupported in this baseline)\n"
            << "  --help             Show this help message\n"
            << "\n"
            << "Example:\n"
            << "  dice-lab --rolls 10000 --sides 20 --seed 42 --format json\n";
    }

    int parseInt(const std::string& value, const std::string& flagName) {
        size_t parsedLength = 0;
        int parsedValue = 0;
        try {
            parsedValue = std::stoi(value, &parsedLength);
        } catch (...) {
            throw std::invalid_argument(flagName + " must be an integer.");
        }

        if (parsedLength != value.size()) {
            throw std::invalid_argument(flagName + " must be an integer.");
        }

        return parsedValue;
    }

    CliOptions parseArgs(int argc, char* argv[]) {
        CliOptions options;
        bool rollsProvided = false;

        for (int index = 1; index < argc; ++index) {
            const std::string argument = argv[index];

            if (argument == "--help") {
                options.showHelp = true;
                continue;
            }

            if (argument == "--parallel") {
                options.parallel = true;
                continue;
            }

            if (index + 1 >= argc) {
                throw std::invalid_argument("Missing value for " + argument + ".");
            }

            const std::string value = argv[++index];
            if (argument == "--rolls") {
                options.rolls = parseInt(value, "--rolls");
                rollsProvided = true;
            } else if (argument == "--sides") {
                options.sides = parseInt(value, "--sides");
            } else if (argument == "--seed") {
                options.seed = parseInt(value, "--seed");
                options.hasSeed = true;
            } else if (argument == "--format") {
                options.format = value;
            } else {
                throw std::invalid_argument("Unsupported argument: " + argument + ".");
            }
        }

        if (options.showHelp) {
            return options;
        }

        if (!rollsProvided) {
            throw std::invalid_argument("Missing required argument: --rolls");
        }
        if (options.rolls <= 0) {
            throw std::invalid_argument("--rolls must be greater than 0.");
        }
        if (options.sides < 2) {
            throw std::invalid_argument("--sides must be greater than or equal to 2.");
        }
        if (options.format != "text" && options.format != "json" && options.format != "csv") {
            throw std::invalid_argument("--format must be one of: text, json, csv.");
        }

        return options;
    }

    SimulationResult runSimulation(const CliOptions& options) {
        Dice dice(options.sides, options.hasSeed, options.seed);
        std::vector<long long> counts(static_cast<size_t>(options.sides), 0);

        double total = 0.0;
        double totalSquares = 0.0;

        for (int iteration = 0; iteration < options.rolls; ++iteration) {
            const int value = dice.roll();
            counts[static_cast<size_t>(value - 1)]++;
            total += static_cast<double>(value);
            totalSquares += static_cast<double>(value) * static_cast<double>(value);
        }

        const double mean = total / static_cast<double>(options.rolls);
        double variance = (totalSquares / static_cast<double>(options.rolls)) - (mean * mean);
        if (variance < 0.0) {
            variance = 0.0;
        }

        return SimulationResult{
            options.rolls,
            options.sides,
            counts,
            mean,
            variance,
            std::sqrt(variance)
        };
    }

    std::string formatText(const SimulationResult& result) {
        std::ostringstream output;
        output << "DiceLab Results\n";
        output << "Total rolls: " << result.totalRolls << "\n";
        output << "Sides: " << result.sides << "\n";
        output << "Distribution\n";
        output << "face | count | percentage\n";

        output << std::fixed << std::setprecision(4);
        for (int face = 1; face <= result.sides; ++face) {
            const long long count = result.distribution[static_cast<size_t>(face - 1)];
            const double percentage = (static_cast<double>(count) / static_cast<double>(result.totalRolls)) * 100.0;
            output << face << " | " << count << " | " << percentage << "\n";
        }

        output << "\nSummary Statistics\n";
        output << std::fixed << std::setprecision(6);
        output << "Mean: " << result.mean << "\n";
        output << "Variance: " << result.variance << "\n";
        output << "Std Dev: " << result.stdDev;
        return output.str();
    }

    std::string formatJson(const SimulationResult& result) {
        std::ostringstream output;
        output << "{\n";
        output << "  \"total_rolls\": " << result.totalRolls << ",\n";
        output << "  \"sides\": " << result.sides << ",\n";
        output << "  \"distribution\": {\n";

        for (int face = 1; face <= result.sides; ++face) {
            const long long count = result.distribution[static_cast<size_t>(face - 1)];
            output << "    \"" << face << "\": " << count;
            if (face < result.sides) {
                output << ",";
            }
            output << "\n";
        }

        output << "  },\n";
        output << std::fixed << std::setprecision(6);
        output << "  \"mean\": " << result.mean << ",\n";
        output << "  \"variance\": " << result.variance << ",\n";
        output << "  \"std_dev\": " << result.stdDev << "\n";
        output << "}";
        return output.str();
    }

    std::string formatCsv(const SimulationResult& result) {
        std::ostringstream output;
        output << "face,count,percentage\n";

        output << std::fixed << std::setprecision(4);
        for (int face = 1; face <= result.sides; ++face) {
            const long long count = result.distribution[static_cast<size_t>(face - 1)];
            const double percentage = (static_cast<double>(count) / static_cast<double>(result.totalRolls)) * 100.0;
            output << face << "," << count << "," << percentage << "\n";
        }

        output << "\nsummary_metric,value\n";
        output << "total_rolls," << result.totalRolls << "\n";
        output << "sides," << result.sides << "\n";
        output << std::fixed << std::setprecision(6);
        output << "mean," << result.mean << "\n";
        output << "variance," << result.variance << "\n";
        output << "std_dev," << result.stdDev;
        return output.str();
    }

    std::string renderOutput(const SimulationResult& result, const std::string& format) {
        if (format == "text") {
            return formatText(result);
        }
        if (format == "json") {
            return formatJson(result);
        }
        if (format == "csv") {
            return formatCsv(result);
        }
        throw std::invalid_argument("Unsupported format: " + format);
    }
}

int main(int argc, char* argv[]) {
    try {
        const CliOptions options = parseArgs(argc, argv);

        if (options.showHelp) {
            printHelp();
            return 0;
        }

        if (options.parallel) {
            throw std::invalid_argument("--parallel is not supported yet in C++ baseline.");
        }

        const SimulationResult result = runSimulation(options);
        std::cout << renderOutput(result, options.format) << "\n";
        return 0;
    } catch (const std::invalid_argument& error) {
        std::cerr << "Input error: " << error.what() << "\n";
        return 1;
    } catch (const std::exception& error) {
        std::cerr << "Internal error: " << error.what() << "\n";
        return 2;
    }
}