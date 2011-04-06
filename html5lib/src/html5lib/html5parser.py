import sys

from . import inputstream
from . import tokenizer

from . import treebuilders
from .treebuilders._base import Marker
from .treebuilders import simpletree

from . import utils

from .constants import contentModelFlags, spaceCharacters, asciiUpper2Lower
from .constants import scopingElements, formattingElements, specialElements
from .constants import headingElements, tableInsertModeElements
from .constants import cdataElements, rcdataElements, voidElements
from .constants import tokenTypes

def parse(doc, treebuilderName="simpletree", encoding=None, implementation=None):
    tb = treebuilders.getTreeBuilder(treebuilderName, 
                                     implementation=implementation)
    p = HTMLParser(tb)
    return p.parse(doc, encoding=encoding)

class HTMLParser(object):
    """HTML parser. Generates a tree structure from a stream of (possibly
        malformed) HTML"""

    def __init__(self, tree = simpletree.TreeBuilder,
                 tokenizer = tokenizer.HTMLTokenizer, strict = False,
                 namespaceHTMLElements = False):
        """
        strict - raise an exception when a parse error is encountered

        tree - a treebuilder class controlling the type of tree that will be
        returned. Built in treebuilders can be accessed through
        html5lib.treebuilders.getTreeBuilder(treeType)
        
        tokenizer - a class that provides a stream of tokens to the treebuilder.
        This may be replaced for e.g. a sanitizer which converts some tags to
        text
        """

        # Raise an exception on the first error encountered
        self.strict = strict

        self.tree = tree(namespaceHTMLElements)
        self.tokenizer_class = tokenizer
        self.errors = []

        self.phases = {
            "initial": InitialPhase(self, self.tree),
            "beforeHtml": BeforeHtmlPhase(self, self.tree),
            "beforeHead": BeforeHeadPhase(self, self.tree),
            "inHead": InHeadPhase(self, self.tree),
            # XXX "inHeadNoscript": InHeadNoScriptPhase(self, self.tree),
            "afterHead": AfterHeadPhase(self, self.tree),
            "inBody": InBodyPhase(self, self.tree),
            "inCDataRCData": InCDataRCDataPhase(self, self.tree),
            "inTable": InTablePhase(self, self.tree),
            "inCaption": InCaptionPhase(self, self.tree),
            "inColumnGroup": InColumnGroupPhase(self, self.tree),
            "inTableBody": InTableBodyPhase(self, self.tree),
            "inRow": InRowPhase(self, self.tree),
            "inCell": InCellPhase(self, self.tree),
            "inSelect": InSelectPhase(self, self.tree),
            "inSelectInTable": InSelectInTablePhase(self, self.tree),
            "afterBody": AfterBodyPhase(self, self.tree),
            "inFrameset": InFramesetPhase(self, self.tree),
            "afterFrameset": AfterFramesetPhase(self, self.tree),
            "afterAfterBody": AfterAfterBodyPhase(self, self.tree),
            "afterAfterFrameset": AfterAfterFramesetPhase(self, self.tree),
            # XXX after after frameset
        }

    def _parse(self, stream, innerHTML=False, container="div",
               encoding=None, parseMeta=True, useChardet=True, **kwargs):
        
        self.tree.reset()
        self.firstStartTag = False
        self.errors = []
        # "quirks" / "limited quirks" / "no quirks"
        self.compatMode = "no quirks"

        self.tokenizer = self.tokenizer_class(stream, encoding=encoding,
                                              parseMeta=parseMeta,
                                              useChardet=useChardet, **kwargs)

        if innerHTML:
            self.innerHTML = container.lower()

            if self.innerHTML in cdataElements:
                self.tokenizer.contentModelFlag = tokenizer.contentModelFlags["RCDATA"]
            elif self.innerHTML in rcdataElements:
                self.tokenizer.contentModelFlag = tokenizer.contentModelFlags["CDATA"]
            elif self.innerHTML == 'plaintext':
                self.tokenizer.contentModelFlag = tokenizer.contentModelFlags["PLAINTEXT"]
            else:
                # contentModelFlag already is PCDATA
                #self.tokenizer.contentModelFlag = tokenizer.contentModelFlags["PCDATA"]
                pass
            self.phase = self.phases["beforeHtml"]
            self.phase.insertHtmlElement()
            self.resetInsertionMode()
        else:
            self.innerHTML = False
            self.phase = self.phases["initial"]

        # We only seem to have InBodyPhase testcases where the following is
        # relevant ... need others too
        self.lastPhase = None
        self.beforeRCDataPhase = None

        CharactersToken = tokenTypes["Characters"]
        SpaceCharactersToken = tokenTypes["SpaceCharacters"]
        StartTagToken = tokenTypes["StartTag"]
        EndTagToken = tokenTypes["EndTag"]
        CommentToken = tokenTypes["Comment"]
        DoctypeToken = tokenTypes["Doctype"]
        
        
        for token in self.normalizedTokens():
            #print self.phase.__class__.__name__
            #print token
            type = token["type"]
            if type == CharactersToken:
                self.phase.processCharacters(token)
            elif type == SpaceCharactersToken:
                self.phase.processSpaceCharacters(token)
            elif type == StartTagToken:
                self.selfClosingAcknowledged = False
                self.phase.processStartTag(token)
                if (token["selfClosing"]
                    and not self.selfClosingAcknowledged):
                    self.parseError("non-void-element-with-trailing-soldius",
                                    {"name":token["name"]})
            elif type == EndTagToken:
                self.phase.processEndTag(token)
            elif type == CommentToken:
                self.phase.processComment(token)
            elif type == DoctypeToken:
                self.phase.processDoctype(token)
            else:
                self.parseError(token["data"], token.get("datavars", {}))

        # When the loop finishes it's EOF
        self.phase.processEOF()

    def normalizedTokens(self):
        for token in self.tokenizer:
            yield self.normalizeToken(token)

    def parse(self, stream, encoding=None, parseMeta=True, useChardet=True):
        """Parse a HTML document into a well-formed tree

        stream - a filelike object or string containing the HTML to be parsed

        The optional encoding parameter must be a string that indicates
        the encoding.  If specified, that encoding will be used,
        regardless of any BOM or later declaration (such as in a meta
        element)
        """
        self._parse(stream, innerHTML=False, encoding=encoding)
        return self.tree.getDocument()
    
    def parseFragment(self, stream, container="div", encoding=None,
                      parseMeta=False, useChardet=True):
        """Parse a HTML fragment into a well-formed tree fragment
        
        container - name of the element we're setting the innerHTML property
        if set to None, default to 'div'

        stream - a filelike object or string containing the HTML to be parsed

        The optional encoding parameter must be a string that indicates
        the encoding.  If specified, that encoding will be used,
        regardless of any BOM or later declaration (such as in a meta
        element)
        """
        self._parse(stream, True, container=container, encoding=encoding)
        return self.tree.getFragment()

    def parseError(self, errorcode="XXX-undefined-error", datavars={}):
        # XXX The idea is to make errorcode mandatory.
        self.errors.append((self.tokenizer.stream.position(), errorcode, datavars))
        if self.strict:
            raise ParseError

    def normalizeToken(self, token):
        """ HTML5 specific normalizations to the token stream """

        if token["type"] == tokenTypes["StartTag"]:
            token["data"] = dict(token["data"][::-1])

        return token


    def resetInsertionMode(self):
        # The name of this method is mostly historical. (It's also used in the
        # specification.)
        last = False
        newModes = {
            "select":"inSelect",
            "td":"inCell",
            "th":"inCell",
            "tr":"inRow",
            "tbody":"inTableBody",
            "thead":"inTableBody",
            "tfoot":"inTableBody",
            "caption":"inCaption",
            "colgroup":"inColumnGroup",
            "table":"inTable",
            "head":"inBody",
            "body":"inBody",
            "frameset":"inFrameset"
        }
        for node in self.tree.openElements[::-1]:
            nodeName = node.name
            if node == self.tree.openElements[0]:
                last = True
                if nodeName not in ['td', 'th']:
                    # XXX
                    assert self.innerHTML
                    nodeName = self.innerHTML
            # Check for conditions that should only happen in the innerHTML
            # case
            if nodeName in ("select", "colgroup", "head", "frameset"):
                # XXX
                assert self.innerHTML
            if nodeName in newModes:
                self.phase = self.phases[newModes[nodeName]]
                break
            elif nodeName == "html":
                if self.tree.headPointer is None:
                    self.phase = self.phases["beforeHead"]
                else:
                   self.phase = self.phases["afterHead"]
                break
            elif last:
                self.phase = self.phases["inBody"]
                break

    def parseRCDataCData(self, token, contentType):
        """Generic (R)CDATA Parsing algorithm
        contentType - RCDATA or CDATA
        """
        assert contentType in ("CDATA", "RCDATA")
        
        element = self.tree.insertElement(token)
        self.tokenizer.contentModelFlag = contentModelFlags[contentType]

        self.originalPhase = self.phase

        self.phase = self.phases["inCDataRCData"]

