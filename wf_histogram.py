# -*- coding: utf8 -*-

import operator, math

__author__ = "glebourgeois@me.com"

class WFHistogram:
  """
  Word Frequencies Histogram : representing a document as 
  token frequencies.
  This class aims at tokenizing text, records it as histograms,
  and then enable comparisons, extractions, some semantic.
  """

  def __init__(self, text, blacklist):
    """
    blacklist must be a set of tokens
    """
    self.raw = text
    self.freq = {}
    self.tokens = set()
    self.blacklist = blacklist

    self._make_histogram(self.raw)

  def add_text(self, t):
    self.raw += t
    self._make_histogram( t )

  def _make_histogram(self, t):
    sep = set([' ', '\n', '\t', '<', '>', '.', ',', ':', '/', '\r', ';', '-', '!', \
               '?', '(', ')', '"', '|', "'", '’', '+', '*', '}', '{'])
    t = t.lower()
    token = ""

    for char in t:
      if char in sep:
        if len(token) > 2 and not token in self.blacklist:
          
          # Digits are not considered tokens
          try:
            int( token )
            token = ""
            continue
          except:
            pass
          
          # Recording the token occurence
          try:
            self.freq[token] += 1
          except:
            self.freq[token] = 1
            self.tokens.add( token )
        
        # resetting token
        token = ""
      
      else:
        token += char

    # All text is parsed, let's check if remaining is a token.
    if len(token) > 2:
      # Digits are not considered tokens
      try:
        int( token )
        return
      except:
        pass

      try:
        self.freq[token] += 1
      except:
        self.freq[token] = 1
        self.tokens.add( token )

  def merge(self, hist):
    """
    Merge this histogram with another one.
    """
    for t in hist.tokens:
      # new token
      if t not in self.tokens:
        self.freq[t] = hist.freq[t]
        self.tokens.add( t )
      # know token, add new frequency
      else:
        self.freq[t] += hist.freq[t]

  def get_new_words(self, hist):
    """
    Given an other hist, returns tokens not know in
    current hist.
    """
    diff = []
    res = {}
    num_words = len(self.tokens)

    for t in hist.tokens:
      if t not in self.tokens:
        diff.append(t)
    
    res["tokens"] = diff
    if num_words < 1:
      res["percent"] = 1
    else:
      res["percent"] = float(len(diff)) / float(num_words)
    
    return res

  def compare(self, hist):
    """
    Will compare current histogram with an external histogram,
    and returns a score of similarity between 0 and 1
    """
    score = 0
    maxm = 0
    for key in self.freq:
      num = self.freq[key]
      
      try:
        cmp_num = hist.freq[key]
        maxm += max(num, cmp_num)
        diff = abs(num - cmp_num)
        score += diff
      except:
        maxm += num

    if maxm < 1:
      return 0.0
    score = float(score) / float(maxm)

    return score

  def __str__(self):
    """
    Transforms histogram in a human readable string 
    (YAML formatting)
    """
    s_hist = sorted(iter(self.freq.items()), key=operator.itemgetter(1))
    s_hist.reverse()
    
    if len(s_hist) < 1:
      return "" 
    max = float( s_hist[0][1] )
    out = ""
    for w in s_hist:
      score = float(w[1]) / max 
      if score > 0.25:
        out += "  - !token\n"
        out += "    word: %s\n" % w[0]
        out += "    score: %f\n" % score
        #out += "%s;%f\n" % (w[0], score)

    return out

  def filter_print(self, filter):
    """
    Print only tokens and their frequencies found in filter (which must be a set),
    with a freq > 0.25
    (CSV formatting)
    """
    filtered = {}
    
    if filter is None:
      return "\n"

    for t in self.freq:
      if t in filter:
        filtered[t] = self.freq[t]
    
    s_hist = sorted(iter(filtered.items()), key=operator.itemgetter(1))
    s_hist.reverse()
    
    if len(s_hist) < 1:
      return "" 
    max = float( s_hist[0][1] )
    out = ""
    for w in s_hist:
      score = float(w[1]) / max 
      if score > 0.25:
        out += "%s;%f\n" % (w[0], score)

    return out

  def idf_print(self, idf, num_pages):
    """
    Given a dictionary containing tokens idf, and
    the number of documents, computes tf/idf for each token and returns
    only ones with a score > 0.25
    (YAML formatting)
    """
    filtered = {}
    tot = 0
    
    for t in self.freq:
      tot += self.freq[t]

    for t in self.freq:
      filtered[t] = (self.freq[t] / tot) * ( math.log(num_pages / idf[t]) )
    
    s_hist = sorted(iter(filtered.items()), key=operator.itemgetter(1))
    s_hist.reverse()
    
    if len(s_hist) < 1:
      return "" 
    
    max = float( s_hist[0][1] )
    if max <= 0:
      return ""
    
    out = ""
    for w in s_hist:
      score = float(w[1]) / max 
      if score > 0.25:
        out += "  - !token\n"
        out += "    word: %s\n" % w[0]
        out += "    score: %f\n" % score
        #out += "%s;%f\n" % (w[0], score)

    return out

  def get_focus_score(self, vocabulary):
    """
    Computes a score of similarity between vocabulary frequencies
    and constant vocabulary.
    """
    s_hist = sorted(iter(self.freq.items()), key=operator.itemgetter(1))
    s_hist.reverse()
    
    if len( s_hist ) < 1:
      return 0.0
    
    max = float( s_hist[0][1] )
    normalized_scores = {}
    score = 0
    tot = 0
    

    if vocabulary is None:
      return 0.0
    
    for t in s_hist:
      s = float(t[1]) / max
      if s > 0.25 :
        tot += s
        normalized_scores[t[0]] = s
    
    for t in vocabulary:
      try:
        score += normalized_scores[t]
      except:
        pass

    #score = score / ( tot * len( normalized_scores ) )
    score = score / len( normalized_scores )

    return score



