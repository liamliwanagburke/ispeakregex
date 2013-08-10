import io
import re
import sys
import textwrap
import functools
from politer import polite, polite_arg

## Constants

# Arbitrary maximum match constant to help identify * operator.
max_match = 2 << 15

# Regex to set the correct article.
an_regex = re.compile(r'\ba(?= [aeiou]| \"[aefhilmnorsxAEFHILMNORSX]\")')

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
    '''Dedents a line, returns it with the amount of indentation.'''
    stripped_line = line.lstrip()
    return stripped_line, len(line) - len(stripped_line)


def is_bulleted(line):
    '''True if the line, minus whitespace, begins with a bullet.'''
    return line.lstrip().startswith("*")
    
    
def is_parenthesized(line):
    '''True if the line starts with or ends with parentheses.'''
    return line.startswith("(") or line.endswith(")")

    
def has_colon(line):
    '''True if the line ends with a colon.'''
    return line.endswith(":")


def is_clause(line):
    '''True if not parenthesized or bulleted.'''
    return not (is_parenthesized(line) or is_bulleted(line))


def quoted(string):
    '''Wraps a string in quotes.'''
    return '"' + string + '"'
    
    
def lookup_char(text_ordinal):
    '''Returns the character corresponding to an ordinal.'''
    return chr(int(text_ordinal))


@polite
@polite_arg('lines')
def split_by_clause(lines):
    for line in lines:
        clause = [line]
        if is_parenthesized(line):
            clause.extend(lines.takeuntil(is_clause))
            if lines:
                clause.append(next(lines))
        else: 
            if lines.any(is_clause):
                clause.extend(lines.takewhile(is_bulleted))
            else:
                clause.extend(lines)
        yield clause


@polite
def conjoin(lines, subord="", coord="", outro=""):
    subord += " " if subord else ""
    coord = coord + " " if coord else subord
    clauses = split_by_clause(lines)
    clause = next(clauses)
    clause[-1] += ',' if clauses else outro
    yield from clause
    for clause in clauses:
        clause[0] = (subord if clauses else coord) + clause[0]
        clause[-1] += ',' if clauses else outro
        yield from clause
       
        
@polite
@polite_arg('lines')
def bullet_list(lines, intro="", outro="", subord="followed by", coord="",
                collapse=True):
    if collapse and not lines.at_least(2):
        intro += " " if intro else ""
        yield intro + lines[0] + outro
    else:
        lines = conjoin(lines, subord, coord, outro)
        if intro:
            yield intro + ":"
        yield from (("  " if is_bulleted(line) else "  * ") + line
                    for line in lines)
    

@polite
def clean(lines):
    wrapper = textwrap.TextWrapper()
    for line in lines:
        line = an_regex.sub('an', line)
        stripped, indent = line_and_indent(line)
        wrapper.initial_indent = " " * indent
        wrapper.subsequent_indent = " " * (indent + 5)
        yield from wrapper.wrap(stripped)

# Functions for getting and formatting the parse tree.

@functools.lru_cache()
def parse_regex(regex_string):
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
    subset = start_grouping(tree)
    min, max = int(lexemes[1]), int(lexemes[2])
    greed = " (non-greedy)" if lexemes[0] == "min_repeat" else ""
    if min == max:
        if min == 1:
            return next(subset)
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
    return bullet_list(subset, leadin)


@polite
def collect_literals(tree):
    for item in tree:
        lexemes = item.split()
        if len(lexemes) < 2 or lexemes[0] != 'literal' or (lexemes[1] in
                                                           special_characters):
            tree.send(item)
            break
        yield lexemes[1]


def regex_not_literal(lexemes, tree, delegate):
    '''Handle 'not_literal' by unpacking the regex optimization.
    
    The 'not_literal' element is produced by a set complement containing
    exactly one character literal (such as '[^a]'). Presumably this is a
    compiler optimization. In order to avoid having two sets of code to handle
    set complements, we manually un-optimize the parse tree and then route the
    translation to the 'regex_in' function.
    '''
    fake_elements = ['end_grouping 0', 'literal ' + lexemes[1],
                     'negate None', 'start_grouping 0']
    tree.send(*fake_elements)
    return regex_in(['in'], tree, delegate)


def regex_literal(lexemes, tree, delegate):
    literals = [lexemes[1]]
    if literals[0] not in special_characters:
        literals.extend(collect_literals(tree))
    if len(literals) == 1:
        for chardict in (special_characters, unusual_characters):
            if literals[0] in chardict:
                return chardict[literals[0]]
        return "the character {0}".format(quoted(lookup_char(literals[0])))
    else:
        chars = (lookup_char(literal) for literal in literals)
        if delegate == 'set':
            quoted_chars = [quoted(char) for char in chars]
            sep = ", " if len(quoted_chars) > 2 else " "
            quoted_chars[-1] = "or " + quoted_chars[-1]
            return "a {0} character".format(sep.join(quoted_chars))
        else:
            chars = quoted(''.join(chars))
            return "the characters {0}".format(chars)


def regex_in(lexemes, tree, delegate):
    set_items = start_grouping(tree, delegate='set')
    if tree[0] == 'negate None':
        next(tree)
        complement = True
    else:
        complement = False
    intro = "any character except " if complement else ""
    if not set_items.at_least(2):
        item = set_items[0]
        if complement and item in categories.values():
            return category_complements[item]
        else:
            return intro + item
    else:
        intro += "one of the following"
        return bullet_list(set_items, intro, subord="", coord="or")
 
 
