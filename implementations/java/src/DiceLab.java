import java.util.Locale;
import java.util.Random;

public final class DiceLab {
    private enum OutputFormat {
        TEXT,
        JSON,
        CSV
    }

    private static final class CliOptions {
        int rolls = -1;
        int sides = 6;
        boolean hasSeed = false;
        long seed = 0L;
        OutputFormat format = OutputFormat.TEXT;
        boolean parallel = false;
        boolean showHelp = false;
    }

    private static final class SimulationResult {
        final int totalRolls;
        final int sides;
        final long[] distribution;
        final double mean;
        final double variance;
        final double stdDev;

        SimulationResult(int totalRolls, int sides, long[] distribution, double mean, double variance, double stdDev) {
            this.totalRolls = totalRolls;
            this.sides = sides;
            this.distribution = distribution;
            this.mean = mean;
            this.variance = variance;
            this.stdDev = stdDev;
        }
    }

    public static void main(String[] args) {
        try {
            CliOptions options = parseArgs(args);

            if (options.showHelp) {
                printHelp();
                System.exit(0);
                return;
            }

            if (options.parallel) {
                throw new IllegalArgumentException("--parallel is not supported yet in Java baseline.");
            }

            SimulationResult result = runSimulation(options);
            System.out.println(renderOutput(result, options.format));
            System.exit(0);
        } catch (IllegalArgumentException ex) {
            System.err.println("Input error: " + ex.getMessage());
            System.exit(1);
        } catch (Exception ex) {
            System.err.println("Internal error: " + ex.getMessage());
            System.exit(2);
        }
    }

    private static CliOptions parseArgs(String[] args) {
        CliOptions options = new CliOptions();

        // Single forward pass keeps parsing explicit and easy to debug.
        for (int index = 0; index < args.length; index++) {
            String argument = args[index];

            if ("--help".equals(argument)) {
                options.showHelp = true;
                continue;
            }

            if ("--parallel".equals(argument)) {
                options.parallel = true;
                continue;
            }

            if (index + 1 >= args.length) {
                throw new IllegalArgumentException("Missing value for " + argument + ".");
            }

            String value = args[++index];
            switch (argument) {
                case "--rolls" -> options.rolls = parseInt(value, "--rolls");
                case "--sides" -> options.sides = parseInt(value, "--sides");
                case "--seed" -> {
                    options.seed = parseLong(value, "--seed");
                    options.hasSeed = true;
                }
                case "--format" -> options.format = parseFormat(value);
                default -> throw new IllegalArgumentException("Unsupported argument: " + argument + ".");
            }
        }

        if (options.showHelp) {
            return options;
        }

        if (options.rolls <= 0) {
            throw new IllegalArgumentException("--rolls must be greater than 0.");
        }
        if (options.sides < 2) {
            throw new IllegalArgumentException("--sides must be greater than or equal to 2.");
        }

        return options;
    }

