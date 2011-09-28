
# Just use the SHA module from the Python standard library

__revision__ = "$Id: SHA.py,v 29691e0c92d1 2011/09/28 11:16:52 dinko $"

from sha import *
import sha
if hasattr(sha, 'digestsize'):
    digest_size = digestsize
    del digestsize
del sha
