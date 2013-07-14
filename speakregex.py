import io
import re
import sys
import textwrap
import itertools
from politer import polite

# Functions for getting and formatting the parse tree for a regular expression.

def line_and_indent(line):
    '''Dedents a line, returns it with the amount of previous indentation.
    '''
    stripped_line = line.lstrip()
    return stripped_line, len(line) - len(stripped_line)

def parse_regex(regex_string, debug=True):
    '''Returns the parse tree for a regular expression, as a string.
    
    Rather than reinvent the wheel, get_parse_tree just compiles the regex you
    pass it with the debug flag set and temporarily redirects stdout to catch
    the debug info.
    '''
    re.purge()
    catch_debug_info = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = catch_debug_info
    fake_regex = re.compile(regex_string, re.DEBUG)
    sys.stdout = old_stdout
    if debug:
        print(catch_debug_info.getvalue())
    return catch_debug_info.getvalue()

@polite
def get_parse_tree(regex_string):
    '''Yields the parse tree for a regular expression, element by element.
    
    Indicates the beginning and end of a group of indented lines by generating
    fake 'start_grouping' and 'end_grouping' elements.
    '''
    last_indent = 0
    indented_tree = parse_regex(regex_string)
    stripped_tree = (line_and_indent(line) for line in
                     indented_tree.splitlines())
    for item, indent in stripped_tree:
        while indent < last_indent:
            yield "end_grouping 0"
            last_indent -= 2
        while indent > last_indent:
            yield "start_grouping 0"
            last_indent += 2
        yield item
    
# Translation functions.
    
def repeat(lexemes, tree, delegate):
    start_grouping(tree)
    min, max = lexemes[1], lexemes[2]
    greed = " (non-greedy)" if lexemes[0] == "min_repeat" else ""
    leadin = "between {0} and {1}{2} occurrences of ".format(min, max, greed)
    subset = translate(tree)
    return leadin + "\n  ".join(subset)
    
def literal(lexemes, tree, delegate):
    literals = [lexemes[1]]
    for item in tree:
        more_lexemes = item.split()
        next_command, next_character = more_lexemes[0], more_lexemes[1]
        if next_command != 'literal':
            tree.send(item)
            break
        literals.append(next_character)
    characters = [chr(int(literal)) for literal in literals]
    if delegate == 'set':
        last_character = characters.pop()
        character_list = "', '".join(characters)
        return "a '{0}' or '{1}' character".format(character_list,
                                                   last_character)
    if len(characters) == 1:
        return "the character '{0}'".format(characters[0])
    return "the characters '{0}'".format("".join(characters))

def regex_in(lexemes, tree, delegate):
    start_grouping(tree)
    item_descs = list(translate(tree, delegate='set'))
    if len(item_descs) == 1:
        return item_descs[0]
    else:
        return "one of the following: " + ", ".join(item_descs)

categories = {
    'category_word': "any alphanumeric character or underscore",
    'category_space': "any whitespace character",
    'category_not_word': "any non-alphanumeric character",
}
    
def category(lexemes, tree, delegate):
    cat_type = lexemes[1]
    no_such_category = "an unknown category: {0}".format(cat_type)
    return categories.get(cat_type, no_such_category)

def subpattern(lexemes, tree, delegate):
    start_grouping(tree)
    pattern_name = lexemes[1]
    subpattern = speechify(translate(tree))
    if pattern_name == 'None':
        subpattern_template = "a non-captured subpattern ({0})"
    else:
        subpattern_template = "subpattern {1} ({0})"
    return subpattern_template.format(subpattern, pattern_name)
    
def groupref(lexemes, tree, delegate):
   pattern_name = lexemes[1]
   return "subpattern {0} again".format(pattern_name)
    
# Some fake 'translation' functions to help iterate over the flattened tree.

def start_grouping(tree):
    if next(tree) != 'start_grouping 0':
        raise ValueError
    return True
    
def unexpected_start_grouping(lexemes, tree, delegate):
    '''Handle 'start_grouping' by removing the following 'end_grouping'.
    
    'start_grouping' is a fake element produced by get_parse_tree when we reach
    the beginning of a subgroup of elements. Since the command immediately
    before this should have eaten the 'start_grouping' element, hitting this
    means that we have made a mistake somewhere. To help repair the damage,
    iterate into the tree to find and remove the 'end_grouping' element we know
    is there, then restore the other elements.
    '''
    elements = list(itertools.takewhile(lambda x: x != 'end_grouping 0', tree))
    for element in reversed(elements):
        tree.send(element)
    return "(warning, some elements may not appear correctly grouped)"
    
def end_grouping(lexemes, tree, delegate):
    '''Handle 'end_grouping' by raising a StopIteration exception.
    
    'end_grouping' is a fake element produced by get_parse_tree when we reach
    the end of a subgroup of elements. Raise a fake StopIteration to tell the
    subgroup iterator that its job is done.
    '''    
    raise StopIteration
    
# The translation dictionary. Dispatch table between regex parser elements
# and translation functions.
    
translation = {
    'max_repeat': repeat,
    'min_repeat': repeat,
    'literal': literal,
    'in': regex_in,
    'category': category,
    'end_grouping': end_grouping,
    'start_grouping': unexpected_start_grouping,
    'subpattern': subpattern,
    'groupref': groupref,
}

def translate(tree, delegate=None):
    for item in tree:
        lexemes = item.split()
        try:
            dispatch = translation[lexemes[0]]
        except KeyError:
            yield "something I don't understand: {0}".format(item)
        else:
            yield dispatch(lexemes, tree, delegate)
    
# The actual function!

def speechify(translation):
    return ", followed by ".join(translation)

def speak(regex_string):
    tree = get_parse_tree(regex_string)
    translation = translate(tree)
    speech_template = "This regular expression will match {0}."
    speech = speech_template.format(speechify(translation))
    print(textwrap.fill(speech))