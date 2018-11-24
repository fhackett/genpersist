from collections import namedtuple

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

_NodeRef = namedtuple('_NodeRef', ['prefix', 'ref'])

class _Node:
    pass

class NodeView:
    def __init__(self, node, version_str):
        super().__setattr__('__node', node)
        super().__setattr__('__version_str', version_str)

    def __getattr__(self, name):
        node = super().__getattribute__('__node')
        version_str = super().__getattribute__('__version_str')
        trie = node[name]
        prefix, attr = trie.longest_prefix_item(version_str)
        if isinstance(attr, _NodeRef):
            new_prefix, other_node = attr
            return NodeView(other_node, new_prefix+version_str[len(prefix):])
        else:
            return attr

    def __setattr__(self, name, attr):
        node = super().__getattribute__('__node')
        version_str = super().__getattribute__('__version_str')
        try:
            trie = getattr(node, name)
        except AttributeError:
            trie = Trie()
            setattr(node, name, trie)
        assert isinstance(trie, Trie)
        version_str += _make_fresh_version(),
        if isinstance(attr, NodeView):
            other_node = super(NodeView, attr).__getattribute__('__node')
            other_version_str = super(NodeView, attr).__getattribute__('__version_str')
            trie[version_str] = _NodeRef(other_version_str, other_node)
        else:
            trie[version_str] = attr
        super().__setattr__('__version_str', version_str)

    def __repr__(self):
        node = super().__getattribute__('__node')
        version_str = super().__getattribute__('__version_str')
        return f'NodeView(version_str={version_str}, data={node})'

class NodeMeta(type):
    def __new__(cls, name, bases, attrs):
        print(cls, name, bases, attrs)
        if '__init__' in attrs:
            old_init = attrs['__init__']
        else:
            old_init = lambda *args, **kwargs: None
        def __init__(self, *args, **kwargs):
            print('real_init')
            NodeView.__init__(self, {}, ())
            old_init(self, *args, **kwargs)
        attrs['__init__'] = __init__
        print(attrs)
        #attrs['__new_view'] = 

        return type(name+'View', (NodeView, *bases), attrs)

class Node(metaclass=NodeMeta):
    pass

