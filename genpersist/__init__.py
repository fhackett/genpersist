import collections as _collections
import functools as _functools
import contextlib as _contextlib
import inspect as _inspect
import contextvars as _contextvars

class Trie:
    def __init__(self):
        self._children = {}

    def __eq__(self, other):
        if isinstance(other, Trie):
            return self._children == other._children
        else:
            return False

    def __repr__(self):
        return f'Trie({self._children})'

    def __setitem__(self, name, value):
        empty = name[:0]
        head = name[:1]
        tail = name[1:]
        if head == empty:
            self._children[empty] = value
        elif head in self._children:
            self._children[head][tail] = value
        else:
            t = Trie()
            self._children[head] = t
            t[tail] = value

    def longest_prefix_item(self, name):
        empty = name[:0]
        head = name[:1]
        tail = name[1:]
        
        if empty in self._children:
            empty_pair = empty, self._children[empty]
        else:
            empty_pair = None, None

        if head == empty:
            return empty_pair
        elif head in self._children:
            t = self._children[head]
            postfix, value = t.longest_prefix_item(tail)
            if postfix is None:
                return empty_pair
            else:
                return head + postfix, value
        else:
            return empty_pair

__version = 0
def _make_fresh_version():
    global __version
    v = __version
    __version += 1
    return v

_NodeRef = _collections.namedtuple('_NodeRef', ['prefix', 'ref', 'cls'])

def _get_version_string(node):
    return super(Node, node).__getattribute__('__Node__version_string')

def _get_operation_handle(node):
    return super(Node, node).__getattribute__('__Node__operation_handle')

def _get_data(node):
    return super(Node, node).__getattribute__('__Node__data')

def _new_node(node, *, version_string):
    cls = super(Node, node).__getattribute__('__class__')
    return cls.__new__(cls,
        __Node__data=_get_data(node),
        __Node__version_string=version_string)

_operation_version = _contextvars.ContextVar('operation_version', default=None)

class ConfluenceError(Exception):
    '''A base class for errors pertaining to confluent versioning.'''
    pass

class IncorrectOperationError(ConfluenceError):
    '''This means that there was an attempt to either:
    - instantiate a Node subclass outside of an operation context
    - mutate a Node subclass's instance in the "wrong" operation context,
    that is, either the node's version does not reflect the current operation
    or there is no current operation
    '''
    pass

@_contextlib.contextmanager
def operation(*nodes):
    """Context manager for an operation, see start_operation and end_operation"""
    current_version = _operation_version.get()
    if current_version is None:
        current_version = _make_fresh_version()
        reset_token = _operation_version.set(current_version)
    else:
        reset_token = None
    try:
        new_nodes = tuple(
            _new_node(node, version_string=(*_get_version_string(node), current_version))
            for node in nodes)
        if len(new_nodes) == 1:
            yield new_nodes[0]
        else:
            yield new_nodes
    finally:
        if reset_token is not None:
            _operation_version.reset(reset_token)

def snapshot(*nodes):
    """Returns a version of the given nodes with one element added to their version string.
    This is almost a no-op, except that if you make a node point to a snapshot of itself
    it will not actually form a circular reference."""
    version = _make_fresh_version()
    snapshots = tuple(_new_node(node, version_string=(*_get_version_string(node), version))
        for node in nodes)
    if len(snapshots) == 1:
        return snapshots[0]
    else:
        return snapshots

class Node:
    # We have this here so we don't impede whatever __init__ the class we took over has going on
    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)

        if '__Node__version_string' in kwargs:
            version_string = kwargs['__Node__version_string']
        else:
            v = _operation_version.get()
            if v is None:
                raise IncorrectOperationError()
            version_string = (v,)
        data = kwargs.get('__Node__data', {})

        super(Node, instance).__setattr__('__Node__version_string', version_string)
        super(Node, instance).__setattr__('__Node__data', data)
        
        return instance
    
    def __getattribute__(self, name):
        data = super().__getattribute__('__Node__data')
        version_string = super().__getattribute__('__Node__version_string')

        if name in data:
            prefix, value = data[name].longest_prefix_item(version_string)
            if prefix is None:
                raise super().__getattribute__(name)
            if isinstance(value, _NodeRef):
                ref_pfx, val, cls= value
                return cls.__new__(cls,
                    __Node__version_string=ref_pfx+version_string[len(prefix)-1:],
                    __Node__data=val)
            else:
                return value
        else:
            return super().__getattribute__(name)

    def __repr__(self):
        data = super().__getattribute__('__Node__data')
        version_string = super().__getattribute__('__Node__version_string')
        values = { key : getattr(self, key) for key in data.keys() }
        return f'Node(version={version_string},values={values})'

    def __setattr__(self, name, value):
        data = super().__getattribute__('__Node__data')
        version_string = super().__getattribute__('__Node__version_string')

        if isinstance(value, Node):
            value_data = _get_data(value)
            value_version_string = _get_version_string(value)
            value_cls = super(Node, value).__getattribute__('__class__')
            value = _NodeRef(value_version_string, value_data, value_cls)

        # only allow setting properties during 1) an operation 2) related to us
        if version_string[-1] != _operation_version.get():
            raise IncorrectOperationError()

        if name not in data:
            data[name] = Trie()
        data[name][version_string] = value

