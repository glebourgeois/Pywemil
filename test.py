from fetcher import Fetcher

f = Fetcher()
p = f.fetch("http://www.yahoo.fr")
if p is not None:
  print( "Fetched website" )
