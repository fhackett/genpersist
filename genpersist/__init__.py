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
        items = { k : v for k, v in self.items()}
        return f'Trie({items})'

    def items(self):
        for k, v in self._children.items():
            if len(k) == 0:
                yield k, v
            else:
                for kk, vv in v.items():
                    yield k+kk, vv

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
    return (v, 0)

def _get_version_string(node):
    return super(Node, node).__getattribute__('__Node__version_string')

def _get_data(node):
    return super(Node, node).__getattribute__('__Node__data')

def _get_tmp_backing(node):
    return super(Node, node).__getattribute__('__Node__tmp_backing')

def _remove_tmp_backing(node):
    super(Node, node).__setattr__('__Node__tmp_backing', None)

def _new_node(node, *, version_string):
    cls = super(Node, node).__getattribute__('__class__')
    return cls.__new__(cls,
        __Node__data=_get_data(node),
        __Node__version_string=version_string,
        __Node__tmp_backing=_get_tmp_backing(node))

_operation_version = _contextvars.ContextVar('operation_version', default=None)
_operation_finalisers = _contextvars.ContextVar('operation_finalisers')
_operation_tmp_backing_cache = _contextvars.ContextVar('operation_tmp_backing_cache')
_skipped_kwargs = _contextvars.ContextVar('skipped_kwargs', default=None)

_ImpureValue = _collections.namedtuple('_ImpureValue', ['value'])

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

class MutableValueError(ConfluenceError):
    '''You cannot assign a mutable object that is not tracked by genpersist to a
    Node's attribute.'''
    pass

@_contextlib.contextmanager
def operation(*nodes):
    """Context manager for an operation, see start_operation and end_operation"""
    current_version = _operation_version.get()
    if current_version is None:
        current_version = _make_fresh_version()
        operation_finalisers = []
        operation_tmp_backing_cache = {}
        reset_token = _operation_version.set(current_version)
        reset_token_f = _operation_finalisers.set(operation_finalisers)
        reset_token_c = _operation_tmp_backing_cache.set(operation_tmp_backing_cache)
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
            # if one finaliser fails, don't corrupt the context variables permanently
            # (all subsequent invocations of the context manager will think they
            # are reentrant calls and will skip finalisers)
            try:
                for fin in operation_finalisers:
                    fin()
            finally:
                _operation_version.reset(reset_token)
                _operation_finalisers.reset(reset_token_f)
                _operation_tmp_backing_cache.reset(reset_token_c)

_tp_cache = {}

def register_wrapper(tp):
    '''A class decorator that allows users to customise how certain classes are
    treated by genpersist. There is a fairly general catch-all conversion process
    that will work for most "normal" classes, but if you're doing something unusual
    involving builtins this may be for you.'''
    assert tp not in _tp_cache
    def register(cls):
        _tp_cache[tp] = cls
        return cls
    return register

def _clean_kwargs(kwargs):
    return {k : v
            for k, v in kwargs.items()
            if k not in ('__Node__version_string', '__Node__data', '__Node__tmp_backing')}

def _wrap(obj, assignee_version_string):
    current_version = _operation_version.get()
    if current_version is None:
        raise IncorrectOperationError()
    
    if isinstance(obj, _ImpureValue):
        return obj

    if isinstance(obj, Node):
        obj_version_string = _get_version_string(obj)
        # special case: if the assigned node's version is entirely a prefix of the assignee's
        # version string, accessing the attribute later will cause the latest version to
        # be retrieved, not the one assigned. That would break intentional past references,
        # in fact leading to unintended cycles in the poster example of a self-appending
        # linked list. If you actually _wanted_ a cycle, you would just assign the latest
        # reference instead (which is what happens if code just blindly reads attributes
        # from a being operated on in an operation context)
        if obj_version_string[-1] != current_version:
            v1, v2 = obj_version_string[-1]
            return _new_node(obj, version_string=(*obj_version_string, (v1, v2+1)))
        return obj
    
    tmp_backing_cache = _operation_tmp_backing_cache.get()
    if id(obj) in tmp_backing_cache:
        return tmp_backing_cache[id(obj)]

    tp = type(obj)
    # don't do anything to immutable primitives
    if tp in (type(None), str, bytes, int, float, complex):
        return obj

    if tp not in _tp_cache:
        def fake_new(cls, *args, **kwargs):
            reset = _skipped_kwargs.set(kwargs)
            try:
                i = super(wrap_tp, cls).__new__(cls, *args, **_clean_kwargs(kwargs))
            finally:
                _skipped_kwargs.reset(reset)
            return i
        wrap_tp = type(tp.__name__ + 'Node', (tp, Node), {'__slots__': (), '__new__': fake_new})
        _tp_cache[tp] = wrap_tp
    else:
        wrap_tp = _tp_cache[tp]

    wrapped = wrap_tp._wrap(obj)
    tmp_backing_cache[id(obj)] = wrapped

    return wrapped

