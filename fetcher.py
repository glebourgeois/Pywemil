# -*- coding: utf8 -*-

import urllib.request, urllib.error, urllib.parse
import re, html.parser, socket, sys

import html5lib
import html5lib.treewalkers
import html5lib.serializer

from Pywemil import html5wrapper

# defines a timeout to stop trying to reach a server
socket.setdefaulttimeout( 5 )

__author__ = "glebourgeois@me.com"

class Fetcher:
  """
  This module can be used to fetch web pages.
  It's able to handle a proxy, and uses a Firefox User Agent.
  """
  
  def __init__(self, proxy=None):
    """
    :param proxy: Give a proxy to use to fetch data, under the form IP:PORT (xx.xx.xx.xx:8080)
    """
    self.proxy = proxy

    self.current_url = None
    self.notfound = 0
    self.ok = 0

    self.badextensions = set( ["pdf", "xls", "doc", "ppt", "rtf", "odt", "zip", "tar.gz", "tar", "exe", "jpg", "png", "jpeg", "bmp", "gif"] )
 
  def crawl_domain(self, domain, depth, debug=False, limit=None, visited=set()):
    """
    Fetches a domain, and then crawls its internal pages until given depth.
    Returns a dictionary of url -> html code.
    """
    pages = {}
    base_domain = urllib.parse.urlparse( domain ).netloc
    
    html = self.fetch( domain, debug)
    if html is not None:
      pages[domain] = html
      visited.add( domain )

    else:
      if debug is True:
        print( "Impossible to crawl %s" % domain )
      return {}

    if depth > 0 and (limit is None or limit > 0):
      dom = None      
      parser = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder("dom"))
      
      try:
        dom = parser.parse( html )
      except Exception as e:
        if debug is True:
          print( e )
        return {}
      
      links = html5wrapper.extract_doc_links( dom )
      for key in links:
        # We do not want anchors to be crawled
        if key[0] == '#':
          continue
        
        url = urllib.parse.urljoin(domain, key)
        
        # Trying to get eventual file extension, and to check its validity
        parts = url.split(".")
        ext = parts[ len(parts) - 1].strip().lower()
        if ext in self.badextensions:
          continue
        
        # Let's check if it's an internal link, and not an outgoing one
        if base_domain == urllib.parse.urlparse( url ).netloc and \
           url not in visited and (limit is None or limit > 0):
             visited.add( url )
             pages.update( self.crawl_domain(url, depth - 1, debug, limit, visited) )
        
             if limit is not None:
               limit -= 1

    return pages

  
  def download(self, url, filename, debug=False, data=None):
    """
    Downloads an item via http, and
    stores it as a file.
    """
    u = None
    opener = None
    request = None
    try:
      # Building opener
      if self.proxy != None:
        if debug:
          print(("Using proxy %s" % self.proxy))
        proxy= urllib.request.ProxyHandler({'http': self.proxy})
        opener = urllib.request.build_opener(proxy)
      else:
        opener = urllib.request.build_opener()

      # Building request      
      request = urllib.request.urlretrieve(url, filename, data=data)
    except Exception as e:
      if debug:        
        print(("Couldn't fetch %s" % url))
        print(e)
      self.notfound += 1
      self.current_url = None
      return None
    
    return True 

  
  def fetch(self, url, debug=False, data=None):
    """
    Fetches a web page.
    If data is None, a GET request will be done, else it will be a POST request using data (must be encoded using urllib.parse.urlencode).
    """
    u = None
    opener = None
    request = None
    try:
      # Building opener
      if self.proxy != None:
        if debug:
          print(("Using proxy %s" % self.proxy))
        proxy= urllib.request.ProxyHandler({'http': self.proxy})
        opener = urllib.request.build_opener(proxy)
        #urllib2.install_opener(opener)
        #urllib2.urlopen('http://www.google.com')
      else:
        opener = urllib.request.build_opener()

      # Building request
      request = urllib.request.Request(url)
      request.add_header("User-Agent", "Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.7.6) Gecko/20050512 Firefox")
      request.add_data(data)

      # Opening URL
      u = opener.open(request)
    except Exception as e:
      if debug:        
        print(("Couldn't fetch %s" % url))
        print(e)
      self.notfound += 1
      self.current_url = None
      return None
    try:
      l = u.read()
      self.current_url = u.geturl()
    
    except Exception as e:
      if debug:
        print("Couldn't read data from socket")
        print(e)
      self.notfound += 1
      self.current_url = None
      return None

    return l    

  def get_current_url(self):
    return self.current_url    
    
  
