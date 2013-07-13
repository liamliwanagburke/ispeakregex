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
        yield from politer(func(*args, **kwargs))
    return wrapped