class Node:
    # support classes that use __slots__ (if we define it but they don't it's meaningless,
    # if we both defined it everything works the way the other class expected)
    __slots__ = [
        '__Node__version_string',
        '__Node__data',
        '__Node__tmp_backing',
    ]

    # We have this here so we don't impede whatever __init__ the class we took over has going on
    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)

        skw = _skipped_kwargs.get()
        if skw is not None:
            kwargs = skw

        if '__Node__version_string' in kwargs:
            version_string = kwargs['__Node__version_string']
        else:
            v = _operation_version.get()
            if v is None:
                raise IncorrectOperationError()
            version_string = (v,)
        data = kwargs.get('__Node__data', {})
        tmp_backing = kwargs.get('__Node__tmp_backing', None)

        super(Node, instance).__setattr__('__Node__version_string', version_string)
        super(Node, instance).__setattr__('__Node__data', data)
        super(Node, instance).__setattr__('__Node__tmp_backing', tmp_backing)
        
        return instance

    @classmethod
    def _wrap(cls, obj):
        wrapped_instance = cls.__new__(cls,
            __Node__version_string=(_operation_version.get(),),
            __Node__tmp_backing=obj)
        _operation_finalisers.get().append(wrapped_instance._operation_finalise)
        return wrapped_instance

    def _operation_finalise(self):
        tmp_backing = super().__getattribute__('__Node__tmp_backing')
        assert tmp_backing is not None
        super().__setattr__('__Node__tmp_backing', None)
        
        for k, v in tmp_backing.__dict__.items():
            setattr(self, k, v)
    
    def _adapt_reference_version(self, value):
        if isinstance(value, Node):
            version_string = _get_version_string(self)
            ref_pfx = _get_version_string(value)
            calculated_version = ref_pfx+tuple(v for v in version_string if v > ref_pfx[-1])
            if ref_pfx != calculated_version:
                return _new_node(value, version_string=calculated_version)
        return value

    def __getattribute__(self, name):
        data = super().__getattribute__('__Node__data')
        version_string = super().__getattribute__('__Node__version_string')

        tmp_backing = super().__getattribute__('__Node__tmp_backing')
        if tmp_backing is not None:
            if hasattr(tmp_backing, name):
                return getattr(tmp_backing, name)
            else:
                return super().__getattribute__(name)

        if name in data:
            prefix, value = data[name].longest_prefix_item(version_string)
            if prefix is None:
                return super().__getattribute__(name)
            return self._adapt_reference_version(value)
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

        tmp_backing = super().__getattribute__('__Node__tmp_backing')
        if tmp_backing is not None:
            return setattr(tmp_backing, name, value)

        # only allow setting properties during 1) an operation 2) related to us
        if version_string[-1] != _operation_version.get():
            raise IncorrectOperationError()

        if name not in data:
            data[name] = Trie()
        data[name][version_string] = _wrap(value, version_string)

@register_wrapper(tuple)
class TupleNode(Node):

    def __init__(self, src=()):
        version_string = _get_version_string(self)
        self._tuple = _ImpureValue(tuple(_wrap(v, version_string) for v in src))

    @classmethod
    def _wrap(cls, obj):
        # since tuples themselves are immutable (but their members might not be)
        # we can just convert the tuple on the spot, unlike the catch-all mutable class
        # conversion you'll see for plain Node objects
        wrapped = TupleNode.__new__(cls)
        # as a tricky edge case however, you could feed this a tuple that indirectly contains
        # a cyclic reference. We cache our converted object _before_ trying to recursively
        # convert the members in order to catch and resolve that cycle instead of infinitely
        # recursing.
        _operation_tmp_backing_cache.get()[id(obj)] = wrapped
        wrapped.__init__(obj)
        return wrapped

    def __len__(self):
        return len(self._tuple.value)

    def __repr__(self):
        return f'$({", ".join(repr(e) for e in self)})'

    def __hash__(self):
        return hash(tuple(self))

    def __iter__(self):
        return (self[i] for i in range(len(self)))

    def __eq__(self, other):
        if not isinstance(other, (tuple, TupleNode)):
            return False

        return len(self) == len(other) and all(a == b for a, b in zip(self, other))

    def _comp(self, other, *, lt_result, gt_result, when_all_eq):
        if not isinstance(other, (tuple, TupleNode)):
            return NotImplemented

        for a, b in zip(self, other):
            if a < b: return lt_result
            elif a > b: return gt_result
        # if we got here everything we zipped was equal
        return when_all_eq(len(self), len(other))

    def __lt__(self, other):
        return self._comp(other,
            lt_result=True,
            gt_result=False,
            when_all_eq=lambda s, o: s < o)

    def __le__(self, other):
        return self._comp(other,
            lt_result=True,
            gt_result=False,
            when_all_eq=lambda s, o: s <= o)

    def __gt__(self, other):
        return self._comp(other,
            lt_result=False,
            gt_result=True,
            when_all_eq=lambda s, o: s > o)

    def __ge__(self, other):
        return self._comp(other,
            lt_result=False,
            gt_result=True,
            when_all_eq=lambda s, o: s >= o)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return TupleNode(self[i] in range(index.start, index.stop, index.step))
        return self._adapt_reference_version(self._tuple.value[index])

    def __add__(self, other):
        if not isinstance(other, (tuple, TupleNode)):
            return NotImplemented

        return TupleNode((*self, *other))

    def __radd__(self, other):
        if not isinstance(other, (tuple, TupleNode)):
            return NotImplemented

        return TupleNode((*other, *self))

    def __mul__(self, times):
        try:
            r = range(times)
        except TypeError:
            # presumably, times was not an appropriate argument for range
            return NotImplemented
        return TupleNode(v for v in self._tuple.value for t in r)

    def __rmul__(self, times):
        return self.__mul__(times)
    
    # __contains__ leave it to the default implementation for now

    def count(self, elem):
        return sum(1 if e == elem else 0 for e in self)

    def index(self, x, i=0, j=None):
        if j is None:
            j = len(self)
        for p in range(i, j):
            if self[p] == x:
                return p
        raise ValueError(x)