    private static int parseInt(String value, String flagName) {
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException ex) {
            throw new IllegalArgumentException(flagName + " must be an integer.");
        }
    }

    private static long parseLong(String value, String flagName) {
        try {
            return Long.parseLong(value);
        } catch (NumberFormatException ex) {
            throw new IllegalArgumentException(flagName + " must be an integer.");
        }
    }

    private static OutputFormat parseFormat(String value) {
        return switch (value) {
            case "text" -> OutputFormat.TEXT;
            case "json" -> OutputFormat.JSON;
            case "csv" -> OutputFormat.CSV;
            default -> throw new IllegalArgumentException("--format must be one of: text, json, csv.");
        };
    }

    private static SimulationResult runSimulation(CliOptions options) {
        // Determinism rule:
        // - with --seed: deterministic within this implementation
        // - without --seed: JVM-chosen seed from system entropy/time
        Random rng = options.hasSeed ? new Random(options.seed) : new Random();

        long[] counts = new long[options.sides];
        double total = 0.0;
        double totalSquares = 0.0;

        for (int i = 0; i < options.rolls; i++) {
            // nextInt(n) returns 0..n-1, so shift by +1.
            int value = rng.nextInt(options.sides) + 1;
            counts[value - 1]++;
            double asDouble = value;
            total += asDouble;
            totalSquares += asDouble * asDouble;
        }

        double mean = total / options.rolls;
        double variance = (totalSquares / options.rolls) - (mean * mean);
        if (variance < 0.0) {
            variance = 0.0;
        }

        return new SimulationResult(
            options.rolls,
            options.sides,
            counts,
            mean,
            variance,
            Math.sqrt(variance)
        );
    }

    private static String renderOutput(SimulationResult result, OutputFormat format) {
        return switch (format) {
            case TEXT -> formatText(result);
            case JSON -> formatJson(result);
            case CSV -> formatCsv(result);
        };
    }

    private static String formatText(SimulationResult result) {
        StringBuilder output = new StringBuilder();
        output.append("DiceLab Results\n");
        output.append("Total rolls: ").append(result.totalRolls).append("\n");
        output.append("Sides: ").append(result.sides).append("\n");
        output.append("Distribution\n");
        output.append("face | count | percentage\n");

        for (int face = 1; face <= result.sides; face++) {
            long count = result.distribution[face - 1];
            double percentage = (count / (double) result.totalRolls) * 100.0;
            output.append(String.format(Locale.US, "%d | %d | %.4f%n", face, count, percentage));
        }

        output.append("\nSummary Statistics\n");
        output.append(String.format(Locale.US, "Mean: %.6f%n", result.mean));
        output.append(String.format(Locale.US, "Variance: %.6f%n", result.variance));
        output.append(String.format(Locale.US, "Std Dev: %.6f", result.stdDev));
        return output.toString();
    }

    private static String formatJson(SimulationResult result) {
        // Manual JSON keeps face keys in predictable ascending order.
        StringBuilder output = new StringBuilder();
        output.append("{\n");
        output.append("  \"total_rolls\": ").append(result.totalRolls).append(",\n");
        output.append("  \"sides\": ").append(result.sides).append(",\n");
        output.append("  \"distribution\": {\n");

        for (int face = 1; face <= result.sides; face++) {
            long count = result.distribution[face - 1];
            output.append("    \"").append(face).append("\": ").append(count);
            if (face < result.sides) {
                output.append(",");
            }
            output.append("\n");
        }

        output.append("  },\n");
        output.append(String.format(Locale.US, "  \"mean\": %.6f,%n", result.mean));
        output.append(String.format(Locale.US, "  \"variance\": %.6f,%n", result.variance));
        output.append(String.format(Locale.US, "  \"std_dev\": %.6f%n", result.stdDev));
        output.append("}");
        return output.toString();
    }

    private static String formatCsv(SimulationResult result) {
        StringBuilder output = new StringBuilder();
        output.append("face,count,percentage\n");

        for (int face = 1; face <= result.sides; face++) {
            long count = result.distribution[face - 1];
            double percentage = (count / (double) result.totalRolls) * 100.0;
            output.append(String.format(Locale.US, "%d,%d,%.4f%n", face, count, percentage));
        }

        output.append("\nsummary_metric,value\n");
        output.append("total_rolls,").append(result.totalRolls).append("\n");
        output.append("sides,").append(result.sides).append("\n");
        output.append(String.format(Locale.US, "mean,%.6f%n", result.mean));
        output.append(String.format(Locale.US, "variance,%.6f%n", result.variance));
        output.append(String.format(Locale.US, "std_dev,%.6f", result.stdDev));
        return output.toString();
    }

    private static void printHelp() {
        System.out.println("Usage: dice-lab --rolls <int> [options]");
        System.out.println();
        System.out.println("Required:");
        System.out.println("  --rolls <int>      Total number of rolls (must be > 0)");
        System.out.println();
        System.out.println("Optional:");
        System.out.println("  --sides <int>      Number of die sides (must be >= 2, default: 6)");
        System.out.println("  --seed <int>       Seed for deterministic RNG");
        System.out.println("  --format <string>  Output format: text|json|csv (default: text)");
        System.out.println("  --parallel         Request parallel mode (unsupported in baseline)");
        System.out.println("  --help             Show this help message");
        System.out.println();
        System.out.println("Example:");
        System.out.println("  dice-lab --rolls 10000 --sides 20 --seed 42 --format json");
    }
}
