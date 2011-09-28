"""Miscellaneous modules

Contains useful modules that don't belong into any of the
other Crypto.* subpackages.

Crypto.Util.number        Number-theoretic functions (primality testing, etc.)
Crypto.Util.randpool      Random number generation
Crypto.Util.RFC1751       Converts between 128-bit keys and human-readable
                          strings of words.

"""

__all__ = ['randpool', 'RFC1751', 'number']

__revision__ = "$Id: __init__.py,v 29691e0c92d1 2011/09/28 11:16:52 dinko $"

