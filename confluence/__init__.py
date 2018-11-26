import collections as _collections
import functools as _functools
import contextlib as _contextlib
import inspect as _inspect

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

class _VersionHandle:
    def __init__(self, version=None):
        self.version = version
        self.version_string = None

def start_operation(node):
    """Idempotently starts an operation, such that all assignments between this function
    call will fall under an operation. If there is not already an operation under way,
    we create a new version number here and use that.
    
    Returns either a version handle or None depending on whether we were the ones who
    started the operation or not."""
    version_handle = super(Node, node).__getattribute__('__Node__version_handle')
    if version_handle.version is None:
        version_handle = _VersionHandle(_make_fresh_version())
        super(Node, node).__setattr__('__Node__version_handle', version_handle)
        return version_handle
    else:
        return None

def start_cooperation(version_handle, node):
    """Ensures that node sees version_handle as its current operation, replacing any existing
    operation underway. Returns the operation replaces to it can be put back when this operation
    is done."""
    old_version_handle = super(Node, node).__getattribute__('__Node__version_handle')
    super(Node, node).__setattr__('__Node__version_handle', version_handle)
    return old_version_handle

def end_cooperation(old_version_handle, node):
    """Reassigns the old version handle to node's version handle, ending the current operation's
    influence on that node."""
    super(Node, node).__setattr__('__Node__version_handle', old_version_handle)

def end_operation(version_handle):
    """Ends the operation indicated by version_handle. If version_handle is None then
    whoever received version_handle from start_operation didn't actually start the
    operation so shouldn't end it either. If version_handle is not None then this is our
    operation and we can safely end it."""
    if version_handle is not None:
        version_handle.version = None

@_contextlib.contextmanager
def operation(node, *others):
    """Context manager for an operation, see start_operation and end_operation"""
    version_handle = start_operation(node)
    cooperation_version_handle = super(Node, node).__getattribute__('__Node__version_handle')
    old_version_handles = [start_cooperation(cooperation_version_handle, n) for n in others]
    try:
        yield node
    finally:
        end_operation(version_handle)
        for old_handle, other in zip(old_version_handles, others):
            end_cooperation(old_handle, other)

def refdup(node):
    version_handle = super(Node, node).__getattribute__('__Node__version_handle')
    node_v = super(Node, node).__getattribute__('__Node__node')
    version_string = super(Node, node).__getattribute__('__Node__version_string')
    cls = super(Node, node).__getattribute__('__class__')
    return cls(
        __Node__version_handle=version_handle,
        __Node__version_string=version_string,
        __Node__node=node_v)

class Node:
    # We have this here so we don't impede whatever __init__ the class we took over has going on
    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)

        if '__Node__version_string' in kwargs:
            version_string = kwargs['__Node__version_string']
        else:
            version_string = (_make_fresh_version(),)
        node = kwargs.get('__Node__node', {})
        version_handle = kwargs.get('__Node__version_handle', _VersionHandle())

        super(Node, instance).__setattr__('__Node__version_string', version_string)
        super(Node, instance).__setattr__('__Node__node', node)
        super(Node, instance).__setattr__('__Node__version_handle', version_handle)
        
        return instance
    
    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        # this is the best way I could find to prevent __init__ from running when creating
        # a new handle to an existing node
        if hasattr(cls, '__init__'):
            real_init = getattr(cls, '__init__')
            @_functools.wraps(real_init)
            def fake_init(self, *args, **kwargs):
                # skip __init__ entirely if we're just changing version string
                if '__Node__version_string' in kwargs or '__Node__node' in kwargs:
                    pass
                else:
                    real_init(self, *args, **kwargs)
            setattr(cls, '__init__', fake_init)
        
        # "convert" all methods to start an operation context, so each one is perceived to
        # operate at one atomic version
        for field_name, field_value in cls.__dict__.items():
            if callable(field_value):
                # extra nested function to avoid only getting the last field_value in proxy's
                # closure
                def _closure(field_value=field_value):
                    @_functools.wraps(field_value)
                    def proxy(self, *args, **kwargs):
                        # ensure that the method "sees" arguments to be part of the same operation
                        cooperation_set = (n
                            for n in (*args, *kwargs.values())
                            if isinstance(n, Node))
                        with operation(self, *cooperation_set) as proxy:
                            return field_value(proxy, *args, **kwargs)
                    return proxy
                setattr(cls, field_name, _closure())
    
    def __getattribute__(self, name):
        node = super().__getattribute__('__Node__node')
        version_string = super().__getattribute__('__Node__version_string')
        version_handle = super().__getattribute__('__Node__version_handle')

        # if none of our attributes change but one of the fields' attributes change, we
        # won't see it if we don't update our version accordingly
        if version_handle.version is not None and version_string[-1] != version_handle.version:
            version_string = (*version_string, version_handle.version)
            super().__setattr__('__Node__version_string', version_string)

        if name in node:
            prefix, value = node[name].longest_prefix_item(version_string)
            if prefix is None:
                raise AttributeError(name)
            if isinstance(value, _NodeRef):
                ref_pfx, val, cls= value
                return cls(
                    __Node__version_string=ref_pfx+version_string[len(prefix)-1:],
                    __Node__node=val,
                    # ensure that the referenced node also sees the current version handle
                    # so a.b.c.d == x increments b's version of c like you would expect
                    __Node__version_handle=version_handle)
            else:
                return value
        elif name.startswith('__') and name.endswith('__'):
            return super().__getattribute__(name)
        else:
            raise AttributeError(name)

    def __repr__(self):
        node = super().__getattribute__('__Node__node')
        version_string = super().__getattribute__('__Node__version_string')
        values = { key : getattr(self, key) for key in node.keys() }
        return f'Node(version={version_string},values={values})'

    def __setattr__(self, name, value):
        node = super().__getattribute__('__Node__node')
        version_string = super().__getattribute__('__Node__version_string')
        version_handle = super().__getattribute__('__Node__version_handle')

        if isinstance(value, Node):
            value_node = object.__getattribute__(value, '__Node__node')
            value_version_string = object.__getattribute__(value, '__Node__version_string')
            value_cls = object.__getattribute__(value, '__class__')
            value = _NodeRef(value_version_string, value_node, value_cls)

        if version_handle.version is None:
            version_string = (*version_string, _make_fresh_version())
        elif version_string[-1] != version_handle.version:
            version_string = (*version_string, version_handle.version)
        # if the latest version == the one in the version handle, don't change anything
        # since reassignments are ok within an operation

        if name not in node:
            node[name] = Trie()
        node[name][version_string] = value

        super().__setattr__('__Node__version_string', version_string)

