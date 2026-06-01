// AlphanumComparatorFast mod by aelurum
// Original code was developed by Dot Net Perls
// For more detail visit: https://www.dotnetperls.com/alphanumeric-sorting

using System;
using System.Collections.Generic;

#if NET6_0_OR_GREATER
namespace AssetStudioGUI
{
    internal class AlphanumComparatorFastNet : IComparer<string>
    {
        public int Compare(string s1, string s2)
        {
            const int maxStackSize = 256;
            int len1 = s1.Length;
            int len2 = s2.Length;
            int marker1 = 0;
            int marker2 = 0;

            // Some buffers we can build up characters in for each chunk.
            Span<char> space1 = len1 > maxStackSize ? new char[len1] : stackalloc char[len1];
            Span<char> space2 = len2 > maxStackSize ? new char[len2] : stackalloc char[len2];

            // Walk through two the strings with two markers.
            while (marker1 < len1 && marker2 < len2)
            {
                char ch1 = s1[marker1];
                char ch2 = s2[marker2];

                int loc1 = 0;
                int loc2 = 0;
                space1.Clear();
                space2.Clear();

                // Walk through all following characters that are digits or
                // characters in BOTH strings starting at the appropriate marker.
                // Collect char arrays.
                do
                {
                    space1[loc1++] = ch1;
                    marker1++;

                    if (marker1 < len1)
                    {
                        ch1 = s1[marker1];
                    }
                    else
                    {
                        break;
                    }
                } while (char.IsDigit(ch1) == char.IsDigit(space1[0]));

                do
                {
                    space2[loc2++] = ch2;
                    marker2++;

                    if (marker2 < len2)
                    {
                        ch2 = s2[marker2];
                    }
                    else
                    {
                        break;
                    }
                } while (char.IsDigit(ch2) == char.IsDigit(space2[0]));

                // If we have collected numbers, compare them numerically.
                // Otherwise, if we have strings, compare them alphabetically.
                int result;

                if (char.IsDigit(space1[0]) && char.IsDigit(space2[0]))
                {
                    if (long.TryParse(space1, out long thisNumericChunk) &&
                        long.TryParse(space2, out long thatNumericChunk))
                    {
                        result = thisNumericChunk.CompareTo(thatNumericChunk);
                    }
                    else
                    {
                        result = MemoryExtensions.CompareTo(space1, space2, StringComparison.Ordinal);
                    }
                }
                else
                {
                    result = MemoryExtensions.CompareTo(space1, space2, StringComparison.InvariantCultureIgnoreCase);
                }

                if (result != 0)
                {
                    return result;
                }
            }
            return len1 - len2;
        }
    }
}
#endif
