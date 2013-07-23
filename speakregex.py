import io
import re
import sys
import textwrap
import collections
import itertools
from politer import polite, politer

## Constants

# Arbitrary maximum match constant to help identify * operator.
max_match = 2 << 15

# Regex to set the correct article.
an_regex = r' a(?= [aeiou]| \"[aefhilmnorsxAEFHILMNORSX]\")'

# Dictionary of special characters.
special_characters = {
    '8': 'a word boundary',
    '9': 'a tab character',
    '10': 'a newline',
    '32': 'a space',
    '34': 'a quotation mark',
    '92': 'a backslash',
}

unusual_characters = {
    '59': 'a semicolon',
    '61': 'an equals sign',
}

## Classes

class Countable(collections.Iterator):
    '''A generator wrapper that provides some length-measuring ability.
    
    While generators have memory and style advantages over lists, the inability
    to test their length (since they may be infinite) makes some problems
    messy. The Countable class provides some primitive methods for solving
    length-related problems without pulling the whole generator stream into
    a list.
    '''
    def __init__(self, iterable):
        self.generator = iter(iterable)
    def __next__(self):
        return next(self.generator)
    def all_but_last(self):
        item = next(self.generator)
        while True:
            try:
                next_item = next(self.generator)
            except StopIteration:
                self.last_item = item
                raise
            yield item
            item = next_item
    def at_least(self, length):
        self.generator, measure = itertools.tee(self.generator)
        try:
            for i in range(length):
                next(measure)
        except StopIteration:
            return False
        return True

## Functions

# Text-handling functions.

def line_and_indent(line):
    '''Dedents a line, returns it with the amount of previous indentation.
    '''
    stripped_line = line.lstrip()
    return stripped_line, len(line) - len(stripped_line)


def lookup_char(text_ordinal):
    '''Takes an ordinal, returns a readable representation of that character.
    '''
    return chr(int(text_ordinal))


def quoted_chars(ordinals, concat=False):
    chars = (lookup_char(ord) for ord in ordinals)
    if not concat:
        return ['"{0}"'.format(char) for char in chars]
    else:
        return '"{0}"'.format("".join(chars))

    
def inline_list(items, internal_sep="", ending_sep=""):
    if internal_sep:
        internal_sep += " "
    separator = ", {0}".format(internal_sep)
    if ending_sep:
        items = list(conjoined(items, ending_sep))
    if len(items) < 3:
        return separator.join(items)
    return " ".join(items)


def conjoined(items, conjunction):
    item_list = list(items)
    if len(items) < 3:
        first_item, last_item = item_list[0], item_list[1]
        yield "{0} {1} {2}".format(first_item, conjunction, last_item)
    else:
        last_item = conjunction + " " + item_list.pop()
        yield from item_list
        yield last_item


def is_bulleted(line):
    return line.lstrip().startswith("*")


def collapsible_list(lines, intro_line="", paren=False):
    ending = ")" if paren else ""
    lines = list(lines)
    if len(lines) == 1:
        yield intro_line + " " + lines[0] + ending
    else:
        lines = list(bullet_list(lines, intro_line))
        last_line = lines.pop()
        yield from lines
        yield last_line + ending
    

def bullet_list(lines, intro_line=None):
    if intro_line:
        yield intro_line + ":"
    for line in lines:
        leader = "  " if is_bulleted(line) else " * "
        line = leader + line
        yield line


def clean_up_syntax(lines):
    first_line = next(lines)
    yield first_line
    for line in lines:
        if not is_bulleted(line):
            line = "followed by " + line
        yield line


def punctuate(lines):
    lines = list(lines)
    last_line = lines.pop() + "."
    for line in lines:
        if not line.endswith(":"):
            line = line + ","
        yield line
    yield last_line


def wrapped_list(lines):
    wrapper = textwrap.TextWrapper()
    for line in lines:
        stripped, indent = line_and_indent(line)
        wrapper.initial_indent = " " * indent
        wrapper.subsequent_indent = " " * (indent + 5)
        yield from wrapper.wrap(stripped)

# Functions for getting and formatting the parse tree.

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
    if int(max) >= max_match:
        leadin = "{0} or more{1} occurrences of".format(min, greed)
    elif int(min) == 0:
        if int(max) == 1:
            leadin = "up to {0}{1} occurrence of".format(max, greed)
        else:
            leadin = "up to {0}{1} occurrences of".format(max, greed)
    else:
        leadin = "between {0} and {1}{2} occurrences of".format(min, max,
                                                                 greed)
    subset = clean_up_syntax(translate(tree))
    return collapsible_list(subset, leadin)


