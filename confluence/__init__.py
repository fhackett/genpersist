import collections as _collections
import functools as _functools

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

class Node:
    # We have this here so we don't impede whatever __init__ the class we took over has going on
    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)

        if '__Node__version_string' in kwargs:
            version_string = kwargs['__Node__version_string']
        else:
            version_string = (_make_fresh_version(),)
        node = kwargs.get('__Node__node', {})

        super(Node, instance).__setattr__('__Node__version_string', version_string)
        super(Node, instance).__setattr__('__Node__node', node)
        
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
    
    def __getattribute__(self, name):
        node = super().__getattribute__('__Node__node')
        version_string = super().__getattribute__('__Node__version_string')

        if name in node:
            prefix, value = node[name].longest_prefix_item(version_string)
            print('got', prefix, value, version_string, name)
            if prefix is None:
                raise AttributeError(name)
            if isinstance(value, _NodeRef):
                ref_pfx, val, cls= value
                return cls(
                    __Node__version_string=ref_pfx+prefix[len(ref_pfx)-1:],
                    __Node__node=val)
            else:
                return value
        else:
            raise AttributeError(name)

    def __repr__(self):
        node = super().__getattribute__('__Node__node')
        values = { key : getattr(self, key) for key in node.keys() }
        return f'Node({values})'

    def __setattr__(self, name, value):
        node = super().__getattribute__('__Node__node')
        version_string = super().__getattribute__('__Node__version_string')

        if isinstance(value, Node):
            value_node = object.__getattribute__(value, '__Node__node')
            value_version_string = object.__getattribute__(value, '__Node__version_string')
            value_cls = object.__getattribute__(value, '__class__')
            value = _NodeRef(value_version_string, value_node, value_cls)

        version_string = (*version_string, _make_fresh_version())
        if name not in node:
            node[name] = Trie()
        node[name][version_string] = value

        super().__setattr__('__Node__version_string', version_string)

