import io
import re
import sys
from politer import polite

# Functions for getting and formatting the parse tree for a regular expression.

def line_and_indent(line):
    '''Takes a line beginning with whitespace, returns the stripped line and
    the length of the whitespace.
    '''
    stripped_line = line.lstrip()
    return stripped_line, len(line) - len(stripped_line)

def parse_regex(regex_string, debug=True):
    '''Takes a regular expression string and returns the parse tree generated
    by the compiler when compiling it, as a string.
    
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
    '''Takes a regular expression and generates the elements in the parse tree.
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
    
def repeating(lexemes, tree, delegate):
    if next(tree) != 'start_grouping 0':
        raise ValueError
    min, max = lexemes[1], lexemes[2]
    leadin = "between {0} and {1}:\n  ".format(min, max)
    subset = translate(tree)
    return leadin + "\n  ".join(subset)
    
def collect_literals(lexemes, tree, delegate):
    literals = [lexemes[1]]
    for item in tree:
        next_command, next_character = item.split()
        if next_command != 'literal':
            tree.send(item)
            break
        literals.append(next_character)
    characters = [chr(int(literal)) for literal in literals]
    if len(characters) == 1:
        return "the character '{0}'".format(characters[0])
    return "the characters '{0}'".format("".join(characters))

def explicit_set(lexemes, tree, delegate):
    if next(tree) != 'start_grouping 0':
        raise ValueError
    item_descs = translate(tree, delegate='set')
    return "One of the following: " + ",".join(item_descs)

categories = {
    'category_word': "an alphanumeric character or underscore",
    'category_space': "any whitespace character",
    'category_not_word': "any non-alphanumeric character",
}
    
def category(lexemes, tree, delegate):
    cat_type = lexemes[1]
    no_such_category = "an unknown category: {0}".format(cat_type)
    return categories.get(cat_type, no_such_category)

# Some fake 'translation' functions to help iterate over the flattened tree.
    
def clean_up_stack(lexemes, tree, delegate):
    '''Handle 'start_grouping' by removing the following 'end_grouping'.
    
    'start_grouping' is a fake element produced by get_parse_tree when we reach
    the beginning of a subgroup of elements. Since the command immediately
    before this should have eaten the 'start_grouping' element, hitting this
    means that we have made a mistake somewhere. To help repair the damage,
    iterate into the tree to find and remove the 'end_grouping' element we know
    is there, then restore the other elements.
    '''
    elements = [element for element in tree]
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
    'max_repeat': repeating,
    'literal': collect_literals,
    'in': explicit_set,
    'category': category,
    'end_grouping': end_grouping,
    'start_grouping': clean_up_stack,
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

def speak(regex_string):
    tree = get_parse_tree(regex_string)
    translation = ["This regular expression will match: "]
    translation.extend(translate(tree))
    make_speech(translation)
    
def make_speech(chunks):
    print("\n".join(chunks))
