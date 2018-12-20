import collections as _collections
import functools as _functools
import contextlib as _contextlib
import inspect as _inspect
import contextvars as _contextvars
import itertools as _itertools

_Sentinel = object()
_ValueSentinel = object()

class Trie:
    __slots__ = ('_children',)
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

    def _items(self, pfx, children):
        for k, v in children.items():
            if k is _ValueSentinel:
                yield pfx+k, v
            else:
                yield from self._items(pfx+(k,), v)

    def items(self):
        yield from self._items((), self._children)

    def __setitem__(self, name, value):
        i = 0
        children = self._children
        while i < len(name):
            c2 = children.get(name[i], _Sentinel)
            if c2 is _Sentinel:
                c2 = {}
                children[name[i]] = c2
            children = c2
            i += 1
        children[_ValueSentinel] = value

    def longest_prefix_item(self, name):
        pfx = []
        i = 0
        last_valid_i = None
        last_valid_v = None
        children = self._children
        while i < len(name):
            v = children.get(name[i], _Sentinel)
            if v is _Sentinel:
                vv = children.get(_ValueSentinel, _Sentinel)
                if vv is _Sentinel:
                    if last_valid_i is None:
                        return None, None
                    return name[:last_valid_i], last_valid_v
                else:
                    return name[:i], vv
            else:
                vv = children.get(_ValueSentinel, _Sentinel)
                if vv is not _Sentinel:
                    last_valid_i = i
                    last_valid_v = vv
                children = v
            i += 1

        vv = children.get(_ValueSentinel, _Sentinel)
        if vv is _Sentinel:
            if last_valid_i is None:
                return None, None
            else:
                return name[:last_valid_i], last_valid_v
        else:
            return name, vv

__version = 0
def _make_fresh_version():
    global __version
    v = __version
    __version += 1
    return (v, 0)

def _get_version_string(node):
    return super(Node, node).__getattribute__('_Node__version_string')

def _get_data(node):
    return super(Node, node).__getattribute__('_Node__data')

def _get_tmp_backing(node):
    return super(Node, node).__getattribute__('_Node__tmp_backing')

def _remove_tmp_backing(node):
    super(Node, node).__setattr__('_Node__tmp_backing', None)

def _new_node(node, *, version_string):
    cls = super(Node, node).__getattribute__('__class__')
    return cls.__new__(cls,
        _Node__data=_get_data(node),
        _Node__version_string=version_string,
        _Node__tmp_backing=_get_tmp_backing(node))

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
            if k not in ('_Node__version_string', '_Node__data', '_Node__tmp_backing')}

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
    __slots__ = (
        '_Node__version_string',
        '_Node__data',
        '_Node__tmp_backing',
    )

    # We have this here so we don't impede whatever __init__ the class we took over has going on
    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)

        skw = _skipped_kwargs.get()
        if skw is not None:
            kwargs = skw

        if '_Node__version_string' in kwargs:
            version_string = kwargs['_Node__version_string']
        else:
            v = _operation_version.get()
            if v is None:
                raise IncorrectOperationError()
            version_string = (v,)
        data = kwargs.get('_Node__data', {})
        tmp_backing = kwargs.get('_Node__tmp_backing', None)

        super(Node, instance).__setattr__('_Node__version_string', version_string)
        super(Node, instance).__setattr__('_Node__data', data)
        super(Node, instance).__setattr__('_Node__tmp_backing', tmp_backing)
        
        return instance

    @classmethod
    def _wrap(cls, obj):
        wrapped_instance = cls.__new__(cls,
            _Node__version_string=(_operation_version.get(),),
            _Node__tmp_backing=obj)
        _operation_finalisers.get().append(wrapped_instance._operation_finalise)
        return wrapped_instance

    def _operation_finalise(self):
        tmp_backing = super().__getattribute__('_Node__tmp_backing')
        assert tmp_backing is not None
        super().__setattr__('_Node__tmp_backing', None)
        
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
        data = super().__getattribute__('_Node__data')
        version_string = super().__getattribute__('_Node__version_string')

        tmp_backing = super().__getattribute__('_Node__tmp_backing')
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
        data = super().__getattribute__('_Node__data')
        version_string = super().__getattribute__('_Node__version_string')
        values = { key : getattr(self, key) for key in data.keys() }
        return f'Node(version={version_string},values={values})'

    def __setattr__(self, name, value):
        data = super().__getattribute__('_Node__data')
        version_string = super().__getattribute__('_Node__version_string')

        tmp_backing = super().__getattribute__('_Node__tmp_backing')
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
    __slots__ = ()

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

