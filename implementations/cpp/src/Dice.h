// HEADER GUARD: Prevents this file from being included multiple times
// (avoids duplicate class errors). First checks if DICE_H is undefined.
// If not defined yet, defines it and includes the content.
// At file end, #endif closes the guard.

#ifndef DICE_H      // "If not defined DICE_H"
#define DICE_H      // Define DICE_H

// Declares a class named Dice - like a blueprint for dice objects
// Classes group data (private) and functions (public) together
class Dice {

    // PUBLIC: Accessible from outside the class (e.g., in main.cpp)
    public:

        // Constructor: Special function called when you create a Dice object
        // Takes 'sides' (e.g., 6 for normal die) and stores it
        Dice(int sides); // No body here - implemented in Dice.cpp

        // roll(): Simulates rolling the die. Returns random 1 to sides
        // const means it doesn't change the Dice object itself
        int roll() const; // Again, body in Dice.cpp

    // PRIVATE: Hidden from outside the class. Only Dice class methods can access
    private:
        // Member variable: Stores the number of sides for this die.
        // Underscore suffix (_) is a common naming convention for privates
        int sides_;
}; // End of Dice class

// Ends the header guard
#endif