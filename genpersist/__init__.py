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

def _new_node(node, *, version_string):
    cls = super(Node, node).__getattribute__('__class__')
    return cls.__new__(cls,
        __Node__data=_get_data(node),
        __Node__version_string=version_string,
        __Node__tmp_backing=_get_tmp_backing(node))

_operation_version = _contextvars.ContextVar('operation_version', default=None)
_operation_finalisers = _contextvars.ContextVar('operation_finalisers')
_operation_tmp_backing_cache = _contextvars.ContextVar('operation_tmp_backing_cache')

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
            # is one finaliser fails, don't corrupt the context variables permanently
            # (all subsequent invocations of the context manager will think they
            # are reentrant calls and will skip finalisers)
            try:
                for fin in operation_finalisers:
                    fin()
            finally:
                _operation_version.reset(reset_token)
                _operation_finalisers.reset(reset_token_f)
                _operation_tmp_backing_cache.reset(reset_token_c)

def _wrap(obj, assignee_version_string, tp_cache={}):
    current_version = _operation_version.get()
    if current_version is None:
        raise IncorrectOperationError()
    
    if isinstance(obj, Node):
        obj_version_string = _get_version_string(obj)
        print(obj, obj_version_string, assignee_version_string)
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

    if tp not in tp_cache:
        wrap_tp = type(tp.__name__ + 'Node', (tp, Node), {})
        tp_cache[tp] = wrap_tp
    else:
        wrap_tp = tp_cache[tp]

    wrapped = wrap_tp._wrap(obj)
    tmp_backing_cache[id(obj)] = wrapped

    return wrapped

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
        tmp_backing = kwargs.get('__Node__tmp_backing', None)
        mutable = kwargs.get('__Node__mutable', False)

        super(Node, instance).__setattr__('__Node__version_string', version_string)
        super(Node, instance).__setattr__('__Node__data', data)
        super(Node, instance).__setattr__('__Node__tmp_backing', tmp_backing)
        super(Node, instance).__setattr__('__Node__mutable', mutable)
        
        return instance

    @classmethod
    def _wrap(cls, obj):
        assert issubclass(cls, type(obj))
        wrapped_instance = cls.__new__(cls,
            __Node__version_string=(_operation_version.get(),),
            __Node__tmp_backing=obj)
        _operation_finalisers.get().append(wrapped_instance._operation_finalise)
        return wrapped_instance

    def _operation_finalise(self):
        tmp_backing = super().__getattribute__('__Node__tmp_backing')
        assert tmp_backing is not None
        super().__setattr__('__Node__tmp_backing', None)
        super().__setattr__('__Node__mutable', False)
        
        for k, v in tmp_backing.__dict__.items():
            setattr(self, k, v)
    
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
                raise super().__getattribute__(name)
            if isinstance(value, Node):
                ref_pfx = _get_version_string(value)
                calculated_version = ref_pfx+tuple(v for v in version_string if v > ref_pfx[-1])
                print('VER', 'version=', version_string, 'prefix=', prefix, 'ref_pfx=', ref_pfx, 'calc=', calculated_version)
                return _new_node(value, version_string=calculated_version)
                if ref_pfx == version_string:
                    return value
                else:
                    calculated_version = ref_pfx+version_string[len(prefix):]
                    return _new_node(value, version_string=calculated_version)
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

        tmp_backing = super().__getattribute__('__Node__tmp_backing')
        if tmp_backing is not None:
            return setattr(tmp_backing, name, value)

        # if isinstance(value, Node):
        #     value_data = _get_data(value)
        #     value_version_string = _get_version_string(value)
        #     value_cls = super(Node, value).__getattribute__('__class__')
        #     value = _NodeRef(value_version_string, value_data, value_cls)
        # elif not isinstance(value, (
        #         int, float, complex, bool, str, bytes, tuple, frozenset, range, type(None))):
        #     raise MutableValueError()

        # only allow setting properties during 1) an operation 2) related to us
        if version_string[-1] != _operation_version.get():
            raise IncorrectOperationError()

        if name not in data:
            data[name] = Trie()
        data[name][version_string] = _wrap(value, version_string)