class CopyList(Node):
    __slots__ = ()

    def __init__(self, iterable=()):
        version_string = _get_version_string(self)
        self._version = version_string
        self._impl = _ImpureValue(list(_wrap(v, version_string) for v in iterable))

    def _operation_finalise(self):
        backing = _get_tmp_backing(self)
        assert backing is not None
        _remove_tmp_backing(self)
        version_string = _get_version_string(self)
        self._version = version_string
        self._impl = _ImpureValue(list(_wrap(v, version_string) for v in backing))

    def _maybe_copy(fn):
        @_functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            b = _get_tmp_backing(self)
            if b is not None:
                return fn(self, *args, **kwargs)
            old = self._impl.value
            if self._version != _get_version_string(self):
                self._impl = _ImpureValue(self._impl.value[:])
                self._version = _get_version_string(self)
            r = fn(self, *args, **kwargs)
            return r
        return wrapper

    @_maybe_copy
    def append(self, v):
        version_string = _get_version_string(self)
        self._impl.value.append(_wrap(v, version_string))

    @_maybe_copy
    def extend(self, iterable):
        b = _get_tmp_backing(self)
        if b is None: b = self._impl.value
        
        version_string = _get_version_string(self)
        b.extend(_wrap(v, version_string) for v in iterable)
    
    def __getitem__(self, index):
        if isinstance(index, slice):
            return list(self._adapt_reference_version(v) for v in self._impl.value[index])
        else:
            return self._adapt_reference_version(self._impl.value[index])

    @_maybe_copy
    def __setitem__(self, index, value):
        version_string = _get_version_string(self)
        if isinstance(index, slice):
            self._impl.value[index] = (_wrap(v, version_string) for v in value)
        else:
            self._impl.value[index] = _wrap(value, version_string)

    @_maybe_copy
    def insert(self, index, value):
        self[index:index] = (value,)

    @_maybe_copy
    def __delitem__(self, index):
        b = _get_tmp_backing(self)
        if b is None: b = self._impl.value
        del b[index]

    @_maybe_copy
    def pop(self, index=-1):
        c = self[index]
        del self[index]
        return c

    def __len__(self):
        b = _get_tmp_backing(self)
        if b is not None:
            return len(b)
        return len(self._impl.value)

    def __iter__(self):
        b = _get_tmp_backing(self)
        if b is None:
            b = self._impl.value

        for i in b:
            yield self._adapt_reference_version(i)

    def __eq__(self, other):
        if isinstance(other, (CopyList, list)):
            return len(self) == len(other) and all(a == b for a, b in zip(self, other))
        else:
            return False

