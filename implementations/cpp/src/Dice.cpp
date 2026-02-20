// Includes the Dice class DECLARATION (blueprint) from Dice.h
// This lets us use Dice::Constructor and Dice::roll here
#include "Dice.h"

// Include C++ random number library for better dice rolls than rand()
#include <random>

// IMPLEMENTATION of the Dice constructor declared in Dice.h
// Dice:: means "inside the Dice Class". Matches Dice(int sides); from header.
// Uses member initializer list (: sides_(sides)) to set sides_ variable BEFORE entering body
// Empty {} body means no extra setup needed.
Dice::Dice(int sides) : sides_(sides) {}

// IMPLEMENTATION of the roll() method declared in Dice.h
// 'const' matches the header - promises not to change 'this' Dice object.
// Returns random int from 1 to sides_ (e.g., 1-6 for normal die).

// Static Variables: created once, shared across ALL Dice objects
// std::random_device rd: Hardware seed for randomness
// std:mt19937 gen(rd()): Mersenne Twister RNG seeded with rd (very good randomness)
// These only initialize once no matter how many Dice objects you create
int Dice::roll() const {
    static std::random_device rd;                       // Get true random seed once
    static std::mt19937 gen(rd());                      // Create Random generator once, seeded with rd

    std::uniform_int_distribution<> dist(1, sides_);    // Define range 1 to sides_
    return dist(gen);                                   // Generate and return random number in range
}