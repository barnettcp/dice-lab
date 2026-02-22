// HEADER GUARD: Prevents this file from being included multiple times
// (avoids duplicate class errors). First checks if DICE_H is undefined.
// If not defined yet, defines it and includes the content.
// At file end, #endif closes the guard.

#ifndef DICE_H      // "If not defined DICE_H"
#define DICE_H      // Define DICE_H

#include <random>

// Declares a class named Dice - like a blueprint for dice objects
// Classes group data (private) and functions (public) together
class Dice {

    // PUBLIC: Accessible from outside the class (e.g., in main.cpp)
    public:

        // Constructor: creates a die with a number of sides.
        // If hasSeed is true, results are deterministic within this implementation.
        Dice(int sides, bool hasSeed = false, int seed = 0); // No body here - implemented in Dice.cpp

        // roll(): Simulates rolling the die. Returns random 1 to sides
        int roll(); // Again, body in Dice.cpp

    // PRIVATE: Hidden from outside the class. Only Dice class methods can access
    private:
        // Member variable: Stores the number of sides for this die.
        // Underscore suffix (_) is a common naming convention for privates
        int sides_;

        // RNG engine and distribution are kept on the object so each instance
        // can be deterministic when a seed is provided.
        std::mt19937 generator_;
        std::uniform_int_distribution<int> distribution_;
}; // End of Dice class

// Ends the header guard
#endif