def regex_category(lexemes, tree, delegate):
    cat_type = lexemes[1]
    no_such_category = "an unknown category: {0}"
    return categories.get(cat_type, no_such_category.format(cat_type))


def regex_subpattern(lexemes, tree, delegate):
    subpattern = start_grouping(tree)
    pattern_name = lexemes[1]
    if pattern_name == 'None':
        if tree[0].startswith('groupref_exists'):
            return next(subpattern)
        else:
            subpattern_intro = "a non-captured subgroup consisting of"
    else:
        subpattern_intro = "subgroup #{0}, consisting of".format(pattern_name)
    return bullet_list(subpattern, subpattern_intro)


def regex_groupref(lexemes, tree, delegate):
   group_name = lexemes[1]
   return "subgroup #{0} again".format(group_name)

    
def regex_any(lexemes, tree, delegate):
    return "any character"


def regex_assert(lexemes, tree, delegate):
    asserted = start_grouping(tree)
    positive = lexemes[0] == 'assert'
    lookahead = lexemes[1] == '1'
    direction = ("we could {0}now match" if lookahead else
                 "we could {0}have just matched")
    positivity = "" if positive else "not "
    assertion = "(if " + direction.format(positivity)
    return bullet_list(asserted, assertion, ending=")")


def regex_branch(lexemes, tree, delegate):
    leadin = 'either' if lexemes[0] == 'branch' else 'or'
    branch = start_grouping(tree)
    return bullet_list(branch, leadin, collapse=False)
    
    
def regex_at(lexemes, tree, delegate):
    location = lexemes[1]
    no_such_location = "an unknown location: {0}".format(location)
    return locations.get(location, no_such_location)

    
def regex_groupref_exists(lexemes, tree, delegate):
    '''Handle the 'groupref_exists' element (as well as can be expected).

    The 'groupref_exists' element corresponds to the (?(id)pattern) syntax,
    and indicates a match that should be expected only if the given group
    was successfully matched earlier in the pattern. To handle it, we remove
    the start_grouping element, identify the group being referenced, iterate
    through the tree until we reach the end of the subgroup, and then
    produce a sublist of the elements in the conditional match.

    Note that we do not support the (?(id)true-pattern|false-pattern)
    syntax, because the 're' module itself does not correctly support it.
    You can test this using the examples given in the 're' documentation,
    which do not work! The parse tree produced by the compiler forgets to
    include the branch marker between the true and false patterns, so they
    get run together.
    '''
    conditional_group = start_grouping(tree)
    group_name = lexemes[1]
    condition = "the subgroup (only if group #{0} was found earlier)"
    return bullet_list(conditional_group, condition.format(group_name))


def regex_range(lexemes, tree, delegate):
    range_regex = r'[0-9]+'
    range_values = (re.findall(range_regex, lexeme) for lexeme in lexemes[1:])
    range_limits = (quoted(lookup_char(val[0])) for val in range_values)
    range_desc = "a character between {0} and {1}"
    return range_desc.format(*range_limits)
    
# Some fake 'translation' functions to help iterate over the flattened tree.

def start_grouping(tree, delegate=None):
    '''Verify that the next element is a 'start_grouping' element and remove
    it.
    
    'start_grouping' is a fake element produced by get_parse_tree when we reach
    the beginning of a subgroup of elements. Elements that expect a subgroup
    use this function to verify that a subgroup is about to start and remove
    the fake element from the list.
    '''
    if next(tree) != 'start_grouping 0':
        raise ValueError
    return translate(tree, delegate)
    
    
def unexpected_start_grouping(lexemes, tree, delegate):
    '''Handle 'start_grouping' by removing the following 'end_grouping'.
    
    'start_grouping' is a fake element produced by get_parse_tree when we reach
    the beginning of a subgroup of elements. Since the command immediately
    before this should have eaten the 'start_grouping' element, hitting this
    means that we have made a mistake somewhere. To help repair the damage,
    iterate into the tree to find and remove the 'end_grouping' element we know
    is there, then restore the other elements.
    '''
    elements = []
    for item in tree:
        if item == 'end_grouping 0':
            break
        else:
            elements.append(item)
    tree.send(*reversed(elements))
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

translation = {
    'max_repeat': regex_repeat,
    'min_repeat': regex_repeat,
    'literal': regex_literal,
    'not_literal': regex_not_literal,
    'in': regex_in,
    'category': regex_category,
    'end_grouping': end_grouping,
    'start_grouping': unexpected_start_grouping,
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
}


@polite
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

# The outward-facing function.

def check_for_quotes(string):
    return re.sub(r'''^r?(["/'])(.*)\1$''', '\2', string)

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
    tree = get_parse_tree(regex_string)
    translation = translate(tree)
    speech_intro = "This regular expression will match"
    translation_list = bullet_list(translation, intro=speech_intro, outro=".")
    output = clean(translation_list)
    try:
        print("\n".join(output))
    except re.error as err:
        sys.stdout = sys.__stdout__
        print("Unfortunately, your regular expression is not valid, because it"
              " contains a " + str(err) + ".")