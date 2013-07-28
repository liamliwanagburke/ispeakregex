import io
import re
import sys
import textwrap
import itertools
from politer import polite

## Constants

# Arbitrary maximum match constant to help identify * operator.
max_match = 2 << 15

# Regex to set the correct article.
an_regex = r'\ba(?= [aeiou]| \"[aefhilmnorsxAEFHILMNORSX]\")'

# Regex to remove quotes from input.
quotes_regex = r'''^r?(["/'])(.*)\1$'''

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
    '95': 'an underscore',
    '124': 'a vertical bar',
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
opposed_categories = {
    'category_word': 'category_not_word',
    'category_space': 'category_not_space',
    'category_digit': 'category_not_digit',
}

category_complements = {categories[k]: categories[v] for k, v in
                     opposed_categories.items()}
category_complements.update({v: k for k, v in category_complements.items()})

# Location definitions.
locations = {
    'at_beginning': 'the beginning of a line',
    'at_end': 'the end of the line',
    'at_boundary': 'the beginning or end of a word',
    'at_non_boundary': '(if not at the beginning or end of a word)',
    'at_beginning_string': 'the beginning of the string',
    'at_end_string': 'the end of the string',
}

# Debug setting. If true, print the parse tree as we parse it.
debug = False

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
    if len(items) > 2:
        return separator.join(items)
    return " ".join(items)


def conjoined(items, conjunction):
    item_list = list(items)
    if len(item_list) < 3:
        first_item, last_item = item_list[0], item_list[1]
        yield "{0} {1} {2}".format(first_item, conjunction, last_item)
    else:
        last_item = conjunction + " " + item_list.pop()
        yield from item_list
        yield last_item


def is_bulleted(line):
    return line.lstrip().startswith("*")


def collapsible_list(lines, intro_line="", ending=""):
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
    last_line = next(lines)
    yield last_line
    for line in lines:
        if not (is_bulleted(line) or line.startswith("(") or
                last_line.endswith(")") or line == "or:"):
            line = "followed by " + line
        yield line
        last_line = line


def punctuate(lines):
    lines = list(lines)
    last_line = lines.pop() + "."
    for line in lines:
        if not line.endswith((":", ")")):
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
        

def check_for_quotes(string):
    return re.sub(quotes_regex, '\2', string)

# Functions for getting and formatting the parse tree.

def parse_regex(regex_string):
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
            if debug: print("end group")
            yield "end_grouping 0"
            last_indent -= 2
        while indent > last_indent:
            if debug: print("start group")
            yield "start_grouping 0"
            last_indent += 2
        if debug: print(item)
        yield item
    
# Translation functions.
    
def regex_repeat(lexemes, tree, delegate):
    start_grouping(tree)
    min, max = int(lexemes[1]), int(lexemes[2])
    greed = " (non-greedy)" if lexemes[0] == "min_repeat" else ""
    if min == max:
        if min == 1:
            return next(translate(tree))
        else:
            leadin = "{0} occurrences of".format(min)    
    elif max >= max_match:
        leadin = "{0} or more{1} occurrences of".format(min, greed)
    elif min == 0:
        if max == 1:
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


def not_literal(lexemes, tree, delegate):
    char_literal = lexemes[1]
    if char_literal in special_characters:
        character = special_characters[char_literal]
    elif char_literal in unusual_characters:
        character = unusual_characters[char_literal]
    else:
        tiny_list = [char_literal,]
        character = quoted_chars(tiny_list)[0]
    return "any character except {0}".format(character)


def literal(lexemes, tree, delegate):
    character = lexemes[1]
    if character in special_characters:
        return special_characters[character]
    literals = [character,] + list(collect_literals(tree))
    if len(literals) == 1:
        if character in unusual_characters:
            return unusual_characters[character]
        return "the character {0}".format(*quoted_chars(literals))
    elif delegate == 'set':
        char_list = inline_list(quoted_chars(literals), ending_sep="or")
        return "a {0} character".format(char_list)
    else:
        characters = quoted_chars(literals, concat=True)
        return "the characters {0}".format(characters)


def regex_in(lexemes, tree, delegate):
    start_grouping(tree)
    modifier = next(tree)
    if modifier == 'negate None':
        intro = "any character except "
    else:
        intro = ""
        tree.send(modifier)
    set_items = list(translate(tree, delegate='set'))
    if len(set_items) == 1:
        item = set_items[0]
        if modifier == 'negate None' and item in categories.values():
            return category_complements[item]
        else:
            return intro + item
    else:
        conjoined_descs = conjoined(set_items, "or")
        return bullet_list(conjoined_descs, intro + "one of the following")
 
 
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
    subpattern = clean_up_syntax(translate(tree))
    return collapsible_list(subpattern, subpattern_intro)


