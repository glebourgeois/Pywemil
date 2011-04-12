# -*- coding: utf-8 -*-

import re, time, random
from Pywemil.fetcher      import Fetcher
import Pywemil.html5wrapper as html5wrapper

class LiberationScraper:

  def __init__(self):
    self.base_url = "http://recherche.liberation.fr/recherche/"
    self.constant_args = "&period=custom&editorial_source=&paper_channel=&sort=-publication_date_time"
    self.fetcher = Fetcher()
    
    # Computed
    self.authors = {} # name associated with a number of articles
    self.links = []   # links toward found articles
    self.txt = []     # articles texts
    
    # Regexps
    self.re_article = '<div class="article">.*?<div class="object-content">(.*?)</div>'
    self.re_author = 'Par <strong>(.*?)</strong>'
    self.re_link = '<a href="(.*?)">'
    #self.re_nnext = '<a href="(.*?)" class="next">'
    self.re_nnext = '<a class="next" href="(.*?)">'
    self.re_txt = '<div class="articleContent">(.*?)</div>'
    
  def scrape_period(self, expression, bday, bmonth, byear, eday, emonth, eyear):
    """
    Scrapes Liberation for a query among a period of time.
    """
    period = "&period_start_day=%d&period_start_month=%d&period_start_year=%d&period_end_day=%d&period_end_month=%d&period_end_year=%d" % (bday, bmonth, byear, eday, emonth, eyear)
    query = "%s?q=%s%s%s" % (self.base_url, expression, period, self.constant_args)
    next = True
    count = 1
    
    while next is True:
      print("\t[%d]" % count)
      count += 1
      
      # fetching page
      page = None
      page = self.fetcher.fetch(query)
      if page is None:
        # Let's try again
        time.sleep(3)
        page = self.fetcher.fetch(query)
        
        if page is None:
          print( "Impossible to fetch [%s]" % query )
          break
      
      page = html5wrapper.clean_html( page )
      
      # is there a next link
      m = re.search(self.re_nnext, page, re.U)
      if m is not None:
        url = m.group(1).strip()
        query = "%s%s" % (self.base_url, url)
        query = query.replace("&amp;amp=", "")
      else:
        print("\t> Last page reached.")
        next = False
     
      links = self._extract_articles(page)
      self.links.extend( links )
     
      for l in links:
        # Let's now extract text from each article, with some courtoisy
        time.sleep( random.uniform(1, 3) )
        p = self.fetcher.fetch( l )
        if p is not None:
          p = html5wrapper.clean_html( p )
          m = re.search(self.re_txt, p, re.U|re.M|re.S)
        
          if m is not None:
            txt = m.group(1).strip()
            txt = "[%s]\n%s" % (l, txt)
            self.txt.append( txt )            
          else:
            print("\n\t[%s] impossible to extract article" % l)

      #FIXME: FAKE break for testing purpose
      #break
    
    # Building final result
    res = {}
    res["links"] = self.links
    res["authors"] = self.authors
    res["txt"] = self.txt    
    
    return res

  def _extract_articles(self, page):
    """
    Extracts links toward articles and authors names
    from a results page.
    """
    links = []
    
    articles = re.findall(self.re_article, page, re.U|re.M|re.S)
    
    for article in articles:
      # Looking for author
      m = re.search(self.re_author, article, re.U|re.M|re.S)
      if m is not None:
        author = m.group(1).strip()        
        try:
          self.authors[author] += 1
        except:
          self.authors[author] = 1
      
      # Looking for article link
      m = re.search(self.re_link, article, re.U|re.M|re.S)
      if m is not None:
        link = m.group(1).strip()
        links.append( link )
      
    return links
      
  
  

    
    
    
    
    
    
    
    
    
    
