// Include standard input/output library for std::cout printing to console
#include <iostream>

// Include vector library to hold roll counts (like a resizable array)
#include <vector>

// Include our Dice class declaration so we can create/use Dice objects
#include "Dice.h"

int main() {
    // Create a standard 6-sided die using the Dice constructor from Dice.app
    Dice d6(6);

    // Number of times we'll roll the die
    const int rolls = 10000;

    // Create vector of 6 integers, all initialized to 0
    // Index 0 = count of 1s, Index 1 = count of 2s, ... , Index 5 = count of 6s
    std::vector<int> counts(6, 0);

    // Loop to simiulate rolling the die 'rolls' times, initially 10,000 from above
    for (int i=0; i < rolls; ++i) {
        // Roll the die, get random number 1-6
        int result = d6.roll();
        // Store in counts: result=1 => counts[0]++, result=2 => counts[1]++, ... , result=6 => counts[5]++
        counts[result - 1]++;
    }

    // Print header showing total rolls performed
    std::cout << "D6 roll results (" << rolls << " rolls):\n";

    // Loop through results 1-6 and print counts
    for (int i = 0; i < 6; ++i) {
        // i+1 converts index back to die face (e.g. index 0 = face 1)
        std::cout << (i + 1) << ": " << counts[i] << "\n";
    }

    // return 0 = program successful completion 
    return 0;
}