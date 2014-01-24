import io
import re
import sys
import textwrap
import functools
import tree

class RegexNode(tree.Node):
    def __init__(self, data, *children):
        super().__init__(data, *children)
        data = data.split()
        self.token = data[0]
        self.data = data[1:]
        self.intro = ""
        self.outro = ""
        self.sublist = False
        self.vanishing = False
        self.subordinate = False
        self.coordinate = False
        self.parenthesized = False
        self.desc = None
    
    def __str__(self, depth=0):
        if self.desc is None:
            for node in self:
                node.get_desc()
        if len(self.children) > 1:
            self.add_syntax()
        elif self.sublist:
            self.attempt_collapse()
        bullet = "* " if depth else ""
        self.desc = bullet + self.intro + self.desc
        descs = textwrap.wrap(self.desc, initial_indent="  " * depth,
                                  subsequent_indent="  " * (depth + 2))
        child_descs = [child.__str__(depth+1) for child in self.children]
        return '\n'.join(descs + child_descs) + self.outro
        
    def get_desc(self):
        try:
            dispatch = translation[self.token]
            desc = dispatch(self)
            self.desc = an_regex.sub('an', desc)
        except KeyError:
            self.desc = "something I don't understand: {0}".format(self.token)
    
    def attempt_collapse(self):
        if not self.sublist:
            return True
        elif len(self.children) > 1:
            return False
        elif self.children[0].attempt_collapse():
            self.desc = "" if self.vanishing else self.desc[:-1] + " "
            self.desc += self.children[0].desc
            self.children[0].detach()
            return True
    
    def add_syntax(self):
        nonparen_children = [child for child in self.children
                             if not child.parenthesized]
        if not nonparen_children:
            return
        for child in nonparen_children[:-1]:
            child.outro += ","
        if self.subordinate:
            for child in nonparen_children[1:]:
                target = (child if not child.older_sibling.parenthesized
                          else child.older_sibling)
                target.intro = "followed by "
        elif self.coordinate:
            nonparen_children[-1].intro = "or "
        
    def __repr__(self):
        desc = "{0} node ({1} parent, {2} children)"
        return desc.format([self.token] + self.data,
                           "1" if self._parent is not None else "no",
                           len(self.children))

## Constants

# Regex to set the correct article.
an_regex = re.compile(r'\ba(?= [aeiou]| \"[aefhilmnorsxAEFHILMNORSX]\")')

# Regex to remove quotes.
quotes_regex = re.compile(r'''^r?(["/'])(.*)\1$''')

# Dictionary of special characters that can't be usefully printed.
special_characters = {
    '7': 'the alert character',
    '8': 'a backspace',
    '9': 'a tab character',
    '10': 'a newline',
    '32': 'a space',
    '34': 'a quotation mark',
    '92': 'a backslash',
}

# Dictionary of unusual characters that can be usefully printed with other
# characters, but should be spelled out when by themselves.
unusual_characters = {
    '36': 'a dollar sign',
    '39': 'an apostrophe',
    '40': 'a left parenthesis',
    '41': 'a right parenthesis',
    '44': 'a comma',
    '59': 'a semicolon',
    '60': 'a less than sign',
    '61': 'an equals sign',
    '62': 'a greater than sign',
    '91': 'a left bracket',
    '93': 'a right bracket',
    '95': 'an underscore',
    '123': 'a left curly bracket',
    '124': 'a vertical bar',
    '125': 'a right curly bracket',
}

# Category definitions.
categories = {
    'category_word': "any alphanumeric character or underscore",
    'category_space': "any whitespace character",
    'category_not_space': "any non-whitespace character",
    'category_not_word': "any non-alphanumeric character",
    'category_digit': "any digit",
    'category_not_digit': "any non-digit character",
}

# For the specific situation where you have a set complement that contains
# only a category, we build a dictionary of category complements so that we can
# substitute the complementary category. Ideally we would ask you not to do
# this in your regex, but there you go.
complements = {
    'category_word': 'category_not_word',
    'category_space': 'category_not_space',
    'category_digit': 'category_not_digit',
}

complements.update({v: k for k, v in complements.items()})

