import io
import re
import sys
from politer import politer

# Functions for getting and formatting the parse tree for a regular expression.

def line_and_indent(line):
    '''Takes a line beginning with whitespace, returns the stripped line and
    the length of the whitespace.
    '''
    stripped_line = line.lstrip()
    return stripped_line, len(line) - len(stripped_line)

def get_parse_tree(regex_string, debug=True):
    '''Takes a regular expression string and returns the parse tree generated
    by the compiler when compiling it, as a string.
    
    Rather than reinvent the wheel, get_parse_tree just compiles the regex you
    pass it with the debug flag set and temporarily redirects stdout to catch
    the debug info.
    '''
    re.purge()
    catch_tree = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = catch_tree
    fake_regex = re.compile(regex_string, re.DEBUG)
    sys.stdout = old_stdout
    if debug:
        print(catch_tree.getvalue())
    return catch_tree.getvalue()

def tree_to_list(tree):
    '''Takes a tree of items formatted as an indented list of strings and
    returns it formatted as a nested list.
    
    The argument to tree_to_list must be a politer (as defined in the politer
    module) over a list of strings.
    '''
    item = next(tree)
    clean_item, start_indent = line_and_indent(item)
    branch = [clean_item]
    for item in tree:
        clean_item, indent = line_and_indent(item)
        if indent == start_indent:
            branch.append(clean_item)
        elif indent > start_indent:
            tree.send(item)
            branch.append(tree_to_list(tree))
        else:
            tree.send(item)
            break
    return branch

def parse_regex(regex_string):
    '''Takes a regular expression and returns the parse tree as a nested list.
    '''
    split_string = get_parse_tree(regex_string).splitlines()
    tree = politer(split_string)
    return tree_to_list(tree)

# Translation functions.
# TODO: get rid of kwarg passthrough, replace with a single keyword system.
# delegate?
    
def repeating(lexemes, tree, **kwargs):
    min, max = lexemes[1], lexemes[2]
    branch = politer(next(tree))
    branch_descs = (translate(item, branch) for item in branch)
    leadin = "between {0} and {1}:\n  ".format(min, max)
    return leadin + "\n  ".join(branch_descs)
    
def collect_literals(lexemes, tree, **kwargs):
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
    
def one_character(lexemes, tree, terse=False, **kwargs):
    char = chr(int(lexemes[1]))
    if char == '\n':
        char = "a new line"
    if terse:
        return "'{0}'".format(char)
    return "the character '{0}'".format(char)

def explicit_set(lexemes, tree, **kwargs):
    items = politer(next(tree))
    item_descs = (translate(item, items, terse=True) for item in items)
    return "One of the following: " + ",".join(item_descs)

categories = {
    'category_word': "an alphanumeric character or underscore",
    'category_space': "any whitespace character",
    'category_not_word': "any non-alphanumeric character",
}
    
def category(lexemes, tree, **kwargs):
    cat_type = lexemes[1]
    no_such_category = "an unknown category: {0}".format(cat_type)
    return categories.get(cat_type, no_such_category)
    
# The translation dictionary. Dispatch table between regex parser elements
# and translation functions.
    
translation = {
    'max_repeat': repeating,
    'literal': collect_literals,
    'in': explicit_set,
    'category': category,
}

def translate(word, tree, **kwargs):
    try:
        lexemes = word.split()
    except AttributeError:
        for item in reversed(word):
            tree.send(item)
        return "and some other stuff:"
    try:
        dispatch = translation[lexemes[0]]
    except KeyError:
        return "something I don't understand: {0}".format(word)
    return dispatch(lexemes, tree, **kwargs)

# The actual function!

def speak(regex_string):
    tree = politer(parse_regex(regex_string))
    output = ["This regex matches:"] + [translate(item, tree) for item in tree]
    make_speech(output)
    
def make_speech(chunks):
    print("\n".join(chunks))
