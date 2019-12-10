import os
import sys

from .math_dollar import split_dollars
from . import __version__

from docutils.nodes import GenericNodeVisitor, Text, math, math_block, FixedTextElement, literal
from docutils.transforms import Transform

from sphinx.util import logging
logger = logging.getLogger(__name__)
logger.info('loading extension %s'%__name__)

NODE_BLACKLIST = node_blacklist = (FixedTextElement, literal, math)

DEBUG = bool(os.environ.get("MATH_DOLLAR_DEBUG", False))

class MathDollarReplacer(GenericNodeVisitor):
    def default_visit(self, node):
        return node

    def visit_Text(self, node):
        parent = node.parent
        while parent:
            if isinstance(parent, node_blacklist):
                if DEBUG and any(i == 'math' for i, _ in split_dollars(str(node).replace('\x00', '\\'))):
                    print("sphinx-math-dollar: Skipping", node, "(node_blacklist = %s)" % (node_blacklist,), file=sys.stderr)
                return
            parent = parent.parent
        # See https://github.com/sympy/sphinx-math-dollar/issues/22
        data = split_dollars(str(node).replace('\x00', '\\'))
        nodes = []
        has_math = False
        for typ, text in data:
            if typ == "math":
                has_math = True
                nodes.append(math(text, Text(text)))
            elif typ == "text":
                nodes.append(Text(text))
            elif typ == "display math":
                has_math = True
                new_node = math_block(text, Text(text))
                new_node.attributes.setdefault('nowrap', False)
                new_node.attributes.setdefault('number', None)
                nodes.append(new_node)
            else:
                raise ValueError("Unrecognized type from split_dollars %r" % typ)
        if has_math:
            node.parent.replace(node, nodes)

class TransformMath(Transform):
    # See http://docutils.sourceforge.net/docs/ref/transforms.html. We want it
    # to apply before things that change rawsource, since we have to use that
    # to get the version of the text with backslashes. I'm not sure which all
    # transforms are relevant here, other than SmartQuotes, so this may need
    # to be adjusted.
    default_priority = 500
    def apply(self, **kwargs):
        self.document.walk(MathDollarReplacer(self.document))

"""
FIXME: rewrite at source-read is too early, there is a risk to embed math in codeblocs
"""
import re
#_linedisplay = re.compile(r"( *)(?:\\[[])([^\n]*?)(?:\\[]])")
#_multilinedisplay = re.compile(r"^( *)(?:\\[[])$((?:^.*$)*?)^(?:\1\\[]])",re.MULTILINE)
redisplay = re.compile(r"(?<! )( *)\\\[(.*?)\1\\\]",re.MULTILINE|re.DOTALL)
shift = '   '
def display_tex(match):
    tab, inner = match.group(1), match.group(2)
    intab = tab + shift
    inner = [l.strip() for l in inner.split('\n')]
    inner = intab + (intab + '\n').join([ l for l in inner if len(l)]) # remove blank lines
    inner = inner.replace('<','\lt ').replace('>','\gt ')
    eq = "\n%s.. math::\n\n%s\n\n"%(tab,inner)
    #logger.info('###\n %s###'%eq)
    return eq

def rewrite_displaymath(app, docname, source):
    source[0] = redisplay.sub(display_tex, source[0])

def config_inited(app, config):
    global node_blacklist, DEBUG
    node_blacklist = config.math_dollar_node_blacklist
    DEBUG = config.math_dollar_debug

def setup(app):
    app.add_transform(TransformMath)
    # We can't force a rebuild here because it will always appear different
    # since the tuple contains classes
    app.add_config_value('math_dollar_node_blacklist', NODE_BLACKLIST, '')
    app.add_config_value('math_dollar_debug', DEBUG, '')
    app.add_config_value('parallel_read_safe', True, '')

    app.connect('config-inited', config_inited)
    app.connect('source-read', rewrite_displaymath)

    return {
        'version': __version__,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