class Phase(object):
    """Base class for helper object that implements each phase of processing
    """
    # Order should be (they can be omitted):
    # * EOF
    # * Comment
    # * Doctype
    # * SpaceCharacters
    # * Characters
    # * StartTag
    #   - startTag* methods
    # * EndTag
    #   - endTag* methods

    def __init__(self, parser, tree):
        self.parser = parser
        self.tree = tree

    def processEOF(self):
        raise NotImplementedError

    def processComment(self, token):
        # For most phases the following is correct. Where it's not it will be
        # overridden.
        self.tree.insertComment(token, self.tree.openElements[-1])

    def processDoctype(self, token):
        self.parser.parseError("unexpected-doctype")

    def processSpaceCharacters(self, token):
        self.tree.insertText(token["data"])

    def processStartTag(self, token):
        self.startTagHandler[token["name"]](token)

    def startTagHtml(self, token):
        if self.parser.firstStartTag == False and token["name"] == "html":
           self.parser.parseError("non-html-root")
        # XXX Need a check here to see if the first start tag token emitted is
        # this token... If it's not, invoke self.parser.parseError().
        for attr, value in token["data"].items():
            if attr not in self.tree.openElements[0].attributes:
                self.tree.openElements[0].attributes[attr] = value
        self.parser.firstStartTag = False

    def processEndTag(self, token):
        self.endTagHandler[token["name"]](token)

class InitialPhase(Phase):
    # This phase deals with error handling as well which is currently not
    # covered in the specification. The error handling is typically known as
    # "quirks mode". It is expected that a future version of HTML5 will defin
    # this.
    def processEOF(self):
        self.parser.parseError("expected-doctype-but-got-eof")
        self.parser.compatMode = "quirks"
        self.parser.phase = self.parser.phases["beforeHtml"]
        self.parser.phase.processEOF()

    def processComment(self, token):
        self.tree.insertComment(token, self.tree.document)

    def processDoctype(self, token):

        name = token["name"]
        publicId = token["publicId"]
        systemId = token["systemId"]
        correct = token["correct"]

        if (name != "html" or publicId != None or
            systemId != None):
            self.parser.parseError("unknown-doctype")
        
        if publicId is None:
            publicId = ""
        if systemId is None:
            systemId = ""
            
        self.tree.insertDoctype(token)

        if publicId != "":
            publicId = publicId.translate(asciiUpper2Lower)

        if ((not correct) or token["name"] != "html"
            or publicId in
            ("+//silmaril//dtd html pro v0r11 19970101//en",
             "-//advasoft ltd//dtd html 3.0 aswedit + extensions//en",
             "-//as//dtd html 3.0 aswedit + extensions//en",
             "-//ietf//dtd html 2.0 level 1//en",
             "-//ietf//dtd html 2.0 level 2//en",
             "-//ietf//dtd html 2.0 strict level 1//en",
             "-//ietf//dtd html 2.0 strict level 2//en",
             "-//ietf//dtd html 2.0 strict//en",
             "-//ietf//dtd html 2.0//en",
             "-//ietf//dtd html 2.1e//en",
             "-//ietf//dtd html 3.0//en",
             "-//ietf//dtd html 3.0//en//",
             "-//ietf//dtd html 3.2 final//en",
             "-//ietf//dtd html 3.2//en",
             "-//ietf//dtd html 3//en",
             "-//ietf//dtd html level 0//en",
             "-//ietf//dtd html level 0//en//2.0",
             "-//ietf//dtd html level 1//en",
             "-//ietf//dtd html level 1//en//2.0",
             "-//ietf//dtd html level 2//en",
             "-//ietf//dtd html level 2//en//2.0",
             "-//ietf//dtd html level 3//en",
             "-//ietf//dtd html level 3//en//3.0",
             "-//ietf//dtd html strict level 0//en",
             "-//ietf//dtd html strict level 0//en//2.0",
             "-//ietf//dtd html strict level 1//en",
             "-//ietf//dtd html strict level 1//en//2.0",
             "-//ietf//dtd html strict level 2//en",
             "-//ietf//dtd html strict level 2//en//2.0",
             "-//ietf//dtd html strict level 3//en",
             "-//ietf//dtd html strict level 3//en//3.0",
             "-//ietf//dtd html strict//en",
             "-//ietf//dtd html strict//en//2.0",
             "-//ietf//dtd html strict//en//3.0",
             "-//ietf//dtd html//en",
             "-//ietf//dtd html//en//2.0",
             "-//ietf//dtd html//en//3.0",
             "-//metrius//dtd metrius presentational//en",
             "-//microsoft//dtd internet explorer 2.0 html strict//en",
             "-//microsoft//dtd internet explorer 2.0 html//en",
             "-//microsoft//dtd internet explorer 2.0 tables//en",
             "-//microsoft//dtd internet explorer 3.0 html strict//en",
             "-//microsoft//dtd internet explorer 3.0 html//en",
             "-//microsoft//dtd internet explorer 3.0 tables//en",
             "-//netscape comm. corp.//dtd html//en",
             "-//netscape comm. corp.//dtd strict html//en",
             "-//o'reilly and associates//dtd html 2.0//en",
             "-//o'reilly and associates//dtd html extended 1.0//en",
             "-//o'reilly and associates//dtd html extended relaxed 1.0//en",
             "-//spyglass//dtd html 2.0 extended//en",
             "-//sq//dtd html 2.0 hotmetal + extensions//en",
             "-//sun microsystems corp.//dtd hotjava html//en",
             "-//sun microsystems corp.//dtd hotjava strict html//en",
             "-//w3c//dtd html 3 1995-03-24//en",
             "-//w3c//dtd html 3.2 draft//en",
             "-//w3c//dtd html 3.2 final//en",
             "-//w3c//dtd html 3.2//en",
             "-//w3c//dtd html 3.2s draft//en",
             "-//w3c//dtd html 4.0 frameset//en",
             "-//w3c//dtd html 4.0 transitional//en",
             "-//w3c//dtd html experimental 19960712//en",
             "-//w3c//dtd html experimental 970421//en",
             "-//w3c//dtd w3 html//en",
             "-//w3o//dtd w3 html 3.0//en",
             "-//w3o//dtd w3 html 3.0//en//",
             "-//w3o//dtd w3 html strict 3.0//en//",
             "-//webtechs//dtd mozilla html 2.0//en",
             "-//webtechs//dtd mozilla html//en",
             "-/w3c/dtd html 4.0 transitional/en",
             "html")
            or (publicId in
                ("-//w3c//dtd html 4.01 frameset//EN",
                 "-//w3c//dtd html 4.01 transitional//EN") and systemId == None)
            or (systemId != None and
              systemId == 
                "http://www.ibm.com/data/dtd/v11/ibmxhtml1-transitional.dtd")):
            self.parser.compatMode = "quirks"
        elif (publicId in
              ("-//w3c//dtd xhtml 1.0 frameset//EN",
               "-//w3c//dtd xhtml 1.0 transitional//EN")
              or (publicId in
                  ("-//w3c//dtd html 4.01 frameset//EN",
                   "-//w3c//dtd html 4.01 transitional//EN") and systemId == None)):
            self.parser.compatMode = "limited quirks"

        self.parser.phase = self.parser.phases["beforeHtml"]

    def processSpaceCharacters(self, token):
        pass

    def processCharacters(self, token):
        self.parser.parseError("expected-doctype-but-got-chars")
        self.parser.compatMode = "quirks"
        self.parser.phase = self.parser.phases["beforeHtml"]
        self.parser.phase.processCharacters(token)

    def processStartTag(self, token):
        self.parser.parseError("expected-doctype-but-got-start-tag",
          {"name": token["name"]})
        self.compatMode = "quirks"
        self.parser.phase = self.parser.phases["beforeHtml"]
        self.parser.phase.processStartTag(token)

    def processEndTag(self, token):
        self.parser.parseError("expected-doctype-but-got-end-tag",
          {"name": token["name"]})
        self.compatMode = "quirks"
        self.parser.phase = self.parser.phases["beforeHtml"]
        self.parser.phase.processEndTag(token)


class BeforeHtmlPhase(Phase):
    # helper methods
    def insertHtmlElement(self):
        self.tree.insertRoot(impliedTagToken("html", "StartTag"))
        self.parser.phase = self.parser.phases["beforeHead"]

    # other
    def processEOF(self):
        self.insertHtmlElement()
        self.parser.phase.processEOF()

    def processComment(self, token):
        self.tree.insertComment(token, self.tree.document)

    def processSpaceCharacters(self, token):
        pass

    def processCharacters(self, token):
        self.insertHtmlElement()
        self.parser.phase.processCharacters(token)

    def processStartTag(self, token):
        if token["name"] == "html":
            self.parser.firstStartTag = True
        self.insertHtmlElement()
        self.parser.phase.processStartTag(token)

    def processEndTag(self, token):
        self.insertHtmlElement()
        self.parser.phase.processEndTag(token)


class BeforeHeadPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("head", self.startTagHead)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            (("head", "br"), self.endTagImplyHead)
        ])
        self.endTagHandler.default = self.endTagOther

    def processEOF(self):
        self.startTagHead(impliedTagToken("head", "StartTag"))
        self.parser.phase.processEOF()

    def processSpaceCharacters(self, token):
        pass

    def processCharacters(self, token):
        self.startTagHead(impliedTagToken("head", "StartTag"))
        self.parser.phase.processCharacters(token)

    def startTagHead(self, token):
        self.tree.insertElement(token)
        self.tree.headPointer = self.tree.openElements[-1]
        self.parser.phase = self.parser.phases["inHead"]

    def startTagOther(self, token):
        self.startTagHead(impliedTagToken("head", "StartTag"))
        self.parser.phase.processStartTag(token)

    def endTagImplyHead(self, token):
        self.startTagHead(impliedTagToken("head", "StartTag"))
        self.parser.phase.processEndTag(token)

    def endTagOther(self, token):
        self.parser.parseError("end-tag-after-implied-root",
          {"name": token["name"]})

class InHeadPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler =  utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("title", self.startTagTitle),
            (("noscript", "noframes", "style"), self.startTagNoScriptNoFramesStyle),
            ("script", self.startTagScript),
            (("base", "link", "command", "eventsource"), 
             self.startTagBaseLinkCommandEventsource),
            ("meta", self.startTagMeta),
            ("head", self.startTagHead)
        ])
        self.startTagHandler.default = self.startTagOther

        self. endTagHandler = utils.MethodDispatcher([
            ("head", self.endTagHead),
            ("br", self.endTagBr)
        ])
        self.endTagHandler.default = self.endTagOther

    # helper
    def appendToHead(self, element):
        if self.tree.headPointer is not None:
            self.tree.headPointer.appendChild(element)
        else:
            assert self.parser.innerHTML
            self.tree.openElementsw[-1].appendChild(element)

    # the real thing
    def processEOF (self):
        self.anythingElse()
        self.parser.phase.processEOF()

    def processCharacters(self, token):
        self.anythingElse()
        self.parser.phase.processCharacters(token)

    def startTagHtml(self, token):
        self.parser.phases["inBody"].processStartTag(token)

    def startTagHead(self, token):
        self.parser.parseError("two-heads-are-not-better-than-one")

    def startTagBaseLinkCommandEventsource(self, token):
        self.tree.insertElement(token)
        self.tree.openElements.pop()
        token["selfClosingAcknowledged"] = True

    def startTagMeta(self, token):
        self.tree.insertElement(token)
        self.tree.openElements.pop()
        token["selfClosingAcknowledged"] = True

        attributes = token["data"]
        if self.parser.tokenizer.stream.charEncoding[1] == "tentative":
            if "charset" in attributes:
                codec = inputstream.codecName(attributes["charset"])
                self.parser.tokenizer.stream.changeEncoding(codec)
            elif "content" in attributes:
                data = inputstream.EncodingBytes(
                    attributes["content"].encode(self.parser.tokenizer.stream.charEncoding[0]))
                parser = inputstream.ContentAttrParser(data)
                codec = parser.parse()
                self.parser.tokenizer.stream.changeEncoding(codec)

    def startTagTitle(self, token):
        self.parser.parseRCDataCData(token, "RCDATA")

    def startTagNoScriptNoFramesStyle(self, token):
        #Need to decide whether to implement the scripting-disabled case
        self.parser.parseRCDataCData(token, "CDATA")

    def startTagScript(self, token):
        #I think this is equivalent to the CDATA stuff since we don't execute script
        #self.tree.insertElement(token)
        self.parser.parseRCDataCData(token, "CDATA")

    def startTagOther(self, token):
        self.anythingElse()
        self.parser.phase.processStartTag(token)

    def endTagHead(self, token):
        node = self.parser.tree.openElements.pop()
        assert node.name == "head", "Expected head got %s"%node.name
        self.parser.phase = self.parser.phases["afterHead"]

    def endTagBr(self, token):
        self.anythingElse()
        self.parser.phase.processEndTag(token)

    def endTagOther(self, token):
        self.parser.parseError("unexpected-end-tag", {"name": token["name"]})

    def anythingElse(self):
        self.endTagHead(impliedTagToken("head"))
        

# XXX If we implement a parser for which scripting is disabled we need to
# implement this phase.
#
# class InHeadNoScriptPhase(Phase):

class AfterHeadPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("body", self.startTagBody),
            ("frameset", self.startTagFrameset),
            (("base", "link", "meta", "noframes", "script", "style", "title"),
              self.startTagFromHead),
            ("head", self.startTagHead)
        ])
        self.startTagHandler.default = self.startTagOther
        self.endTagHandler = utils.MethodDispatcher([("br", self.endTagBr)])
        self.endTagHandler.default = self.endTagOther

    def processEOF(self):
        self.anythingElse()
        self.parser.phase.processEOF()

    def processCharacters(self, token):
        self.anythingElse()
        self.parser.phase.processCharacters(token)

    def startTagBody(self, token):
        self.tree.insertElement(token)
        self.parser.phase = self.parser.phases["inBody"]

    def startTagFrameset(self, token):
        self.tree.insertElement(token)
        self.parser.phase = self.parser.phases["inFrameset"]

    def startTagFromHead(self, token):
        self.parser.parseError("unexpected-start-tag-out-of-my-head",
          {"name": token["name"]})
        self.tree.openElements.append(self.tree.headPointer)
        self.parser.phases["inHead"].processStartTag(token)
        for node in self.tree.openElements[::-1]:
            if node.name == "head":
                self.tree.openElements.remove(node)
                break

    def startTagHead(self, token):
        self.parser.parseError("unexpected-start-tag", {"name":token["name"]})

    def startTagOther(self, token):
        self.anythingElse()
        self.parser.phase.processStartTag(token)

    def endTagBr(self, token):
        #This is not currently in the spec
        self.anythingElse()
        self.parser.phase.processEndTag(token)

    def endTagOther(self, token):
        self.parser.parseError("unexpected-end-tag", {"name":token["name"]})

    def anythingElse(self):
        self.tree.insertElement(impliedTagToken("body", "StartTag"))
        self.parser.phase = self.parser.phases["inBody"]


class InBodyPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#in-body
    # the crazy mode
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        #Keep a ref to this for special handling of whitespace in <pre>
        self.processSpaceCharactersNonPre = self.processSpaceCharacters

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            (("base", "link", "meta", "script", "style", "title"),
              self.startTagProcessInHead),
            ("body", self.startTagBody),
            (("address", "article", "aside", "blockquote", "center", "datagrid",
              "details", "dialog", "dir", "div", "dl", "fieldset", "figure",
              "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "listing",
              "menu", "nav", "ol", "p", "pre", "section", "ul"),
              self.startTagCloseP),
            ("form", self.startTagForm),
            (("li", "dd", "dt"), self.startTagListItem),
            ("plaintext",self.startTagPlaintext),
            (headingElements, self.startTagHeading),
            ("a", self.startTagA),
            (("b", "big", "em", "font", "i", "s", "small", "strike", "strong",
              "tt", "u"),self.startTagFormatting),
            ("nobr", self.startTagNobr),
            ("button", self.startTagButton),
            (("applet", "marquee", "object"), self.startTagAppletMarqueeObject),
            ("xmp", self.startTagXmp),
            ("table", self.startTagTable),
            (("area", "basefont", "bgsound", "br", "embed", "img", "param",
              "spacer", "wbr"), self.startTagVoidFormatting),
            ("hr", self.startTagHr),
            ("image", self.startTagImage),
            ("input", self.startTagInput),
            ("isindex", self.startTagIsIndex),
            ("textarea", self.startTagTextarea),
            (("iframe", "noembed", "noframes", "noscript"), self.startTagCdata),
            ("select", self.startTagSelect),
            (("rp", "rt"), self.startTagRpRt),
            (("option", "optgroup"), self.startTagOpt),
            (("caption", "col", "colgroup", "frame", "frameset", "head",
              "tbody", "td", "tfoot", "th", "thead",
              "tr"), self.startTagMisplaced),
            (("event-source", "command"), self.startTagNew)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("body",self.endTagBody),
            ("html",self.endTagHtml),
            (("address", "article", "aside", "blockquote", "center", "datagrid",
              "details", "dialog", "dir", "div", "dl", "fieldset", "figure",
              "footer", "header", "listing", "menu", "nav", "ol", "pre", "section",
              "ul"), self.endTagBlock),
            ("form", self.endTagForm),
            ("p",self.endTagP),
            (("dd", "dt", "li"), self.endTagListItem),
            (headingElements, self.endTagHeading),
            (("a", "b", "big", "em", "font", "i", "nobr", "s", "small",
              "strike", "strong", "tt", "u"), self.endTagFormatting),
            (("applet", "button", "marquee", "object"), self.endTagAppletButtonMarqueeObject),
            ("br", self.endTagBr),
            ])
        self.endTagHandler.default = self.endTagOther

    # helper
    def addFormattingElement(self, token):
        self.tree.insertElement(token)
        self.tree.activeFormattingElements.append(
            self.tree.openElements[-1])

    # the real deal
    def processEOF(self):
        allowed_elements = frozenset(("dd", "dt", "li", "p", "tbody", "td",
                                      "tfoot", "th", "thead", "tr", "body",
                                      "html"))
        for node in self.tree.openElements[::-1]:
            if node.name not in allowed_elements:
                self.parser.parseError("expected-closing-tag-but-got-eof")
                break
        #Stop parsing
    
    def processSpaceCharactersDropNewline(self, token):
        # Sometimes (start of <pre>, <listing>, and <textarea> blocks) we
        # want to drop leading newlines
        data = token["data"]
        self.processSpaceCharacters = self.processSpaceCharactersNonPre
        if (data.startswith("\n") and
            self.tree.openElements[-1].name in ("pre", "listing", "textarea")
            and not self.tree.openElements[-1].hasContent()):
            data = data[1:]
        if data:
            self.tree.reconstructActiveFormattingElements()
            self.tree.insertText(data)

    def processCharacters(self, token):
        # XXX The specification says to do this for every character at the
        # moment, but apparently that doesn't match the real world so we don't
        # do it for space characters.
        self.tree.reconstructActiveFormattingElements()
        self.tree.insertText(token["data"])

    #This matches the current spec but may not match the real world
    def processSpaceCharacters(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.tree.insertText(token["data"])

    def startTagProcessInHead(self, token):
        self.parser.phases["inHead"].processStartTag(token)

    def startTagBody(self, token):
        self.parser.parseError("unexpected-start-tag", {"name": "body"})
        if (len(self.tree.openElements) == 1
            or self.tree.openElements[1].name != "body"):
            assert self.parser.innerHTML
        else:
            for attr, value in token["data"].items():
                if attr not in self.tree.openElements[1].attributes:
                    self.tree.openElements[1].attributes[attr] = value

    def startTagCloseP(self, token):
        if self.tree.elementInScope("p"):
            self.endTagP(impliedTagToken("p"))
        self.tree.insertElement(token)
        if token["name"] in ("pre", "listing"):
            self.processSpaceCharacters = self.processSpaceCharactersDropNewline

    def startTagForm(self, token):
        if self.tree.formPointer:
            self.parser.parseError("unexpected-start-tag", {"name": "form"})
        else:
            if self.tree.elementInScope("p"):
                self.endTagP("p")
            self.tree.insertElement(token)
            self.tree.formPointer = self.tree.openElements[-1]

    def startTagListItem(self, token):
        if self.tree.elementInScope("p"):
            self.endTagP(impliedTagToken("p"))
        stopNames = {"li":("li"), "dd":("dd", "dt"), "dt":("dd", "dt")}
        stopName = stopNames[token["name"]]
        # AT Use reversed in Python 2.4...
        for i, node in enumerate(self.tree.openElements[::-1]):
            if node.name in stopName:
                poppedNodes = []
                for j in range(i+1):
                    poppedNodes.append(self.tree.openElements.pop())
                if i >= 1:
                    self.parser.parseError(
                        i == 1 and "missing-end-tag" or "missing-end-tags",
                        {"name": ", ".join([item.name
                                             for item
                                             in poppedNodes[:-1]])})
                break
        

            # Phrasing elements are all non special, non scoping, non
            # formatting elements
            if (node.name in (specialElements | scopingElements)
              and node.name not in ("address", "div")):
                break
        # Always insert an <li> element.
        self.tree.insertElement(token)

    def startTagPlaintext(self, token):
        if self.tree.elementInScope("p"):
            self.endTagP(impliedTagToken("p"))
        self.tree.insertElement(token)
        self.parser.tokenizer.contentModelFlag = contentModelFlags["PLAINTEXT"]

    def startTagHeading(self, token):
        if self.tree.elementInScope("p"):
            self.endTagP(impliedTagToken("p"))
        # Uncomment the following for IE7 behavior:
        #
        #for item in headingElements:
        #    if self.tree.elementInScope(item):
        #        self.parser.parseError("unexpected-start-tag", {"name": token["name"]})
        #        item = self.tree.openElements.pop()
        #        while item.name not in headingElements:
        #            item = self.tree.openElements.pop()
        #        break
        self.tree.insertElement(token)

    def startTagA(self, token):
        afeAElement = self.tree.elementInActiveFormattingElements("a")
        if afeAElement:
            self.parser.parseError("unexpected-start-tag-implies-end-tag",
              {"startName": "a", "endName": "a"})
            self.endTagFormatting(impliedTagToken("a"))
            if afeAElement in self.tree.openElements:
                self.tree.openElements.remove(afeAElement)
            if afeAElement in self.tree.activeFormattingElements:
                self.tree.activeFormattingElements.remove(afeAElement)
        self.tree.reconstructActiveFormattingElements()
        self.addFormattingElement(token)

    def startTagFormatting(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.addFormattingElement(token)

    def startTagNobr(self, token):
        self.tree.reconstructActiveFormattingElements()
        if self.tree.elementInScope("nobr"):
            self.parser.parseError("unexpected-start-tag-implies-end-tag",
              {"startName": "nobr", "endName": "nobr"})
            self.processEndTag(impliedTagToken("nobr"))
            # XXX Need tests that trigger the following
            self.tree.reconstructActiveFormattingElements()
        self.addFormattingElement(token)

    def startTagButton(self, token):
        if self.tree.elementInScope("button"):
            self.parser.parseError("unexpected-start-tag-implies-end-tag",
              {"startName": "button", "endName": "button"})
            self.processEndTag(impliedTagToken("button"))
            self.parser.phase.processStartTag(token)
        else:
            self.tree.reconstructActiveFormattingElements()
            self.tree.insertElement(token)
            self.tree.activeFormattingElements.append(Marker)

    def startTagAppletMarqueeObject(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.tree.insertElement(token)
        self.tree.activeFormattingElements.append(Marker)

    def startTagXmp(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.parser.parseRCDataCData(token, "CDATA")

    def startTagTable(self, token):
        if self.tree.elementInScope("p"):
            self.processEndTag(impliedTagToken("p"))
        self.tree.insertElement(token)
        self.parser.phase = self.parser.phases["inTable"]

    def startTagVoidFormatting(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.tree.insertElement(token)
        self.tree.openElements.pop()

    def startTagHr(self, token):
        if self.tree.elementInScope("p"):
            self.endTagP(impliedTagToken("p"))
        self.tree.insertElement(token)
        self.tree.openElements.pop()

    def startTagImage(self, token):
        # No really...
        self.parser.parseError("unexpected-start-tag-treated-as",
          {"originalName": "image", "newName": "img"})
        self.processStartTag(impliedTagToken("img", "StartTag",
                                             attributes=token["data"],
                                             selfClosing=token["selfClosing"]))

    def startTagInput(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.tree.insertElement(token)
        if self.tree.formPointer:
            # XXX Not exactly sure what to do here
            self.tree.openElements[-1].form = self.tree.formPointer
        self.tree.openElements.pop()

    def startTagIsIndex(self, token):
        self.parser.parseError("deprecated-tag", {"name": "isindex"})
        if self.tree.formPointer:
            return
        self.processStartTag(impliedTagToken("form", "StartTag"))
        self.processStartTag(impliedTagToken("hr", "StartTag"))
        self.processStartTag(impliedTagToken("p", "StartTag"))
        self.processStartTag(impliedTagToken("label", "StartTag"))
        # XXX Localization ...
        self.processCharacters(
            {"type":tokenTypes["Characters"], 
             "data":"This is a searchable index. Insert your search keywords here: "})
        attributes = token["data"].copy() #don't really need a copy here I think
        attributes["name"] = "isindex"
        self.processStartTag(impliedTagToken("input", "StartTag", 
                                             attributes = attributes,
                                             selfClosing = 
                                             token["selfClosing"]))
        self.processEndTag(impliedTagToken("label"))
        self.processEndTag(impliedTagToken("p"))
        self.processStartTag(impliedTagToken("hr", "StartTag"))
        self.processEndTag(impliedTagToken("form"))

    def startTagTextarea(self, token):
        # XXX Form element pointer checking here as well...
        self.tree.insertElement(token)
        self.parser.tokenizer.contentModelFlag = contentModelFlags["RCDATA"]
        self.processSpaceCharacters = self.processSpaceCharactersDropNewline

    def startTagCdata(self, token):
        """iframe, noembed noframes, noscript(if scripting enabled)"""
        self.parser.parseRCDataCData(token, "CDATA")

    def startTagOpt(self, token):
        if self.tree.elementInScope("option"):
            self.parser.phase.processEndTag(impliedTagToken("option"))
        self.tree.reconstructActiveFormattingElements()
        self.parser.tree.insertElement(token)

    def startTagSelect(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.tree.insertElement(token)
        if self.parser.phase in (self.parser.phases["inTable"],
                                 self.parser.phases["inCaption"],
                                 self.parser.phases["inColumnGroup"],
                                 self.parser.phases["inTableBody"], 
                                 self.parser.phases["inRow"],
                                 self.parser.phases["inCell"]):
            self.parser.phase = self.parser.phases["inSelectInTable"]
        else:
            self.parser.phase = self.parser.phases["inSelect"]

    def startTagRpRt(self, token):
        if self.tree.elementInScope("ruby"):
            self.tree.generateImpliedEndTags()
            if self.tree.openElements[-1].name != "ruby":
                self.parser.parseError()
                while self.tree.openElements[-1].name != "ruby":
                    self.tree.openElements.pop()
        self.tree.insertElement(token)

    def startTagMisplaced(self, token):
        """ Elements that should be children of other elements that have a
        different insertion mode; here they are ignored
        "caption", "col", "colgroup", "frame", "frameset", "head",
        "option", "optgroup", "tbody", "td", "tfoot", "th", "thead",
        "tr", "noscript"
        """
        self.parser.parseError("unexpected-start-tag-ignored", {"name": token["name"]})

    def startTagNew(self, token):
        """New HTML5 elements, "event-source", "section", "nav",
        "article", "aside", "header", "footer", "datagrid", "command"
        """
        #2007-08-30 - MAP - commenting out this write to sys.stderr because
        #  it's really annoying me when I run the validator tests
        #sys.stderr.write("Warning: Undefined behaviour for start tag %s"%name)
        self.startTagOther(token)
        #raise NotImplementedError

    def startTagOther(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.tree.insertElement(token)

    def endTagP(self, token):
        if self.tree.elementInScope("p"):
            self.tree.generateImpliedEndTags("p")
        if self.tree.openElements[-1].name != "p":
            self.parser.parseError("unexpected-end-tag", {"name": "p"})
        if self.tree.elementInScope("p"):
            while self.tree.elementInScope("p"):
                self.tree.openElements.pop()
        else:
            self.startTagCloseP(impliedTagToken("p", "StartTag"))
            self.endTagP(impliedTagToken("p"))

    def endTagBody(self, token):
        # XXX Need to take open <p> tags into account here. We shouldn't imply
        # </p> but we should not throw a parse error either. Specification is
        # likely to be updated.
        if (len(self.tree.openElements) == 1 or
            self.tree.openElements[1].name != "body"):
            # innerHTML case
            self.parser.parseError()
            return
        elif self.tree.openElements[-1].name != "body":
            for node in self.tree.openElements[2:]:
                if node.name not in frozenset(("dd", "dt", "li", "p",
                                               "tbody", "td", "tfoot",
                                               "th", "thead", "tr")):
                    #Not sure this is the correct name for the parse error
                    self.parser.parseError(
                        "expected-one-end-tag-but-got-another",
                        {"expectedName": "body", "gotName": node.name})
                    break
        self.parser.phase = self.parser.phases["afterBody"]

    def endTagHtml(self, token):
        self.endTagBody(impliedTagToken("body"))
        if not self.parser.innerHTML:
            self.parser.phase.processEndTag(token)

    def endTagBlock(self, token):
        #Put us back in the right whitespace handling mode
        if token["name"] == "pre":
            self.processSpaceCharacters = self.processSpaceCharactersNonPre
        inScope = self.tree.elementInScope(token["name"])
        if inScope:
            self.tree.generateImpliedEndTags()
        if self.tree.openElements[-1].name != token["name"]:
             self.parser.parseError("end-tag-too-early", {"name": token["name"]})
        if inScope:
            node = self.tree.openElements.pop()
            while node.name != token["name"]:
                node = self.tree.openElements.pop()

    def endTagForm(self, token):
        self.tree.formPointer = None
        if not self.tree.elementInScope(token["name"]):
            self.parser.parseError("unexpected-end-tag",
                                   {"name":"form"})
        else:
            self.tree.generateImpliedEndTags()
            if self.tree.openElements[-1].name != token["name"]:
                self.parser.parseError("end-tag-too-early-ignored",
                                       {"name": "form"})
            node = self.tree.openElements.pop()
            while node.name != token["name"]:
                node = self.tree.openElements.pop()

    def endTagListItem(self, token):
        # AT Could merge this with the Block case
        if self.tree.elementInScope(token["name"]):
            self.tree.generateImpliedEndTags(token["name"])
        
        if self.tree.openElements[-1].name != token["name"]:
            self.parser.parseError("end-tag-too-early", {"name": token["name"]})

        if self.tree.elementInScope(token["name"]):
            node = self.tree.openElements.pop()
            while node.name != token["name"]:
                node = self.tree.openElements.pop()

    def endTagHeading(self, token):
        for item in headingElements:
            if self.tree.elementInScope(item):
                self.tree.generateImpliedEndTags()
                break
        if self.tree.openElements[-1].name != token["name"]:
            self.parser.parseError("end-tag-too-early", {"name": token["name"]})

        for item in headingElements:
            if self.tree.elementInScope(item):
                item = self.tree.openElements.pop()
                while item.name not in headingElements:
                    item = self.tree.openElements.pop()
                break

    def endTagFormatting(self, token):
        """The much-feared adoption agency algorithm"""
        # http://www.whatwg.org/specs/web-apps/current-work/#adoptionAgency
        # XXX Better parseError messages appreciated.
        name = token["name"]
        while True:
            # Step 1 paragraph 1
            afeElement = self.tree.elementInActiveFormattingElements(
                token["name"])
            if not afeElement or (afeElement in self.tree.openElements and
              not self.tree.elementInScope(afeElement.name)):
                self.parser.parseError("adoption-agency-1.1", {"name": token["name"]})
                return

            # Step 1 paragraph 2
            elif afeElement not in self.tree.openElements:
                self.parser.parseError("adoption-agency-1.2", {"name": token["name"]})
                self.tree.activeFormattingElements.remove(afeElement)
                return

            # Step 1 paragraph 3
            if afeElement != self.tree.openElements[-1]:
                self.parser.parseError("adoption-agency-1.3", {"name": token["name"]})

            # Step 2
            # Start of the adoption agency algorithm proper
            afeIndex = self.tree.openElements.index(afeElement)
            furthestBlock = None
            for element in self.tree.openElements[afeIndex:]:
                if element.name in specialElements | scopingElements:
                    furthestBlock = element
                    break

            # Step 3
            if furthestBlock is None:
                element = self.tree.openElements.pop()
                while element != afeElement:
                    element = self.tree.openElements.pop()
                self.tree.activeFormattingElements.remove(element)
                return
            commonAncestor = self.tree.openElements[afeIndex-1]

            # Step 5
            if furthestBlock.parent:
                furthestBlock.parent.removeChild(furthestBlock)

            # Step 6
            # The bookmark is supposed to help us identify where to reinsert
            # nodes in step 12. We have to ensure that we reinsert nodes after
            # the node before the active formatting element. Note the bookmark
            # can move in step 7.4
            bookmark = self.tree.activeFormattingElements.index(afeElement)

            # Step 7
            lastNode = node = furthestBlock
            while True:
                # AT replace this with a function and recursion?
                # Node is element before node in open elements
                node = self.tree.openElements[
                    self.tree.openElements.index(node)-1]
                while node not in self.tree.activeFormattingElements:
                    tmpNode = node
                    node = self.tree.openElements[
                        self.tree.openElements.index(node)-1]
                    self.tree.openElements.remove(tmpNode)
                # Step 7.3
                if node == afeElement:
                    break
                # Step 7.4
                if lastNode == furthestBlock:
                    bookmark = self.tree.activeFormattingElements.\
                      index(node) + 1
                # Step 7.5
                cite = node.parent
                if node.hasContent():
                    clone = node.cloneNode()
                    # Replace node with clone
                    self.tree.activeFormattingElements[
                      self.tree.activeFormattingElements.index(node)] = clone
                    self.tree.openElements[
                      self.tree.openElements.index(node)] = clone
                    node = clone
                # Step 7.6
                # Remove lastNode from its parents, if any
                if lastNode.parent:
                    lastNode.parent.removeChild(lastNode)
                node.appendChild(lastNode)
                # Step 7.7
                lastNode = node
                # End of inner loop

            # Step 8
            if lastNode.parent:
                lastNode.parent.removeChild(lastNode)
            commonAncestor.appendChild(lastNode)

            # Step 9
            clone = afeElement.cloneNode()

            # Step 10
            furthestBlock.reparentChildren(clone)

            # Step 11
            furthestBlock.appendChild(clone)

            # Step 12
            self.tree.activeFormattingElements.remove(afeElement)
            self.tree.activeFormattingElements.insert(bookmark, clone)

            # Step 13
            self.tree.openElements.remove(afeElement)
            self.tree.openElements.insert(
              self.tree.openElements.index(furthestBlock) + 1, clone)

    def endTagAppletButtonMarqueeObject(self, token):
        if self.tree.elementInScope(token["name"]):
            self.tree.generateImpliedEndTags()
        if self.tree.openElements[-1].name != token["name"]:
            self.parser.parseError("end-tag-too-early", {"name": token["name"]})

        if self.tree.elementInScope(token["name"]):
            element = self.tree.openElements.pop()
            while element.name != token["name"]:
                element = self.tree.openElements.pop()
            self.tree.clearActiveFormattingElements()

    def endTagBr(self, token):
        self.parser.parseError("unexpected-end-tag-treated-as",
          {"originalName": "br", "newName": "br element"})
        self.tree.reconstructActiveFormattingElements()
        self.tree.insertElement(impliedTagToken("br", "StartTag"))
        self.tree.openElements.pop()

    def endTagOther(self, token):
        for node in self.tree.openElements[::-1]:
            if node.name == token["name"]:
                self.tree.generateImpliedEndTags()
                if self.tree.openElements[-1].name != token["name"]:
                    self.parser.parseError("unexpected-end-tag", {"name": token["name"]})
                while self.tree.openElements.pop() != node:
                    pass
                break
            else:
                if node.name in specialElements | scopingElements:
                    self.parser.parseError("unexpected-end-tag", {"name": token["name"]})
                    break

class InCDataRCDataPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)
        self.startTagHandler = utils.MethodDispatcher([])
        self.startTagHandler.default = self.startTagOther
        self.endTagHandler = utils.MethodDispatcher([
                ("script", self.endTagScript)])
        self.endTagHandler.default = self.endTagOther

    def processCharacters(self, token):
        self.tree.insertText(token["data"])
    
    def processEOF(self):
        self.parser.parseError("expected-named-closing-tag-but-got-eof", 
                               self.tree.openElements[-1].name)
        self.tree.openElements.pop()
        self.parser.phase = self.parser.originalPhase
        self.parser.phase.processEOF()

    def startTagOther(self, token):
        assert False, "Tried to process start tag %s in (R)CDATA mode"%name

    def endTagScript(self, token):
        node = self.tree.openElements.pop()
        assert node.name == "script"
        self.parser.phase = self.parser.originalPhase
        #The rest of this method is all stuff that only happens if
        #document.write works
    
    def endTagOther(self, token):
        node = self.tree.openElements.pop()
        self.parser.phase = self.parser.originalPhase

class InTablePhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#in-table
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)
        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("caption", self.startTagCaption),
            ("colgroup", self.startTagColgroup),
            ("col", self.startTagCol),
            (("tbody", "tfoot", "thead"), self.startTagRowGroup),
            (("td", "th", "tr"), self.startTagImplyTbody),
            ("table", self.startTagTable),
            (("style", "script"), self.startTagStyleScript),
            ("input", self.startTagInput)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("table", self.endTagTable),
            (("body", "caption", "col", "colgroup", "html", "tbody", "td",
              "tfoot", "th", "thead", "tr"), self.endTagIgnore)
        ])
        self.endTagHandler.default = self.endTagOther

    # helper methods
    def clearStackToTableContext(self):
        # "clear the stack back to a table context"
        while self.tree.openElements[-1].name not in ("table", "html"):
            #self.parser.parseError("unexpected-implied-end-tag-in-table",
            #  {"name":  self.tree.openElements[-1].name})
            self.tree.openElements.pop()
        # When the current node is <html> it's an innerHTML case

    def getCurrentTable(self):
        i = -1
        while self.tree.openElements[i].name != "table":
             i -= 1
        return self.tree.openElements[i]

    # processing methods
    def processEOF(self):
        if self.tree.openElements[-1].name != "html":
            self.parser.parseError("eof-in-table")
        else:
            assert self.parser.innerHTML
        #Stop parsing

    def processSpaceCharacters(self, token):
        if "tainted" not in self.getCurrentTable()._flags:
            self.tree.insertText(token["data"])
        else:
            self.processCharacters(token)

    def processCharacters(self, token):
        if self.tree.openElements[-1].name in ("style", "script"):
           self.tree.insertText(token)
        else:
            if "tainted" not in self.getCurrentTable()._flags:
                self.parser.parseError("unexpected-char-implies-table-voodoo")
                self.getCurrentTable()._flags.append("tainted")
            # Do the table magic!
            self.tree.insertFromTable = True
            self.parser.phases["inBody"].processCharacters(token)
            self.tree.insertFromTable = False

    def startTagCaption(self, token):
        self.clearStackToTableContext()
        self.tree.activeFormattingElements.append(Marker)
        self.tree.insertElement(token)
        self.parser.phase = self.parser.phases["inCaption"]

    def startTagColgroup(self, token):
        self.clearStackToTableContext()
        self.tree.insertElement(token)
        self.parser.phase = self.parser.phases["inColumnGroup"]

    def startTagCol(self, token):
        self.startTagColgroup(impliedTagToken("colgroup", "StartTag"))
        self.parser.phase.processStartTag(token)

    def startTagRowGroup(self, token):
        self.clearStackToTableContext()
        self.tree.insertElement(token)
        self.parser.phase = self.parser.phases["inTableBody"]

    def startTagImplyTbody(self, token):
        self.startTagRowGroup(impliedTagToken("tbody", "StartTag"))
        self.parser.phase.processStartTag(token)

    def startTagTable(self, token):
        self.parser.parseError("unexpected-start-tag-implies-end-tag",
          {"startName": "table", "endName": "table"})
        self.parser.phase.processEndTag(impliedTagToken("table"))
        if not self.parser.innerHTML:
            self.parser.phase.processStartTag(token)

    def startTagStyleScript(self, token):
        if "tainted" not in self.getCurrentTable()._flags:
            self.parser.phases["inHead"].processStartTag(token)
        else:
            self.startTagOther(token)

    def startTagInput(self, token):
        if "type" in token["data"] and token["data"]["type"].translate(asciiUpper2Lower) == "hidden" and "tainted" not in self.getCurrentTable()._flags:
            self.parser.parseError("unexpected-hidden-input-in-table")
            self.tree.insertElement(token)
            # XXX associate with form
            self.tree.openElements.pop()
        else:
            self.startTagOther(token)

    def startTagOther(self, token):
        self.parser.parseError("unexpected-start-tag-implies-table-voodoo", {"name": token["name"]})
        if "tainted" not in self.getCurrentTable()._flags:
            self.getCurrentTable()._flags.append("tainted")
        # Do the table magic!
        self.tree.insertFromTable = True
        self.parser.phases["inBody"].processStartTag(token)
        self.tree.insertFromTable = False

    def endTagTable(self, token):
        if self.tree.elementInScope("table", True):
            self.tree.generateImpliedEndTags()
            if self.tree.openElements[-1].name != "table":
                self.parser.parseError("end-tag-too-early-named",
                  {"gotName": "table",
                   "expectedName": self.tree.openElements[-1].name})
            while self.tree.openElements[-1].name != "table":
                self.tree.openElements.pop()
            self.tree.openElements.pop()
            self.parser.resetInsertionMode()
        else:
            # innerHTML case
            assert self.parser.innerHTML
            self.parser.parseError()

    def endTagIgnore(self, token):
        self.parser.parseError("unexpected-end-tag", {"name": token["name"]})

    def endTagOther(self, token):
        self.parser.parseError("unexpected-end-tag-implies-table-voodoo", {"name": token["name"]})
        if "tainted" not in self.getCurrentTable()._flags:
            self.getCurrentTable()._flags.append("tainted")
        # Do the table magic!
        self.tree.insertFromTable = True
        self.parser.phases["inBody"].processEndTag(token)
        self.tree.insertFromTable = False


class InCaptionPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#in-caption
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            (("caption", "col", "colgroup", "tbody", "td", "tfoot", "th",
              "thead", "tr"), self.startTagTableElement)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("caption", self.endTagCaption),
            ("table", self.endTagTable),
            (("body", "col", "colgroup", "html", "tbody", "td", "tfoot", "th",
              "thead", "tr"), self.endTagIgnore)
        ])
        self.endTagHandler.default = self.endTagOther

    def ignoreEndTagCaption(self):
        return not self.tree.elementInScope("caption", True)

    def processEOF(self):
        self.parser.phases["inBody"].processEOF()

    def processCharacters(self, token):
        self.parser.phases["inBody"].processCharacters(token)

    def startTagTableElement(self, token):
        self.parser.parseError()
        #XXX Have to duplicate logic here to find out if the tag is ignored
        ignoreEndTag = self.ignoreEndTagCaption()
        self.parser.phase.processEndTag(impliedTagToken("caption"))
        if not ignoreEndTag:
            self.parser.phase.processStartTag(token)

    def startTagOther(self, token):
        self.parser.phases["inBody"].processStartTag(token)

    def endTagCaption(self, token):
        if not self.ignoreEndTagCaption():
            # AT this code is quite similar to endTagTable in "InTable"
            self.tree.generateImpliedEndTags()
            if self.tree.openElements[-1].name != "caption":
                self.parser.parseError("expected-one-end-tag-but-got-another",
                  {"gotName": "caption",
                   "expectedName": self.tree.openElements[-1].name})
            while self.tree.openElements[-1].name != "caption":
                self.tree.openElements.pop()
            self.tree.openElements.pop()
            self.tree.clearActiveFormattingElements()
            self.parser.phase = self.parser.phases["inTable"]
        else:
            # innerHTML case
            assert self.parser.innerHTML
            self.parser.parseError()

    def endTagTable(self, token):
        self.parser.parseError()
        ignoreEndTag = self.ignoreEndTagCaption()
        self.parser.phase.processEndTag(impliedTagToken("caption"))
        if not ignoreEndTag:
            self.parser.phase.processEndTag(token)

    def endTagIgnore(self, token):
        self.parser.parseError("unexpected-end-tag", {"name": token["name"]})

    def endTagOther(self, token):
        self.parser.phases["inBody"].processEndTag(token)


class InColumnGroupPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#in-column

    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("col", self.startTagCol)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("colgroup", self.endTagColgroup),
            ("col", self.endTagCol)
        ])
        self.endTagHandler.default = self.endTagOther

    def ignoreEndTagColgroup(self):
        return self.tree.openElements[-1].name == "html"

    def processEOF(self):
        if self.tree.openElements[-1].name == "html":
            assert self.parser.innerHTML
            return
        else:
            ignoreEndTag = self.ignoreEndTagColgroup()
            self.endTagColgroup("colgroup")
            if not ignoreEndTag:
                self.parser.phase.processEOF()

    def processCharacters(self, token):
        ignoreEndTag = self.ignoreEndTagColgroup()
        self.endTagColgroup(impliedTagToken("colgroup"))
        if not ignoreEndTag:
            self.parser.phase.processCharacters(token)

    def startTagCol(self, token):
        self.tree.insertElement(token)
        self.tree.openElements.pop()

    def startTagOther(self, token):
        ignoreEndTag = self.ignoreEndTagColgroup()
        self.endTagColgroup("colgroup")
        if not ignoreEndTag:
            self.parser.phase.processStartTag(token)

    def endTagColgroup(self, token):
        if self.ignoreEndTagColgroup():
            # innerHTML case
            assert self.parser.innerHTML
            self.parser.parseError()
        else:
            self.tree.openElements.pop()
            self.parser.phase = self.parser.phases["inTable"]

    def endTagCol(self, token):
        self.parser.parseError("no-end-tag", {"name": "col"})

    def endTagOther(self, token):
        ignoreEndTag = self.ignoreEndTagColgroup()
        self.endTagColgroup("colgroup")
        if not ignoreEndTag:
            self.parser.phase.processEndTag(token)


class InTableBodyPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#in-table0
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)
        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("tr", self.startTagTr),
            (("td", "th"), self.startTagTableCell),
            (("caption", "col", "colgroup", "tbody", "tfoot", "thead"),
             self.startTagTableOther)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            (("tbody", "tfoot", "thead"), self.endTagTableRowGroup),
            ("table", self.endTagTable),
            (("body", "caption", "col", "colgroup", "html", "td", "th",
              "tr"), self.endTagIgnore)
        ])
        self.endTagHandler.default = self.endTagOther

    # helper methods
    def clearStackToTableBodyContext(self):
        while self.tree.openElements[-1].name not in ("tbody", "tfoot",
          "thead", "html"):
            #self.parser.parseError("unexpected-implied-end-tag-in-table",
            #  {"name": self.tree.openElements[-1].name})
            self.tree.openElements.pop()
        if self.tree.openElements[-1].name == "html":
            assert self.parser.innerHTML

    # the rest
    def processEOF(self):
        self.parser.phases["inTable"].processEOF()
    
    def processSpaceCharacters(self, token):
        self.parser.phases["inTable"].processSpaceCharacters(token)

    def processCharacters(self, token):
        self.parser.phases["inTable"].processCharacters(token)

    def startTagTr(self, token):
        self.clearStackToTableBodyContext()
        self.tree.insertElement(token)
        self.parser.phase = self.parser.phases["inRow"]

    def startTagTableCell(self, token):
        self.parser.parseError("unexpected-cell-in-table-body", 
                               {"name": token["name"]})
        self.startTagTr(impliedTagToken("tr", "StartTag"))
        self.parser.phase.processStartTag(token)

    def startTagTableOther(self, token):
        # XXX AT Any ideas on how to share this with endTagTable?
        if (self.tree.elementInScope("tbody", True) or
            self.tree.elementInScope("thead", True) or
            self.tree.elementInScope("tfoot", True)):
            self.clearStackToTableBodyContext()
            self.endTagTableRowGroup(
                impliedTagToken(self.tree.openElements[-1].name))
            self.parser.phase.processStartTag(token)
        else:
            # innerHTML case
            self.parser.parseError()

    def startTagOther(self, token):
        self.parser.phases["inTable"].processStartTag(token)

    def endTagTableRowGroup(self, token):
        if self.tree.elementInScope(token["name"], True):
            self.clearStackToTableBodyContext()
            self.tree.openElements.pop()
            self.parser.phase = self.parser.phases["inTable"]
        else:
            self.parser.parseError("unexpected-end-tag-in-table-body",
              {"name": token["name"]})

    def endTagTable(self, token):
        if (self.tree.elementInScope("tbody", True) or
            self.tree.elementInScope("thead", True) or
            self.tree.elementInScope("tfoot", True)):
            self.clearStackToTableBodyContext()
            self.endTagTableRowGroup(
                impliedTagToken(self.tree.openElements[-1].name))
            self.parser.phase.processEndTag(token)
        else:
            # innerHTML case
            self.parser.parseError()

    def endTagIgnore(self, token):
        self.parser.parseError("unexpected-end-tag-in-table-body",
          {"name": token["name"]})

    def endTagOther(self, token):
        self.parser.phases["inTable"].processEndTag(token)


class InRowPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#in-row
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)
        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            (("td", "th"), self.startTagTableCell),
            (("caption", "col", "colgroup", "tbody", "tfoot", "thead",
              "tr"), self.startTagTableOther)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("tr", self.endTagTr),
            ("table", self.endTagTable),
            (("tbody", "tfoot", "thead"), self.endTagTableRowGroup),
            (("body", "caption", "col", "colgroup", "html", "td", "th"),
              self.endTagIgnore)
        ])
        self.endTagHandler.default = self.endTagOther

    # helper methods (XXX unify this with other table helper methods)
    def clearStackToTableRowContext(self):
        while self.tree.openElements[-1].name not in ("tr", "html"):
            self.parser.parseError("unexpected-implied-end-tag-in-table-row",
              {"name": self.tree.openElements[-1].name})
            self.tree.openElements.pop()

    def ignoreEndTagTr(self):
        return not self.tree.elementInScope("tr", tableVariant=True)

    # the rest
    def processEOF(self):
        self.parser.phases["inTable"].processEOF()
    
    def processSpaceCharacters(self, token):
        self.parser.phases["inTable"].processSpaceCharacters(token)        

    def processCharacters(self, token):
        self.parser.phases["inTable"].processCharacters(token)

    def startTagTableCell(self, token):
        self.clearStackToTableRowContext()
        self.tree.insertElement(token)
        self.parser.phase = self.parser.phases["inCell"]
        self.tree.activeFormattingElements.append(Marker)

    def startTagTableOther(self, token):
        ignoreEndTag = self.ignoreEndTagTr()
        self.endTagTr("tr")
        # XXX how are we sure it's always ignored in the innerHTML case?
        if not ignoreEndTag:
            self.parser.phase.processStartTag(token)

    def startTagOther(self, token):
        self.parser.phases["inTable"].processStartTag(token)

    def endTagTr(self, token):
        if not self.ignoreEndTagTr():
            self.clearStackToTableRowContext()
            self.tree.openElements.pop()
            self.parser.phase = self.parser.phases["inTableBody"]
        else:
            # innerHTML case
            assert self.parser.innerHTML
            self.parser.parseError()

    def endTagTable(self, token):
        ignoreEndTag = self.ignoreEndTagTr()
        self.endTagTr("tr")
        # Reprocess the current tag if the tr end tag was not ignored
        # XXX how are we sure it's always ignored in the innerHTML case?
        if not ignoreEndTag:
            self.parser.phase.processEndTag(token)

    def endTagTableRowGroup(self, token):
        if self.tree.elementInScope(token["name"], True):
            self.endTagTr("tr")
            self.parser.phase.processEndTag(token)
        else:
            # innerHTML case
            self.parser.parseError()

    def endTagIgnore(self, token):
        self.parser.parseError("unexpected-end-tag-in-table-row",
            {"name": token["name"]})

    def endTagOther(self, token):
        self.parser.phases["inTable"].processEndTag(token)

class InCellPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#in-cell
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)
        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            (("caption", "col", "colgroup", "tbody", "td", "tfoot", "th",
              "thead", "tr"), self.startTagTableOther)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            (("td", "th"), self.endTagTableCell),
            (("body", "caption", "col", "colgroup", "html"), self.endTagIgnore),
            (("table", "tbody", "tfoot", "thead", "tr"), self.endTagImply)
        ])
        self.endTagHandler.default = self.endTagOther

    # helper
    def closeCell(self):
        if self.tree.elementInScope("td", True):
            self.endTagTableCell(impliedTagToken("td"))
        elif self.tree.elementInScope("th", True):
            self.endTagTableCell(impliedTagToken("th"))

    # the rest
    def processEOF(self):
        self.parser.phases["inBody"].processEOF()
        
    def processCharacters(self, token):
        self.parser.phases["inBody"].processCharacters(token)

    def startTagTableOther(self, token):
        if (self.tree.elementInScope("td", True) or
            self.tree.elementInScope("th", True)):
            self.closeCell()
            self.parser.phase.processStartTag(token)
        else:
            # innerHTML case
            self.parser.parseError()

    def startTagOther(self, token):
        self.parser.phases["inBody"].processStartTag(token)
        # Optimize this for subsequent invocations. Can't do this initially
        # because self.phases doesn't really exist at that point.
        self.startTagHandler.default =\
          self.parser.phases["inBody"].processStartTag

    def endTagTableCell(self, token):
        if self.tree.elementInScope(token["name"], True):
            self.tree.generateImpliedEndTags(token["name"])
            if self.tree.openElements[-1].name != token["name"]:
                self.parser.parseError("unexpected-cell-end-tag",
                  {"name": token["name"]})
                while True:
                    node = self.tree.openElements.pop()
                    if node.name == token["name"]:
                        break
            else:
                self.tree.openElements.pop()
            self.tree.clearActiveFormattingElements()
            self.parser.phase = self.parser.phases["inRow"]
        else:
            self.parser.parseError("unexpected-end-tag", {"name": token["name"]})

    def endTagIgnore(self, token):
        self.parser.parseError("unexpected-end-tag", {"name": token["name"]})

    def endTagImply(self, token):
        if self.tree.elementInScope(token["name"], True):
            self.closeCell()
            self.parser.phase.processEndTag(token)
        else:
            # sometimes innerHTML case
            self.parser.parseError()

    def endTagOther(self, token):
        self.parser.phases["inBody"].processEndTag(token)
        # Optimize this for subsequent invocations. Can't do this initially
        # because self.phases doesn't really exist at that point.
        self.endTagHandler.default = self.parser.phases["inBody"].processEndTag


class InSelectPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("option", self.startTagOption),
            ("optgroup", self.startTagOptgroup),
            ("select", self.startTagSelect),
            ("input", self.startTagInput)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("option", self.endTagOption),
            ("optgroup", self.endTagOptgroup),
            ("select", self.endTagSelect),
            (("caption", "table", "tbody", "tfoot", "thead", "tr", "td",
              "th"), self.endTagTableElements)
        ])
        self.endTagHandler.default = self.endTagOther

    # http://www.whatwg.org/specs/web-apps/current-work/#in-select
    def processEOF(self):
        if self.tree.openElements[-1].name != "html":
            self.parser.parseError("eof-in-select")
        else:
            assert self.parser.innerHtml

    def processCharacters(self, token):
        self.tree.insertText(token["data"])

    def startTagOption(self, token):
        # We need to imply </option> if <option> is the current node.
        if self.tree.openElements[-1].name == "option":
            self.tree.openElements.pop()
        self.tree.insertElement(token)

    def startTagOptgroup(self, token):
        if self.tree.openElements[-1].name == "option":
            self.tree.openElements.pop()
        if self.tree.openElements[-1].name == "optgroup":
            self.tree.openElements.pop()
        self.tree.insertElement(token)

    def startTagSelect(self, token):
        self.parser.parseError("unexpected-select-in-select")
        self.endTagSelect("select")

    def startTagInput(self, token):
        self.parser.parseError("unexpected-input-in-select")
        self.endTagSelect("select")
        self.parser.phase.processStartTag(token)

    def startTagOther(self, token):
        self.parser.parseError("unexpected-start-tag-in-select",
          {"name": token["name"]})

    def endTagOption(self, token):
        if self.tree.openElements[-1].name == "option":
            self.tree.openElements.pop()
        else:
            self.parser.parseError("unexpected-end-tag-in-select",
              {"name": "option"})

    def endTagOptgroup(self, token):
        # </optgroup> implicitly closes <option>
        if (self.tree.openElements[-1].name == "option" and
            self.tree.openElements[-2].name == "optgroup"):
            self.tree.openElements.pop()
        # It also closes </optgroup>
        if self.tree.openElements[-1].name == "optgroup":
            self.tree.openElements.pop()
        # But nothing else
        else:
            self.parser.parseError("unexpected-end-tag-in-select",
              {"name": "optgroup"})

    def endTagSelect(self, token):
        if self.tree.elementInScope("select", True):
            node = self.tree.openElements.pop()
            while node.name != "select":
                node = self.tree.openElements.pop()
            self.parser.resetInsertionMode()
        else:
            # innerHTML case
            self.parser.parseError()

    def endTagTableElements(self, token):
        self.parser.parseError("unexpected-end-tag-in-select",
          {"name": token["name"]})
        if self.tree.elementInScope(token["name"], True):
            self.endTagSelect("select")
            self.parser.phase.processEndTag(token)

    def endTagOther(self, token):
        self.parser.parseError("unexpected-end-tag-in-select",
          {"name": token["name"]})


class InSelectInTablePhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            (("caption", "table", "tbody", "tfoot", "thead", "tr", "td", "th"), self.startTagTable)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            (("caption", "table", "tbody", "tfoot", "thead", "tr", "td", "th"), self.endTagTable)
        ])
        self.endTagHandler.default = self.endTagOther

    def processEOF(self):
        self.parser.phases["inSelect"].processEOF()

    def processCharacters(self, token):
        self.parser.phases["inSelect"].processCharacters(token)
    
    def startTagTable(self, token):
        self.parser.parseError("unexpected-table-element-start-tag-in-select-in-table", {"name": token["name"]})
        self.endTagOther(impliedTagToken("select"))
        self.parser.phase.processStartTag(token)

    def startTagOther(self, token):
        self.parser.phases["inSelect"].processStartTag(token)

    def endTagTable(self, token):
        self.parser.parseError("unexpected-table-element-end-tag-in-select-in-table", {"name": token["name"]})
        if self.tree.elementInScope(token["name"]):
            self.endTagOther(impliedTagToken("select"))
            self.parser.phase.processEndTag(token)

    def endTagOther(self, token):
        self.parser.phases["inSelect"].processEndTag(token)


class InForeignContentPhase(Phase):
        def __init__(self, parser, tree):
            Phase.__init__(self, parser, tree)
            self.secondardInsertionMode = None

        def processStartTag(self, token):
            
            self.startTagHandler = utils.MethodDispatcher([
                    ("html", self.startTagHtml)
                    ])
            self.startTagHandler.default = self.startTagOther

            self.endTagHandler = utils.MethodDispatcher([("html", self.endTagHtml)])
            self.endTagHandler.default = self.endTagOther

class AfterBodyPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
                ("html", self.startTagHtml)
                ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([("html", self.endTagHtml)])
        self.endTagHandler.default = self.endTagOther

    def processEOF(self):
        #Stop parsing
        pass
    
    def processComment(self, token):
        # This is needed because data is to be appended to the <html> element
        # here and not to whatever is currently open.
        self.tree.insertComment(token, self.tree.openElements[0])

    def processCharacters(self, token):
        self.parser.parseError("unexpected-char-after-body")
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processCharacters(token)

    def startTagHtml(self, token):
        self.parser.phases["inBody"].processStartTag(token)

    def startTagOther(self, token):
        self.parser.parseError("unexpected-start-tag-after-body",
          {"name": token["name"]})
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processStartTag(token)

    def endTagHtml(self,name):
        if self.parser.innerHTML:
            self.parser.parseError("unexpected-end-tag-after-body-innerhtml")
        else:
            self.parser.phase = self.parser.phases["afterAfterBody"]

    def endTagOther(self, token):
        self.parser.parseError("unexpected-end-tag-after-body",
          {"name": token["name"]})
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processEndTag(token)

class InFramesetPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#in-frameset
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("frameset", self.startTagFrameset),
            ("frame", self.startTagFrame),
            ("noframes", self.startTagNoframes)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("frameset", self.endTagFrameset),
            ("noframes", self.endTagNoframes)
        ])
        self.endTagHandler.default = self.endTagOther

    def processEOF(self):
        if self.tree.openElements[-1].name != "html":
            self.parser.parseError("eof-in-frameset")
        else:
            assert self.parser.innerHTML

    def processCharacters(self, token):
        self.parser.parseError("unexpected-char-in-frameset")

    def startTagFrameset(self, token):
        self.tree.insertElement(token)

    def startTagFrame(self, token):
        self.tree.insertElement(token)
        self.tree.openElements.pop()

    def startTagNoframes(self, token):
        self.parser.phases["inBody"].processStartTag(token)

    def startTagOther(self, token):
        self.parser.parseError("unexpected-start-tag-in-frameset",
          {"name": token["name"]})

    def endTagFrameset(self, token):
        if self.tree.openElements[-1].name == "html":
            # innerHTML case
            self.parser.parseError("unexpected-frameset-in-frameset-innerhtml")
        else:
            self.tree.openElements.pop()
        if (not self.parser.innerHTML and
            self.tree.openElements[-1].name != "frameset"):
            # If we're not in innerHTML mode and the the current node is not a
            # "frameset" element (anymore) then switch.
            self.parser.phase = self.parser.phases["afterFrameset"]

    def endTagNoframes(self, token):
        self.parser.phases["inBody"].processEndTag(token)

    def endTagOther(self, token):
        self.parser.parseError("unexpected-end-tag-in-frameset",
          {"name": token["name"]})


class AfterFramesetPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#after3
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("noframes", self.startTagNoframes)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("html", self.endTagHtml)
        ])
        self.endTagHandler.default = self.endTagOther

    def processEOF(self):
        #Stop parsing
        pass

    def processCharacters(self, token):
        self.parser.parseError("unexpected-char-after-frameset")

    def startTagNoframes(self, token):
        self.parser.phases["inHead"].processStartTag(token)

    def startTagOther(self, token):
        self.parser.parseError("unexpected-start-tag-after-frameset",
          {"name": token["name"]})

    def endTagHtml(self, token):
        self.parser.phase = self.parser.phases["afterAfterFrameset"]

    def endTagOther(self, token):
        self.parser.parseError("unexpected-end-tag-after-frameset",
          {"name": token["name"]})


class AfterAfterBodyPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml)
        ])
        self.startTagHandler.default = self.startTagOther

    def processEOF(self):
        pass

    def processComment(self, token):
        self.tree.insertComment(token, self.tree.document)

    def processSpaceCharacters(self, token):
        self.parser.phases["inBody"].processSpaceCharacters(token)

    def processCharacters(self, token):
        self.parser.parseError("expected-eof-but-got-char")
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processCharacters(token)

    def startTagHtml(self, token):
        self.parser.phases["inBody"].processStartTag(token)

    def startTagOther(self, token):
        self.parser.parseError("expected-eof-but-got-start-tag",
          {"name": token["name"]})
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processStartTag(token)

    def processEndTag(self, token):
        self.parser.parseError("expected-eof-but-got-end-tag",
          {"name": token["name"]})
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processEndTag(token)

class AfterAfterFramesetPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("noframes", self.startTagNoFrames)
        ])
        self.startTagHandler.default = self.startTagOther

    def processEOF(self):
        pass

    def processComment(self, token):
        self.tree.insertComment(token, self.tree.document)

    def processSpaceCharacters(self, token):
        self.parser.phases["inBody"].processSpaceCharacters(token)

    def processCharacters(self, token):
        self.parser.parseError("expected-eof-but-got-char")
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processCharacters(token)

    def startTagHtml(self, token):
        self.parser.phases["inBody"].processStartTag(token)

    def startTagNoFrames(self, token):
        self.parser.phases["inHead"].processStartTag(token)

    def startTagOther(self, token):
        self.parser.parseError("expected-eof-but-got-start-tag",
          {"name": token["name"]})
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processStartTag(token)

    def processEndTag(self, token):
        self.parser.parseError("expected-eof-but-got-end-tag",
          {"name": token["name"]})
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processEndTag(token)

def impliedTagToken(name, type="EndTag", attributes = None, 
                    selfClosing = False):
    if attributes is None:
        attributes = {}
    return {"type":tokenTypes[type], "name":name, "data":attributes,
            "selfClosing":selfClosing}

class ParseError(Exception):
    """Error in parsed document"""
    pass