@register_wrapper(list)
class ListNode(Node):
    __slots__ = ()

    class _Record(Node):
        __slots__ = ()
        def __init__(self, nxt, jmp, length, val):
            self.nxt = nxt
            self.jmp = jmp
            self.len = length
            self.val = val
            self.back = None

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
        self.insert(len(self), val)

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

        err_index = index
        if index < 0:
            index += len(self)

        p = self._find_prefix(index)
        if p is None:
            raise IndexError(err_index)
        return p.val

    def __setitem__(self, index, value):
        b = _get_tmp_backing(self)
        if b is not None: b[index] = value; return

        if isinstance(index, slice):
            raise Exception('TODO')

        err_index = index
        if index < 0:
            index += len(self)

        p = self._find_prefix(index)
        if p is None:
            raise IndexError(err_index)
        p.val = value

    def __delitem__(self, index):
        b = _get_tmp_backing(self)
        if b is not None: del b[index]; return

        if isinstance(index, slice):
            raise Exception('TODO')

        err_index = index
        if index < 0:
            index += len(self)
        try:
            self.pop(index)
        except IndexError as e:
            raise IndexError(err_index) from e

    def __iter__(self):
        b = _get_tmp_backing(self)
        if b is not None: return iter(b)
        return self._iter_from(0)

    def insert(self, i, x):
        if i < 0 or i > len(self):
            raise IndexError(i)

        # keep all elements up to i unmodified
        p = self._find_prefix(i)
        if p is None: # i == len(self)
            before = self._root
        else:
            before = p.nxt

        if before is None:
            new_len = 1
        else:
            new_len = before.len+1
        new = ListNode._Record(before, None, new_len+1, x)
        
        if p is None:
            self._root = new
        else:
            p.nxt = new
        
        new.back = p
        if before is not None:
            before.back = new
        self._recalculate_from(new)

    def pop(self, i=None):
        if i is None:
            i = len(self)-1
        if i < 0 or i >= len(self):
            raise IndexError(i)

        p = self._find_prefix(i)
        before = p.nxt
        after = p.back
        if before is not None:
            before.back = after
        if after is None:
            self._root = before
        else:
            after.nxt = before
        self._recalculate_from(after)
        return p.val

    def _recalculate_from(self, p):
        if p is None:
            return # empty

        # start from the first changed node
        root = p.nxt
        if root is None:
            p.nxt = None
            p.jmp = None
            p.len = 1
            root = p

        while root.back is not None:
            p = root.back
                
            t = root.jmp
                
            if t is None:
                t_len = 0
            else:
                t_len = t.len
            
            if t is None or t.jmp is None:
                t_jmp_len = 0
            else:
                t_jmp_len = t.jmp.len
            
            if root.len - t_len == t_len - t_jmp_len:
                t = t.jmp
            else:
                t = root
            
            p.jmp = t
            p.len = root.len+1
            root = root.back

    def _iter_from(self, start):
        p = self._find_prefix(start)
        while p is not None:
            yield p.val
            p = p.back

# CHUNK_SIZE = 64
# 
# class ChunkList(Node):
#     __slots__ = ()
#     def __init__(self, iterable=()):
#         self._bins = ListNode()
#         self._sizes = ListNode()
# 
#     def _find_bin(self, pos):
#         return _bisect.bisect_left(self._sizes, pos)
#     
#     def __len__(self):
#         if len(self._sizes) == 0:
#             return 0
#         else:
#             return self._sizes[-1]
# 
#     def append(self, e):
#         if len(self._bins) == 0:
#             self._bins.append(CopyList([e]))
#             self._sizes.append(1)
#         else:
#             last_bin = self._bins[-1]
#             if len(last_bin) == CHUNK_SIZE:
#                 new_last_bin = CopyList(last_bin[CHUNK_SIZE//2:])
#                 del last_bin[:CHUNK_SIZE//2]
#                 new_last_bin.append(e)
#                 self._sizes[-1] -= CHUNK_SIZE//2
#                 self._sizes.append(CHUNK_SIZE//2 + 1)
#             else:
#                 last_bin.append(e)
#                 self._sizes[-1] += 1
# 
#     def _del_range(self, start, stop):
#         i = self._find_bin(start)
#         s_start = self._sizes[i]
#         if stop-s_start < len(self._bins[start-s_start]):
#             s_stop = stop - s_start
#         else:
#             s_stop = -1
#         del self._bins[start-s_start:s_stop]
# 
#     def _insert_seq(self, pos, seq):
# 
# 
#     def __setitem__(self, index, value):
#         if isinstance(index, slice):
#             start = index.start or 0
#             stop = len(self) if index.stop is None else index.stop
#             if index.step is not None:
#                 raise Exception('TODO')

