class Node(object):
    '''A simple implementation of a tree node.
    '''
    __slots__ = ('_parent', 'children', 'data')
    
    def __init__(self, data=None, children=()):
        '''Instantiates a tree Node.

        data: The data contained by this node.
        children: An iterable of nodes to add as children to this node.
        '''
        self._parent = None
        self.data = data
        self.children = []
        for child in children:
            self.add(child)
            
    @property
    def parent(self):
        '''The node's parent node, or None. Setting this moves the node.'''
        return self._parent
        
    @parent.setter
    def parent(self, node):
        if node is self._parent:
            pass
        elif node is None:
            if self in self._parent.children:
                self._parent.remove(self)
            self._parent = None
        else:
            if self._parent is not None:
                self._parent.remove(self)
            try:
                self._parent = node
                node.add(self)
            except AttributeError as exc:
                self._parent = None
                raise ValueError("node parent must be node or None") from exc
    
    @property
    def siblings(self):
        '''A view of the children of this node's parent.'''
        return [] if self.parent is None else self.parent.children[:]
        
    def add(self, node):
        '''Adds the given node as a child of this one.'''
        if node not in self.children:
            self.children.append(node)
        node.parent = self
        return self
        
    def __iadd__(self, item):
        '''Adds a given node as a child of this one.'''
        if isinstance(item, Node):
            return self.add(item)
        else:
            return NotImplemented
        
    def remove(self, node):
        '''Removes the given node from this node's children.'''
        try:
            self.children.remove(node)
        except ValueError as exc:
            raise ValueError("tree.remove(x): x not in tree") from exc
        node.parent = None
        return self

    def __isub__(self, item):
        '''Removes a given node from this node's children.'''
        if isinstance(item, Node):
            return self.remove(item)
        else:
            return NotImplemented
    
    def detach(self):
        '''Removes this node from its parent node.'''
        self.parent = None
        return self
        
    def replace(self, child, adoptee):
        '''Replace a current child with a new child node.'''
        age = self.children.index(child)
        child.parent = None
        self.children.insert(age, adoptee)
        adoptee.parent = self
        
    def older_siblings(self):
        '''Yields this node's older siblings in increasing order of age.'''
        sibs = reversed(self.siblings)
        for node in sibs:
            if node == self:
                break
        yield from sibs
    
    @property
    def older_sibling(self):
        '''This node's immediate older sibling, or None.'''
        try:
            return next(self.older_siblings())
        except StopIteration:
            return None
    
    def younger_siblings(self):
        '''Yields this node's younger siblings in decreasing order of age.'''
        sibs = iter(self.siblings)
        for node in sibs:
            if node == self:
                break
        yield from sibs
    
    @property
    def younger_sibling(self):
        '''This node's immediate younger sibling, or None.'''
        try:
            return next(self.younger_siblings())
        except StopIteration:
            return None

    def __str__(self, depth=0):
        '''Print this node and its tree.'''
        descs = [("  " * depth) + str(self.data)]
        child_descs = (child.__str__(depth+1) for child in self.children)
        descs.extend(child_descs)
        return "\n".join(descs)
    
    def __repr__(self):
        desc = "{0} node ({1} parent, {2} children)"
        return desc.format(self.data, "1" if self._parent is not None
                           else "no", len(self.children))

    def __iter__(self):
        '''Iterates depth-first into this node's tree.'''
        yield self
        for child in self.children:
            yield from iter(child)