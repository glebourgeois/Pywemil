Get started with Fetcher
^^^^^^^^^^^^^^^^^^^^^^^^
Fetch a simple page
...................

>>> from fetcher import Fetcher
>>> f = Fetcher()
>>> html = f.fetch("http://www.google.fr")
>>> if html is None:
...   print( "Page unfetchable" )

Fetch a simple page using a proxy
.................................

>>> from fetcher import Fetcher
>>> f = Fetcher("94.75.206.38:3128")
>>> html = f.fetch("http://www.google.fr")
>>> if html is None:
...   print( "Page unfetchable" )

.. note::
   You must indicate Proxy IP *and* its port to Fetcher constructor.

Download a simple file
......................

>>> from fetcher import Fetcher
>>> f = Fetcher()
>>> html = f.download("http://www.google.fr/logos/classicplus.png", "./img.png")
>>> if html is None:
...   print( "File unfetchable" )

.. note::
   You can pass POST data using data parameter (see @session_fetcher)

Crawl a website
...............

The fetcher is able to crawl the "inside" of a website, for a given depth. The *crawl_domain* method will return a dictionnary, associating pages url to their content.

>>> from fetcher import Fetcher
>>> f = Fetcher(lowerize=False) # some links may not be resolvable in lower case
>>> pages = f.crawl_domain( "http://www.yahoo.com", 1, debug=True )

.. note::
   It is recommended not to use a large depth (3 should be a maximum).

Reference
---------

.. autoclass:: fetcher.Fetcher
  :members:
