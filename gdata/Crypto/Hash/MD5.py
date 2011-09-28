
# Just use the MD5 module from the Python standard library

__revision__ = "$Id: MD5.py,v 29691e0c92d1 2011/09/28 11:16:52 dinko $"

from md5 import *

import md5
if hasattr(md5, 'digestsize'):
    digest_size = digestsize
    del digestsize
del md5