@register_wrapper(list)
class ListNode(Node):

    class _Record(Node):
        #__slots__ = ('nxt', 'jmp', 'len', 'val')
        def __init__(self, nxt, jmp, length, val):
            self.nxt = nxt
            self.jmp = jmp
            self.len = length
            self.val = val

    def __init__(self, iterable=(), s=None):
        self._root = s
        self.extend(iterable)

    def _operation_finalise(self):
        backing = _get_tmp_backing(self)
        assert backing is not None
        _remove_tmp_backing(self)
        self._root = None
        self.extend(backing)
    
    def __eq__(self, other):
        if isinstance(other, (ListNode, list)):
            return len(self) == len(other) and all(a == b for a, b in zip(self, other))
        else:
            return False

    def append(self, val):
        if self._root is None:
            self._root = ListNode._Record(None, None, 1, val)
        else:
            s = self._root
            
            t = s.jmp
            
            if t is None:
                t_len = 0
            else:
                t_len = t.len
            
            if t is None or t.jmp is None:
                t_jmp_len = 0
            else:
                t_jmp_len = t.jmp.len
            
            if s.len - t_len == t_len - t_jmp_len:
                t = t.jmp
            else:
                t = s
            
            self._root = ListNode._Record(s, t, s.len+1, val)

    def extend(self, iterable):
        for e in iterable:
            self.append(e)

    def __len__(self):
        b = _get_tmp_backing(self)
        if b is not None:
            return len(b)

        if self._root is None:
            return 0
        else:
            return self._root.len

    def _find_prefix(self, pos):
        if pos < 0 or pos >= len(self):
            return None

        s = self._root
        while s.len-1 > pos:
            if s.jmp is None or s.jmp.len-1 < pos:
                s = s.nxt
            else:
                s = s.jmp
        return s

    def __getitem__(self, index):
        if isinstance(index, slice):
            raise Exception('TODO')
        p = self._find_prefix(index)
        if p is None:
            raise IndexError(index)
        return p.val

    def __setitem__(self, index, value):
        b = _get_tmp_backing(self)
        if b is not None: b[index] = value; return

        if isinstance(index, slice):
            raise Exception('TODO')
        p = self._find_prefix(index)
        if p is None:
            raise IndexError(index)
        p.val = value

    def __delitem__(self, index):
        b = _get_tmp_backing(self)
        if b is not None: del b[index]; return
        
        raise Exception('TODO')

    def __iter__(self):
        b = _get_tmp_backing(self)
        if b is not None: return iter(b)
        return self._iter_from(0)

    def insert(self, i, x):
        if i < 0 or i > len(self):
            raise IndexError(i)

        # keep all elements up to i unmodified
        p = self._find_prefix(i-1)
        # rebuild the list past that point, using a separate object so __iter__ doesn't get
        # confused
        minion = ListNode(s=p)
        minion.append(x)
        minion.extend(self._iter_from(i))
        self._root = minion._root

    def pop(self, i=None):
        if i is None:
            i = len(self)-1
        if i < 0 or i >= len(self):
            raise IndexError(i)

        p = self._find_prefix(i)
        minion = ListNode(s=p.nxt)
        minion.extend(self._iter_from(i+1))
        self._root = minion._root
        return p.val

    def _iter_from(self, start):
        if self._root is None or start >= len(self): return
        # hold a stack of unvisited nodes
        # (this may, but might not for small lists, omit skipped nodes)
        stack = [self._root]
        while len(stack) != 0:
            s = stack.pop()
            # this is basically a search operation unrolled to store each node
            # it checks as it iterates
            while s.len-1 > start:
                if s.jmp is None or s.jmp.len-1 < start:
                    if s.nxt is None: break
                    if s.len-1 > start: stack.append(s)
                    s = s.nxt
                else:
                    stack.append(s)
                    s = s.jmp

            yield s.val
            start += 1

