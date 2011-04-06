Get started with DOM-Funs
^^^^^^^^^^^^^^^^^^^^^^^^^

To use it :

>>> from html5wrapper import *

Get an XPath
------------

>>> import html5lib
>>> p = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder("dom"))
>>> doc = p.parse(page)
>>> for node in doc.getElementsByTagName("img"):
...   print(absolute_xpath(node))

.. note: An absolute XPath is an XPath rooted to the tree root.

.. note: Generally, there are several ways to build an XPath. This method builds it unambiguous having each node filtered by its position with respect to its siblings. 
   
   To point to the <b>3</b> node in the following HTML *<a><b>1</b><c>2</c><b>3</b></a>*, the XPath will be /a[1]/b[2] .

Sign a Node
-----------

A signature is a string describing a node structure. It is used to determine semantically equivalent subtrees in a webpage. For example, without HTML presentation nodes (i.e. <font>, <b>, …), two product pages are supposed to have the same signature.

>>> for node in doc.getElementsByTagName("p"):
...   print(node_signature(node))

Get nodes using their signature:
--------------------------------

To get all nodes in a subtree matching the given signature : 

>>> for node in get_nodes_matching_signature(node, signature):
...   print(node.nodeName)

Find some text
---------------

This is a somewhat complex but powerful way to retrieve some text nodes from a tree : 

>>> doc = p.parse(page)
>>> find_text(doc, "Tw-Eñ.!Ga?", matcher=XXX, tag_filter=YYY)

tag_filter is a function applied to each node, returning True if a node should not be explorated for the search. It's particularely useful to ignore nodes like *script*  and *style*. 3 filters currently exist : 

  - dont_filter: do not filter
  - filter_useless_tags: remove script, style and head tags
  - filter_script_style: only remove script and style

matcher is the function used to match the given text with text nodes. It must return None when the text is not matched and any other value else. Currently there are 4 matches : 

  - exact_matcher_ci: the texts must be the same, except for the case (ci = case insensitive)
  - find_matcher and find_matcher_ci: the searched text must be inside the node text
  - alnum_find_matcher_ci: the searched text and node text are cleaned to only keep alphanumeric symbols and then find_matcher_ci is called.

These functions currently return a pair containing the matcher name and a confidence (0 = does not match, 1 = full match).

Find some tags
--------------

>>> for node1 in doc.getElementsByTagName("p"):
...   for node2 in find_tags(node1, set(["a", "img"]))
...     print(node2.nodeName)

.. note:
   This finds the *a* and *img* nodes contained in *p* nodes.

Highlight a node
----------------

>>> for node in doc.getElementsByTagName("p"):
...   highlight_node(node, "red")
>>> for node in doc.getElementsByTagName("a"):
...   backgroundize_node(node, "red")

.. note:
   highlight_node surround a node with a 5px border. backgroundize_node adds a coloured background to the node.

Count tags
----------

To count the number of nodes in a subtree: 

>>> for node in doc.getElementsByTagName("div"):
...   print(count_tags(node))

Print nodes
-----------

To pretty-print a subtree: 

>>> for node in doc.getElementsByTagName("div"):
...   print_node(node)


Merge consecutive text nodes
----------------------------

With html code like <a>une r&eacute;f&eacute;rence</a>, html5lib gives us 5 text nodes:

  - une r
  - é
  - f
  - é
  - rence

To fix that, after loading an html document, you can call merge_text_nodes:

>>> import html5lib
>>> p = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder("dom"))
>>> doc = p.parse(page)
>>> merge_text_nodes(doc)



Reference
---------

.. automodule:: html5wrapper
  :members:
