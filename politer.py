'''Provides a 'polite' iterator object which can be sent back values and which
allows sequence operations to be performed on it.

exported:
    Politer -- the eponymous generator/sequence class
    @polite -- decorator that makes a generator function return a Politer
'''

import functools
import itertools
import collections

def politer(iterable):
    '''Wraps an iterable in a Politer if it is not already wrapped.'''
    if isinstance(iterable, Politer):
        return iterable
    return Politer(iterable)

def polite(func):
    '''Decorator function that wraps a generator function and makes it
    return a Politer object.
    '''
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        return politer(func(*args, **kwargs))
    return wrapped
    
class Politer(collections.Iterator, collections.Sequence):
    '''
    A 'polite' iterator object which provides many useful methods.

    While generators often provide a cleaner approach to problems, their
    indeterminate and temporal nature make some problems -- such as those
    that require looking ahead or knowing the length of a sequence -- more
    difficult. Politer is an attempt to provide methods for solving those
    problems, in two ways:

    1) It allows you to send values back to the generator, which will put
    them on top of the 'stack'. As a convenience, it provides a prev()
    method for the common use case of rewinding the generator exactly one
    value.

    2) It provides a 'lazy' implementation of the sequence protocol,
    allowing you to get the politer's length, index into it, etc. just like
    a list. The politer will internally unroll as much of the generator as
    necessary in order to perform the requested operation. It also provides
    some 'lazy' methods to avoid using the more exhaustive ones, such as
    at_least() and popped().

    Note that pulling values off the politer using next() will change its
    length and the indices of the contained elements -- the politer is a
    'list of uniterated values,' albeit with the ability to send values
    back.

    Politers use deques internally to hold their unrolled values. They
    should perform well for relatively short-range looks ahead during
    iteration, but if you intend to perform many sequence operations that
    target the 'far end' of the generator, you will probably do better just
    casting the generator to a list.
    '''
    
    __slots__ = ['_generator', '_values', '_previous']
    
    def __init__(self, iterable):
        '''Instantiates a Politer. 'iterable' is the object to wrap.'''
        self._generator = iter(iterable)
        self._values = collections.deque()
        self._previous = None
    
    def __next__(self):
        '''Gets the next value from the politer.'''
        if self._values:
            value = self._values.popleft()
        else:
            value = next(self._generator)
        self._previous = value
        return value
        
    def send(self, *values):
        '''Puts values 'on top' of the politer, last-in-first-out.'''
        self._values.extendleft(values)      
        
    def prev(self):
        '''Rewinds the generator exactly one value. Not repeatable.'''
        if self._previous is None:
            raise StopIteration('politer.prev() is not repeatable')
        self._values.appendleft(self._previous)
        self._previous = None
    
    def at_least(self, length):
        '''Lazily evaluates len(self) >= length.'''
        return self._advance_until(lambda: len(self._values) >= length)
        
    def __len__(self):
        '''Gets the length of the politer, dumping the generator to do so.'''
        self._dump()
        return len(self._values)
    
    def __getitem__(self, index):
        '''Gets the value at a specific index, or gets a slice.
        
        Since deques can't be sliced, if a slice is requested we cast the
        internal deque to a list and slice that, with the attendant
        costs.'''
        if isinstance(index, slice):
            return self._getslice(index)
        elif isinstance(index, int):
            if not self._advance_until(lambda: len(self._values) > index):
                raise IndexError("politer index out of range")
            return self._values[index]
        else:
            raise TypeError("politer indices must be integers")
            
    def __contains__(self, value):
        '''Lazily tests membership.'''
        return self._advance_until(lambda: value in self._values)    
        
    def count(self, value):
        '''Counts the occurrences of value in the politer.
        
        Dumps the generator.
        '''
        self._dump()
        return self._values.count(value)
        
    def index(self, value, i=0, j=None):
        '''Finds the first occurrence of value in the politer.
        
        Always dumps the generator. (Doesn't technically have to, but
        doing it the right way was very complicated.)
        '''
        self._dump()
        if j is None:
            j = len(self._values)
        return self._values.index(value, i, j)
        
    def close(self):
        '''Closes the generator and discards all values.'''
        self._generator.close()
        del self._values
        self._values = collections.deque()
        
    def pop(self):
        '''Dumps the generator, then removes and returns the last item.'''
        self._dump()
        return self._values.pop()
        
    def popped(self, n=1):
        '''Yields every item in the politer except the last n.'''
        yield from self.takewhile(lambda _: self.at_least(n))
        
    def __nonzero__(self):
        '''Returns True if there are any remaining values.'''
        return self._advance_until(lambda: self._values)
        
    def takewhile(self, func):
        '''As itertools, but preserves the failing element.'''
        saved = None
        for item in itertools.takewhile(func, self):
            yield item
            saved = item
        self.prev()
        if saved is not None:
            self._previous = saved
    
    def takeuntil(self, func):
        '''Opposite of takewhile.'''
        yield from self.takewhile(lambda x: not func(x))
        
    def _getslice(self, sliceobj):
        start = sliceobj.start if sliceobj.start is not None else 0
        stop = sliceobj.stop if sliceobj.stop is not None else -1 # force dump
        if start < 0 or stop < 0:                 
            self._dump()                           
        else:
            self._advance_until(lambda: len(self._values) >= stop)
        return list(self._values)[sliceobj]
        
    def _advance(self):
        try:
            self._values.append(next(self._generator))
            return True
        except StopIteration:
            return False
        
    def _advance_until(self, func):
        while not func():
            if not self._advance():
                return False
        return True
            
    def _dump(self):
        self._values.extend(self._generator)