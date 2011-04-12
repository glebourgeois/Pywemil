import xml.dom
import re

import html5lib
import html5lib.treewalkers
import html5lib.serializer


__author__ = "samuel.charron@gmail.com"

def absolute_xpath(node):
  "Generate an absolute xpath from a node."
  xpath = ""
  while node.nodeType != xml.dom.minidom.Node.DOCUMENT_NODE:
    pos = 1

    if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
      for n in node.parentNode.childNodes:
        if n == node: break
        if n.nodeType == xml.dom.minidom.Node.ELEMENT_NODE and n.nodeName == node.nodeName:
          pos = pos + 1
      xpath = "/%s[%i]" % (node.nodeName, pos) + xpath

    elif node.nodeType == xml.dom.minidom.Node.TEXT_NODE:
      for n in node.parentNode.childNodes:
        if n == node: break
        if n.nodeType == xml.dom.minidom.Node.TEXT_NODE:
          pos = pos + 1
      xpath = ("/text()[%i]" % pos) + xpath

    node = node.parentNode

  return xpath

def node_signature2(node, pretty = False, level = 0):
  """
    Generate a signature for a node. It's a flat (= string) representation of node's tree.
    With pretty = True, each node is on its line and subtrees are indented using level.
  """
  sig = ""
  if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE or node.nodeType == xml.dom.minidom.Node.DOCUMENT_NODE:
    lsig = ""
    for child in node.childNodes:
      lsig = lsig + node_signature2(child, pretty = pretty, level = level + 1)

    name = node.nodeName

    if pretty:
      for i in range(level):
        name = ' ' + name
      sig = name + "\n" + lsig
    else:
      sig = name + "(" + lsig + ")"

  return sig

def node_signature(node, pretty = False, level = 0):
  sig = node_signature2(node, pretty, level)

  parent = node.parentNode
  while parent is not None:
    sig = parent.nodeName + ">" + sig
    parent = parent.parentNode

  return sig

  

def get_nodes_matching_signature2(node, presig, signature, pretty = False, level = 0):

  (sig, nodes) = ("", [])

  if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE or node.nodeType == xml.dom.minidom.Node.DOCUMENT_NODE:
    lsig = ""
    for child in node.childNodes:
      (tmp_sig, tmp_nodes) = get_nodes_matching_signature2(child, presig + node.nodeName + ">", signature, pretty = pretty, level = level + 1)
      lsig = lsig + tmp_sig
      nodes += tmp_nodes

    name = node.nodeName

    if pretty:
      for i in range(level):
        name = ' ' + name
      sig = name + "\n" + lsig
    else:
      sig = name + "(" + lsig + ")"

    if presig + sig == signature:
      nodes.append(node)

  return (sig, nodes)

def get_nodes_matching_signature(node, signature, pretty = False):
  """
    Return nodes matching the given *signature* (see node_signature).
  """

  return get_nodes_matching_signature2(node, "", signature, pretty=pretty, level=0)[1]

  
def exact_matcher_ci(node_text, ref_text):
  "Match exactly two texts, case insensitive (node_text.lower() == ref_text.lower())."
  if node_text.lower() == ref_text.lower():
    return ("exact_matcher_ci", 1)
  else:
    return None

def find_matcher(node_text, ref_text):
  "Find if it exists an occurence of ref_text in node_text, case sensitive"
  if node_text.find(ref_text) != -1:
    return ("find_matcher", len(ref_text) / len(node_text))
  else:
    return None

def find_matcher_ci(node_text, ref_text):
  "Find if it exists an occurence of ref_text in node_text, case insensitive"
  if node_text.lower().find(ref_text.lower()) != -1:
    return ("find_matcher_ci", len(ref_text) / len(node_text))
  else:
    return None

__strip_non_alnum_re = re.compile("[^a-zA-Z0-9]", re.S | re.M | re.I)
def alnum_find_matcher_ci(node_text, ref_text):
  "Filter node_text and ref_text keeping only alnum characters, then same behaviour than find_matcher_ci"
  node_text = __strip_non_alnum_re.sub('', node_text)
  ref_text = __strip_non_alnum_re.sub('', ref_text)

  if node_text.lower().find(ref_text.lower()) != -1:
    return ("alnum_find_matcher_ci", len(ref_text) / len(node_text))
  else:
    return None

def dont_filter(tag_name):
  "Don't filter tags"
  return False


def filter_script_style(tag_name):
  "Filter out script and style tags"
  return tag_name in set(["script", "style"])

def filter_useless_tags(tag_name):
  """
    Filter out lots of useless tags:
    
      - script
      - style
      - head

  """
  return tag_name in set(["script", "style", "head"])

def find_text(node, text, matcher = exact_matcher_ci, tag_filter = dont_filter):
  """
    Find a text node matching *text*.
    This function uses a matcher, a function taking two bits of texts and returning non-None when matching.
    It also takes a tag_filter, a function that can be used to filter out some nodes, returning True for nodes to not follow.
    This function returns list of (return values of matcher, matching node) pairs.
  """
  if node.nodeType == xml.dom.minidom.Node.TEXT_NODE:
    ret = matcher(node.nodeValue, text)
    if ret is None:
      return []
    else:
      return [(ret, node)]

  elif node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE or node.nodeType == xml.dom.minidom.Node.DOCUMENT_NODE:
    if tag_filter(node.nodeName):
      return []
    else:
      l = []
      for child in node.childNodes:
        l += find_text(child, text, matcher=matcher, tag_filter=tag_filter)

      if node.attributes is not None:
        for i in range(node.attributes.length):
          attr = node.attributes.item(i)
          if attr.name in set(["alt"]):
            ret = matcher(attr.value, text)
            if ret is not None:
              l += [(ret, node)]

      return l

  # Not a text node nor an element node
  return []


