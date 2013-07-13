"""Provides "polite" iterators that can receive and return values.

Politer provides an iterator over an object that is "polite" - if you pass it
any number of values, it will accept them and place them on top of the iterator
stack, returning them before continuing to iterate.

When iterating over streams or generators, one common use case is to accept and
act on values until they fail to meet a certain condition. For example, given
two large sorted files, you might want to print all lines that appear in both
files. Since the files are very large, you would like to avoid reading them
into memory. Since they are sorted, the simplest way is to take a line from one
file and iterate through the next file until you find a line that would come
after it:

def broken_match_lines(file1, file2):
	for line1 in file1:
		for line2 in file2:
			if line2 > line1:
				break
			elif line2 == line1:
				print(line1)

However, this code is faulty, because the value that fails the condition
is lost.

file1 = ["0", "1", "2 -- this line fails to match", "4"]
file2 = ["0", "2 -- this line fails to match"]
print(broken_match_lines(file1, file2))

(Note that itertools.takewhile has this problem.)

One solution is to save the most recent value and add it manually to the
iteration. However, this is confusing to implement and to read:

def messy_match_lines(file1, file2):
	last_line = ""
	for line1 in file1:
		if last_line > line1:
			break
		elif last_line == line1:
			print(line1)
		else:
			for line2 in file2:
				if line2 > line1:
					last_line = line2
					break
				elif line2 == line1:
					print(line1)

def also_messy_match_lines(file1, file2):
	last_line = ""
	for line1 in file1:
		for line2 in itertools.chain([last_line], file2):
			if line2 > line1:
				last_line = line2
				break
			elif line2 == line1:
				print(line1)

In some cases, such as when multiple functions are iterating over the same
stream, it may be extremely complex or impossible to use this strategy.

Ideally, you would simply tell the iterator to take the line back, and it would
"politely" do so, putting it back on top of the iterator 'stack' and yielding
it again to the next request. This module provides a generator function that
wraps an iterator and gives it this capability, making it a polite iterator, or
"politer":

def polite_match_lines(file1, file2):
	politefile = politer(file2)
	for line1 in file1:
		for line2 in politefile:
			if line2 > line1:
				politefile.send(line2)
				break
			elif line2 == line1:
				print(line1)

The generator object returned by politer() can be passed seamlessly between
functions just as if it were the original stream, even if you are putting
values back or even putting new values on top of the stack. No special
state-maintenance code is required.

Functions exported:
	politer(iterable): takes an iterable, returns a "polite" one
	@polite: decorator function that makes a generator function "polite"
"""

from functools import wraps

def politer(iterable):
    '''Passed an iterable object, returns a 'polite' iterator, which stores
    values you send to it and puts them on 'top' of the iterator, returning
    them first before continuing.
    '''
    iterable = iter(iterable)
    values = []
    while True:
        if values:
            value = (yield values.pop())
        else:
            value = (yield next(iterable))
        while value is not None:
            values.append(value)
            value = (yield None)

def polite(func):
    '''Decorator function that wraps a generator function and makes it
    'polite,' so that it can take values you send to it and put them on 'top'
    of its stack of values, returning them first before continuing.
    '''
    @wraps(func)
    def wrapped(*args, **kwargs):
        return politer(func(*args, **kwargs))
    return wrapped