# Location definitions.
locations = {
    'at_beginning': 'the beginning of a line',
    'at_end': 'the end of the line',
    'at_boundary': 'a word boundary',
    'at_non_boundary': 'a non-word boundary',
    'at_beginning_string': 'the beginning of the string',
    'at_end_string': 'the end of the string',
}

# Debug setting. If true, print the parse tree.
debug = False

## Functions

# Text-handling functions.
    
def line_and_indent(line):
    '''Dedents a line, returns it with the amount of indentation.'''
    stripped_line = line.lstrip()
    return stripped_line, len(line) - len(stripped_line)


def quoted(string):
    '''Wraps a string in quotes.'''
    return '"' + string + '"'
    
    
def lookup_char(text_ordinal):
    '''Returns the character corresponding to an ordinal.'''
    return chr(int(text_ordinal))


def quoted_chars(*text_ordinals):
    return ''.join(['"'] + [chr(int(ord)) for ord in text_ordinals] + ['"'])


# Functions for getting and formatting the parse tree.

@functools.lru_cache()
def get_debug_tree(regex_string):
    '''Returns the parse tree for a regular expression, as a string.

    Rather than reinvent the wheel, 'parse_regex' just compiles the regex
    you pass it with the debug flag set and temporarily redirects stdout to
    catch the debug info.

    Because the regex compiler has a cache, if you attempt to compile the
    same regular expression repeatedly, you won't get the debug info. To
    avoid this problem, we purge the cache every time, and keep a cache for
    'parse_regex' instead.
    '''
    re.purge()
    catch_debug_info = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = catch_debug_info
    fake_regex = re.compile(regex_string, re.DEBUG)
    sys.stdout = old_stdout
    return catch_debug_info.getvalue()
    

def parse_tree(regex_string):
    '''Yields the parse tree for a regular expression.
    '''
    tree_strings = get_debug_tree(regex_string).splitlines()
    tree = RegexNode('start_tree')
    pointer = tree
    last_indent = 0
    tree_tuples = (line_and_indent(line) for line in tree_strings)
    for line, indent in tree_tuples:
        if indent > last_indent:
            pointer = pointer.children[-1]
        elif indent < last_indent:
            for i in range(0, last_indent - indent, 2):
                pointer = pointer.parent
        pointer += RegexNode(line)
        last_indent = indent
    if debug:
        print('\n'.join(repr(node) for node in tree))
    return tree
    
# Translation functions.

def regex_repeat(node):
    node.sublist = True
    node.subordinate = True
    min, max = int(node.data[0]), int(node.data[1])
    greed = " (non-greedy)" if node.token == "min_repeat" else ""
    if min == max:
        if min == 1:
            leadin = "1 occurrence of:"
        else:
            leadin = "{0} occurrences of:".format(min)    
    elif max > 2 << 15:
        leadin = "{0} or more{1} occurrences of:".format(min, greed)
    elif min == 0:
        if max == 1:
            leadin = "up to 1{0} occurrence of:".format(greed)
        else:
            leadin = "up to {0}{1} occurrences of:".format(max, greed)
    else:
        leadin = "between {0} and {1}{2} occurrences of:".format(min, max,
                                                                 greed)
    return leadin
    

def regex_not_literal(node):
    return "any character except " + get_literals(node)


def regex_literal(node):
    if node.data[0] not in special_characters:
        for sibling in node.younger_siblings():
            if (sibling.token != 'literal' or sibling.data[0] in
                special_characters):
                break
            node.data.extend(sibling.data)
            sibling.detach()
    return get_literals(node)


def get_literals(node):
    if len(node.data) == 1:
        for chardict in (special_characters, unusual_characters):
            if node.data[0] in chardict:
                return chardict[node.data[0]]
        return "the character {0}".format(quoted_chars(*node.data))
    elif node.parent.token == 'in':
        chars = [quoted_chars(literal) for literal in node.data]
        sep = ", " if len(chars) > 2 else " "
        chars[-1] = "or " + chars[-1]
        return "a {0} character".format(sep.join(chars))
    else:
        return "the characters {0}".format(quoted_chars(*node.data))
            
 