def find_tags(node, tag_set):
  "Find nodes with name contained in *tag_set*"
  l = []

  if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
    if node.nodeName in tag_set:
      l = [node]
    for child in node.childNodes:
      l += find_tags(child, tag_set)
  return l

def highlight_node(node, color):
  """
    Highlight a node, surrounding it with 5px borders of the given color
  """

  if node.nodeType == xml.dom.minidom.Node.TEXT_NODE:
    node = node.parentNode

  if node.nodeName == "tbody":
    node = node.parentNode

  if node.nodeName != "tr":
    node.setAttribute("style", "border: 5px solid %s;" % color)
  else:
    for c in node.childNodes:
      if c.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
        c.setAttribute("style", "border-top: 5px solid %s; border-bottom: 5px solid %s;" % (color, color))

    idx = 0
    while idx < len(node.childNodes):
      if node.childNodes[idx].nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
        node.childNodes[idx].setAttribute("style", "border-top: 5px solid %s; border-bottom: 5px solid %s; border-left: 5px solid %s;" % (color, color, color))
        break
      idx = idx + 1

    idx = len(node.childNodes) - 1
    while idx >= 0:
      if node.childNodes[idx].nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
        node.childNodes[idx].setAttribute("style", "border-top: 5px solid %s; border-bottom: 5px solid %s; border-right: 5px solid %s;" % (color, color, color))
        break
      idx = idx - 1

def backgroundize_node(node, color):
  """
    Highlight a node, adding it a background of the given color
  """
  if node.nodeName == "tbody":
    node = node.parentNode

  if node.nodeName != "tr":
    node.setAttribute("style", "background-color: %s;" % color)
  else:
    for c in node.childNodes:
      if c.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
        c.setAttribute("style", "background-color: %s;" % color)

def extract_doc_links(doc):
  """
  Extracts all hyperlinks from a dom document.
  Returns a dictionary with link as key, and value as a tuple (dom element, link text).
  """
  ret = {}
  for link in doc.getElementsByTagName("a"):
    href = link.getAttribute("href")
    content = ""
    for child in link.childNodes:
      if child.nodeType == xml.dom.minidom.Node.TEXT_NODE:
        content = content + child.nodeValue + " "

    ret[href]  = (link, content)
    
  return ret

def count_tags(node):
  """
    Count the number of tags of the subtree rooted at the given *node*.
  """
  if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE or \
     node.nodeType == xml.dom.minidom.Node.DOCUMENT_NODE:
    ret = 1
    for child in node.childNodes:
      ret += count_tags(child)
    return ret
  return 0

def print_node(node, level = 0):
  """
    Print the subtree rooted at *node*, with children and text nodes indented.
    element node are indented with ' ' (spaces), text nodes with '.' (dots)
  """
  if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE or node.nodeType == xml.dom.minidom.Node.DOCUMENT_NODE:
    for i in range(level):
      print(' ', end='')
    print(node.nodeName)
    for child in node.childNodes:
      print_node(child, level + 1)
  else:
    for i in range(level):
      print('.', end='')
    print(node.nodeValue)

def merge_text_nodes2(doc, node):
  i = 0
  while i < node.childNodes.length - 1:
    c1 = node.childNodes.item(i)
    c2 = node.childNodes.item(i + 1)
    if c1.nodeType == xml.dom.minidom.Node.TEXT_NODE and c2.nodeType == xml.dom.minidom.Node.TEXT_NODE:
      node.replaceChild(doc.createTextNode(c1.nodeValue + c2.nodeValue), c1)
      node.removeChild(c2).unlink()
      continue
    i = i + 1
  for c in node.childNodes:
    merge_text_nodes2(doc, c)

def merge_text_nodes(doc):
  """Merge consecutive text nodes in a DOM tree. Assume that the current node is an element or a document"""
  assert doc.nodeType == xml.dom.minidom.Node.DOCUMENT_NODE
  merge_text_nodes2(doc, doc)
  return doc

def get_text_from_subtree(node):
  """
  Merges text nodes inside a node. May be used for example
  to generate merged text inside a <p> tag.
  Useless tags as script, style, ... are ignored.
  """
  txt = ""
  
  for n in node.childNodes:
    if n.nodeType == xml.dom.minidom.Node.TEXT_NODE:
      # We want real content text, no script junk
      if not filter_useless_tags( node.nodeName ):
        txt += n.nodeValue
    else:
        txt += ' ' + get_text_from_subtree( n )

  return txt
  
def clean_html(html):
  """
  Takes a raw html string, and converts it into a good html string, 
  well encoded.
  """
  p = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder("dom"))
  doc = p.parse( html )

  walker = html5lib.treewalkers.getTreeWalker("dom")
  stream = walker(doc)
  s = html5lib.serializer.XHTMLSerializer(omit_optional_tags=False)
  output_generator = s.serialize(stream)

  str = ""
  for item in output_generator:
    str += item

  return str

