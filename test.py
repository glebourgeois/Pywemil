
from Pywemil.fetcher import Fetcher
from Pywemil import scrapers

s = scrapers.LiberationScraper()
period = s.scrape_period("al-qaeda", 1, 1, 2000, 31, 12, 2000)

print( period )


"""
from fetcher import Fetcher

f = Fetcher()
p = f.fetch("http://www.yahoo.fr")
if p is not None:
  print( "Fetched website" )
"""