def regex_in(node):
    node.sublist = True
    node.vanishing = True
    node.coordinate = True
    if node.children[0].token == 'negate':
        node.children[0].detach()
        leadin = "any character except"
        if node.children[0].token == 'category' and len(node.children) == 1:
            node.children[0].data[0] = complements[node.children[0].data[0]]
    else:
        leadin = "one of the following:"
    return leadin


def regex_category(node):
    try:
        return categories[node.data[0]]
    except KeyError:
        return "an unknown category: {0}".format(node.data[0])


def regex_subpattern(node):
    node.sublist = True
    node.subordinate = True
    pattern_name = node.data[0]
    if pattern_name == 'None':
        if node.children[0].token == 'groupref_exists':
            child = node.children[0]
            node.parent.replace(node, child)
            return regex_groupref_exists(child)
        else:
            subpattern_intro = "a non-captured subgroup consisting of:"
    else:
        subpattern_intro = "subgroup #{0}, consisting of:".format(pattern_name)
    return subpattern_intro


def regex_groupref(node):
   return "subgroup #{0} again".format(node.data[0])

    
def regex_any(node):
    return "any character"


def regex_assert(node):
    node.sublist = True
    node.subordinate = True
    node.parenthesized = True
    positive = node.token == 'assert'
    lookahead = node.data[0] == '1'
    direction = ("we could {0}now match:" if lookahead else
                 "we could {0}have just matched:")
    positivity = "" if positive else "not "
    assertion = "(if " + direction.format(positivity)
    node.outro = ")"
    return assertion


def regex_branch(node):
    node.subordinate = True
    return 'either:' if node.token == 'branch' else 'or:'
    
    
def regex_at(node):
    try:
        return locations[node.data[0]]
    except KeyError:
        return "an unknown location: {0}".format(node.data[0])

    
def regex_groupref_exists(node):
    '''Handle the 'groupref_exists' element (as well as can be expected).

    The 'groupref_exists' element corresponds to the (?(id)pattern) syntax,
    and indicates a match that should be expected only if the given group
    was successfully matched earlier in the pattern. To handle it, we remove
    the start_grouping element, identify the group being referenced, iterate
    through the tree until we reach the end of the subgroup, and then
    produce a collapse of the elements in the conditional match.

    Note that we do not support the (?(id)true-pattern|false-pattern)
    syntax, because the 're' module itself does not correctly support it.
    You can test this using the examples given in the 're' documentation,
    which do not work! The parse tree produced by the compiler forgets to
    include the branch marker between the true and false patterns, so they
    get run together.
    '''
    node.sublist = True
    node.subordinate = True
    condition = "(if group #{0} was found earlier) a subgroup consisting of:"
    return condition.format(node.data[0])


def regex_range(node):
    range_limits = (quoted(lookup_char(val)) for val in node.data)
    range_desc = "a character between {0} and {1}"
    return range_desc.format(*range_limits)
    
    
def start_tree(node):
    node.outro = "."
    node.sublist = True
    node.subordinate = True
    return "This regular expression will match:"

# The translation dictionary. Dispatch table between regex parser elements
# and translation functions.

translation = {
    'max_repeat': regex_repeat,
    'min_repeat': regex_repeat,
    'literal': regex_literal,
    'not_literal': regex_not_literal,
    'in': regex_in,
    'category': regex_category,
    'subpattern': regex_subpattern,
    'groupref': regex_groupref,
    'any': regex_any,
    'assert': regex_assert,
    'assert_not': regex_assert,
    'at': regex_at,
    'branch': regex_branch,
    'or': regex_branch,
    'range': regex_range,
    'groupref_exists': regex_groupref_exists,
    'start_tree': start_tree,
}

# The outward-facing function.

def check_for_quotes(string):
    return quotes_regex.sub('\2', string)


def speak(regex_string=None, clean_quotes=True):
    '''Given a regular expression, prints the translation for that regular
    expression.
    
    clean_quotes: If true, checks if the given regular expression is enclosed
    in quotation marks and removes them before translating it.
    '''
    if regex_string is None:
        regex_string = input("Enter a regular expression:")
    if clean_quotes:
        regex_string = check_for_quotes(regex_string)
    print(parse_tree(regex_string))