def groupref(lexemes, tree, delegate):
   pattern_name = lexemes[1]
   return "subgroup #{0} again".format(pattern_name)

    
def regex_any(lexemes, tree, delegate):
    return "any character"


def regex_assert(lexemes, tree, delegate):
    start_grouping(tree)
    positive = lexemes[0] == 'assert'
    lookahead = lexemes[1] == '1'
    direction = ("we could {0}now match" if lookahead else
                 "we could {0}have just matched")
    positivity = "" if positive else "not "
    assertion = "(if " + direction.format(positivity)
    asserted = clean_up_syntax(translate(tree))
    return collapsible_list(asserted, assertion, ending=")")


def regex_branch(lexemes, tree, delegate):
    start_grouping(tree)
    branch = translate(tree)
    branches = []
    first_branch = list(bullet_list(clean_up_syntax(branch), "either"))
    branches.append(first_branch)
    for item in tree:
        if item != "or":
            tree.send(item)
            break
        start_grouping(tree)
        branch = translate(tree)
        new_branch = list(bullet_list(clean_up_syntax(branch), "or"))
        branches.append(new_branch[:])
    return itertools.chain(*branches)

    
def regex_at(lexemes, tree, delegate):
    location = lexemes[1]
    no_such_location = "an unknown location: {0}".format(location)
    return locations.get(location, no_such_location)

    
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
    
    
def unexpected_start_grouping(lexemes, tree, delegate):
    '''Handle 'start_grouping' by removing the following 'end_grouping'.
    
    'start_grouping' is a fake element produced by get_parse_tree when we reach
    the beginning of a subgroup of elements. Since the command immediately
    before this should have eaten the 'start_grouping' element, hitting this
    means that we have made a mistake somewhere. To help repair the damage,
    iterate into the tree to find and remove the 'end_grouping' element we know
    is there, then restore the other elements.
    '''
    elements = list(itertools.takewhile(lambda line: line != 'end_grouping 0',
                                        tree))
    for element in reversed(elements):
        tree.send(element)
    return "(warning, some elements may not appear correctly grouped)"

    
def end_grouping(lexemes, tree, delegate):
    '''Handle 'end_grouping' by raising a StopIteration exception.
    
    'end_grouping' is a fake element produced by get_parse_tree when we reach
    the end of a subgroup of elements. Raise a fake StopIteration to shut down
    the subgroup translator.
    '''
    raise StopIteration
    
# The translation dictionary. Dispatch table between regex parser elements
# and translation functions.
# Because this dictionary contains all the regex functions, it has to come
# after them, even though it's a constant. Sorry!
    
translation = {
    'max_repeat': regex_repeat,
    'min_repeat': regex_repeat,
    'literal': literal,
    'not_literal': not_literal,
    'in': regex_in,
    'category': category,
    'end_grouping': end_grouping,
    'start_grouping': unexpected_start_grouping,
    'subpattern': subpattern,
    'groupref': groupref,
    'any': regex_any,
    'assert': regex_assert,
    'assert_not': regex_assert,
    'at': regex_at,
    'branch': regex_branch,
    'range': regex_range,
}

def translate(tree, delegate=None):
    '''Given a parse tree, yields the translation for each element.
    
    'translate' looks each element up in the translation dictionary and calls
    the associated function to generate the appropriate translation. It expects
    either a string or a iterable containing strings in return. 'translate' is
    also used by some of the functions to translate the subgroups associated
    with their elements.
    
    delegate: The function calling translate, which is passed to the functions
    it calls. Used when output should be in a different format for a particular
    type of subgroup.
    '''
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

# The functions that do the actual work!

def speak(regex_string=None, clean_quotes=True):
    '''Given a regular expression, prints the translation for that regular
    expression.
    
    'speak' gets the parse tree for the regular expression, produces the list
    of elements, runs it through a bunch of text-formatting functions, and
    prints it out.
    
    clean_quotes: If true, checks if the given regular expression is enclosed
    in quotation marks and removes them before translating it.
    '''
    if regex_string is None:
        regex_string = input("Enter a regular expression:")
    if clean_quotes:
        regex_string = check_for_quotes(regex_string)
    tree = get_parse_tree(regex_string)
    translation = translate(tree)
    syntax_pass = clean_up_syntax(translation)
    punctuation_pass = punctuate(syntax_pass)
    speech_intro = "This regular expression will match"
    bulleted_translation = collapsible_list(punctuation_pass, speech_intro)
    final_translation = wrapped_list(bulleted_translation)
    try:
        print("\n".join(final_translation))
    except re.error as err:
        sys.stdout = sys.__stdout__
        print("Unfortunately, your regular expression is not valid, because it"
              " contains a " + str(err) + ".")