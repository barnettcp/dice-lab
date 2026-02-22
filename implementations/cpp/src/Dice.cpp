// Includes the Dice class DECLARATION (blueprint) from Dice.h
// This lets us use Dice::Constructor and Dice::roll here
#include "Dice.h"

// Include C++ random number library for better dice rolls than rand()
#include <random>

namespace {
    std::mt19937 makeGenerator(bool hasSeed, int seed) {
        if (hasSeed) {
            return std::mt19937(static_cast<std::mt19937::result_type>(seed));
        }
        std::random_device randomDevice;
        return std::mt19937(randomDevice());
    }
}

// IMPLEMENTATION of the Dice constructor declared in Dice.h
// Dice:: means "inside the Dice Class".
Dice::Dice(int sides, bool hasSeed, int seed)
    : sides_(sides),
      generator_(makeGenerator(hasSeed, seed)),
      distribution_(1, sides_) {}

// IMPLEMENTATION of the roll() method declared in Dice.h
// Returns random int from 1 to sides_ (e.g., 1-6 for normal die).
int Dice::roll() {
    return distribution_(generator_);                   // Generate and return random number in range
}