def collect_literals(tree):
    for item in tree:
        lexemes = item.split()
        if len(lexemes) < 2 or lexemes[0] != 'literal' or (lexemes[1] in
                                                           special_characters):
            tree.send(item)
            break
        yield lexemes[1]


def literal(lexemes, tree, delegate):
    character = lexemes[1]
    if character in special_characters:
        return special_characters[character]
    literals = [character,] + list(collect_literals(tree))
    if len(literals) == 1:
        if character in unusual_characters:
            return unusual_characters[character]
        return "the character {0}".format(*quoted_chars(literals))
    if delegate == 'set':
        char_list = inline_list(quoted_chars(literals), ending_sep="or")
        return "a {0} character".format(char_list)
    characters = quoted_chars(literals, concat=True)
    return "the characters {0}".format(characters)


def regex_in(lexemes, tree, delegate):
    start_grouping(tree)
    set_items = translate(tree, delegate='set')
    item_descs = list(set_items)
    if len(item_descs) == 1:
        return item_descs[0]
    else:
        conjoined_descs = conjoined(item_descs, "or")
        return bullet_list(conjoined_descs, "one of the following:")

categories = {
    'category_word': "any alphanumeric character or underscore",
    'category_space': "any whitespace character",
    'category_not_word': "any non-alphanumeric character",
    'category_digit': "any digit",
}
    
def category(lexemes, tree, delegate):
    cat_type = lexemes[1]
    no_such_category = "an unknown category: {0}".format(cat_type)
    return categories.get(cat_type, no_such_category)


def subpattern(lexemes, tree, delegate):
    start_grouping(tree)
    pattern_name = lexemes[1]
    if pattern_name == 'None':
        subpattern_intro = "a non-captured subgroup consisting of"
    else:
        subpattern_intro = "subgroup #{0}, consisting of".format(pattern_name)
    subpattern = translate(tree)
    return collapsible_list(subpattern, subpattern_intro)


def groupref(lexemes, tree, delegate):
   pattern_name = lexemes[1]
   return "subgroup #{0} again".format(pattern_name)

    
def regex_any(lexemes, tree, delegate):
    return "any character"


def regex_assert(lexemes, tree, delegate):
    pass

    
def assert_not(lexemes, tree, delegate):
    start_grouping(tree)
    negated_pattern = list(clean_up_syntax(translate(tree)))
    attached_element = next(translate(tree))
    negation = "{0} (unless preceded by".format(attached_element)
    return collapsible_list(negated_pattern, negation, paren=True)


locations = {
    'at_beginning': 'the beginning of a line',
    'at_end': 'the end of the line',
}

    
def regex_at(lexemes, tree, delegate):
    location = lexemes[1]
    return locations[location]

    
def regex_range(lexemes, tree, delegate):
    range_regex = r'[0-9]+'
    range_values = (re.findall(range_regex, lexeme) for lexeme in lexemes[1:])
    range_limits = quoted_chars(val[0] for val in range_values)
    range_desc = "a character between {0} and {1}"
    return range_desc.format(*range_limits)
    
# Some fake 'translation' functions to help iterate over the flattened tree.

def start_grouping(tree):
    '''Verify that the next element is a 'start_grouping' element and remove
    it.
    
    'start_grouping' is a fake element produced by get_parse_tree when we reach
    the beginning of a subgroup of elements. Elements that expect a subgroup
    use this function to verify that a subgroup is about to start and remove
    the fake element from the list.
    '''
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
    elements = list(itertools.takewhile(grouped, tree))
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
    
def grouped(line): return line != 'end_grouping 0'
    
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
    'any': regex_any,
    'assert_not': assert_not,
    'at': regex_at,
    'range': regex_range,
}


def translate(tree, delegate=None):
    for item in tree:
        lexemes = item.split()
        try:
            dispatch = translation[lexemes[0]]
        except KeyError:
            yield "something I don't understand: {0}".format(item)
        else:
            result = dispatch(lexemes, tree, delegate)
            if isinstance(result, str):
                yield result
            else:
                yield from result

# The actual function!          

def speak(regex_string=None):
    if regex_string is None:
        regex_string = input("Enter a regular expression (unquoted, please):")
    speech_intro = "This regular expression will match"
    tree = get_parse_tree(regex_string)
    translation = translate(tree)
    syntax_pass = clean_up_syntax(translation)
    punctuation_pass = punctuate(syntax_pass)
    bulleted_translation = collapsible_list(punctuation_pass, speech_intro)
    final_translation = wrapped_list(bulleted_translation)
    print("\n".join(final_translation))