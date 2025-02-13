"""
Helper interface and functions for generalized object configuration, to and
from JSON-compliant dictionaries.

While this interface and utility methods should be general enough to add
JSON-compliant dictionary-based configuration to any object, this was created
in mind with the SMQTK plugin module.

Standard configuration dictionaries should be JSON compliant take the following
general format:

.. code-block:: json

    {
        "type": "one-of-the-keys-below",
        "ClassName1": {
            "param1": "val1",
            "param2": "val2"
        },
        "ClassName2": {
            "p1": 4.5,
            "p2": null
        }
    }

The "type" key is considered a special key that should always be present and it
specifies one of the other keys within the same dictionary. Each other key in
the dictionary should be the name of a ``Configurable`` inheriting class type.
Usually, the classes named within a block inherit from a common interface and
the "type" value denotes a selection of a specific sub-class for use, though
this is not required property of these constructs.

"""
import abc
import inspect
import json
import types
from typing import (
    Any, Callable, Dict, FrozenSet, Iterable, Sequence, Set, Tuple, Type,
    TypeVar, Union
)

from smqtk_core.dict import merge_dict


# Type variable for arbitrary types.
T = TypeVar("T")
# Type variable for Configurable-inheriting types.
C = TypeVar("C", bound="Configurable")


def _param_map_func(func: Callable) -> Dict[str, object]:
    """
    Get the given function's parameter names and default values as a dict.

    :param func: Function to map parameter keys and defaults from. Usually a
        constructor in this context.

    :return: Dictionary whose keys are the string names of input function
        parameters, minus the 'self' parameter, and whose values are the
        default defined by the function, or None if there is no default
        specified.
    """
    sig = inspect.signature(func)
    # We don't care to record `*` or `**` params, so only retain non-variadic
    # parameters.
    keep_kinds = {inspect.Parameter.POSITIONAL_ONLY,
                  inspect.Parameter.POSITIONAL_OR_KEYWORD,
                  inspect.Parameter.KEYWORD_ONLY}

    pmap = {}
    for k, param in sig.parameters.items():
        if k == 'self':
            continue
        elif param.kind in keep_kinds:
            dflt = param.default
            if dflt is param.empty:
                # We want to map empty (no default) to the None value.
                dflt = None
            pmap[k] = dflt
    return pmap


def _type_to_key(t: Type) -> str:
    """
    Common function for transforming a class type to its associated string key
    for use in configuration semantics.

    :param t: Type to get the key for.
    :return: String key for the input type.
    """
    return f"{t.__module__}.{t.__name__}"


class Configurable (metaclass=abc.ABCMeta):
    """
    Interface for objects that should be configurable via a configuration
    dictionary consisting of JSON types.
    """

    __slots__ = ()

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """
        Generate and return a default configuration dictionary for this class.
        This will be primarily used for generating what the configuration
        dictionary would look like for this class without instantiating it.

        By default, we observe what this class's constructor takes as arguments,
        turning those argument names into configuration dictionary keys. If any
        of those arguments have defaults, we will add those values into the
        configuration dictionary appropriately. The dictionary returned should
        only contain JSON compliant value types.

        It is not be guaranteed that the configuration dictionary returned
        from this method is valid for construction of an instance of this class.

        :return: Default configuration dictionary for the class.
        :rtype: dict

        >>> # noinspection PyUnresolvedReferences
        >>> class SimpleConfig(Configurable):
        ...     def __init__(self, a=1, b='foo'):
        ...         self.a = a
        ...         self.b = b
        ...     def get_config(self):
        ...         return {'a': self.a, 'b': self.b}
        >>> self = SimpleConfig()
        >>> config = self.get_default_config()
        >>> assert config == {'a': 1, 'b': 'foo'}
        """
        # Check that the current class has a defined constructor. Otherwise a
        # default constructor does not checkout as a method or function.
        if isinstance(cls.__init__, (types.MethodType, types.FunctionType)):
            dflt_config = _param_map_func(cls.__init__)
            # TODO: Validate JSON compliance of ``dflt_config`` here?
            return dflt_config

        # No constructor explicitly defined on this class
        return {}

    @classmethod
    def from_config(
        cls: Type[C],
        config_dict: Dict,
        merge_default: bool = True
    ) -> C:
        """
        Instantiate a new instance of this class given the configuration
        JSON-compliant dictionary encapsulating initialization arguments.

        This base method is adequate without modification when a class's
        constructor argument types are JSON-compliant.  If one or more are not,
        however, this method then needs to be overridden in order to convert
        from a JSON-compliant stand-in into the more complex object the
        constructor requires.  It is recommended that when complex types *are*
        used they also inherit from the :class:`Configurable` in order to
        hopefully make easier the conversion to and from JSON-compliant
        stand-ins.

        When this method *does* need to be overridden, this usually looks like
        the following pattern:

        .. code-block:: python

           D = TypeVar("D", bound="MyClass")

           class MyClass (Configurable):

               @classmethod
               def from_config(
                   cls: Type[D],
                   config_dict: Dict,
                   merge_default: bool = True
               ) -> D:
                   # Perform a shallow copy of the input ``config_dict`` which
                   # is important to maintain idempotency.
                   config_dict = dict(config_dict)

                   # Optionally guarantee default values are present in the
                   # configuration dictionary.  This is useful when the
                   # configuration dictionary input is partial and the logic
                   # contained here wants to use config parameters that may
                   # have defaults defined in the constructor.
                   if merge_default:
                       config_dict = merge_dict(cls.get_default_config(),
                                                config_dict)

                   #
                   # Perform any overriding of `config_dict` values here.
                   #

                   # Create and return an instance using the super method.
                   return super().from_config(config_dict,
                                              merge_default=merge_default)

        *Note on type annotations*:
        When defining a sub-class of configurable and override this class
        method, we will need to defined a new TypeVar that is bound at the new
        class type.  This is because super requires a type to be given that
        descends from the implementing type.  If `C` is used as defined in this
        interface module, which is upper-bounded on the base
        :py:class:`Configurable` class, the type analysis will see that we are
        attempting to invoke super with a type that may not strictly descend
        from the implementing type (``MyClass`` in the example above), and
        cause an error during type analysis.

        :param config_dict: JSON compliant dictionary encapsulating
            a configuration.
        :type config_dict: dict

        :param merge_default: Merge the given configuration on top of the
            default provided by ``get_default_config``.
        :type merge_default: bool

        :return: Constructed instance from the provided config.

        """
        # The simple case is that the class doesn't require any special
        # parameters other than those that can be provided via the JSON
        # specification, which we cover here. If an implementation needs
        # something more special, they can override this function.
        if merge_default:
            config_dict = merge_dict(cls.get_default_config(), config_dict)

        # A `type: ignore` is applied here as there is an error emitted due to
        # this abstract class not locally defining a constructor that takes
        # arguments. While locally valid, this is an abstract class that
        # sensibly does not define a constructor. This construction is intended
        # to apply dynamically to the sub-class that is being instantiated from
        # the input configuration dictionary. It is also technically valid for
        # keyword variadic expansion to be empty and be expanded into a
        # constructor that takes no parameters. Due to the reasons above, we
        # `type: ignore` this line.
        return cls(**config_dict)  # type: ignore

    @abc.abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """
        Return a JSON-compliant dictionary that could be passed to this class's
        ``from_config`` method to produce an instance with identical
        configuration.

        In the most cases, this involves naming the keys of the dictionary
        based on the initialization argument names as if it were to be passed
        to the constructor via dictionary expansion.  In some cases, where it
        doesn't make sense to store some object constructor parameters are
        expected to be supplied at as configuration values (i.e. must be
        supplied at runtime), this method's returned dictionary may leave those
        parameters out. In such cases, the object's ``from_config``
        class-method would also take additional positional arguments to fill in
        for the parameters that this returned configuration lacks.

        :return: JSON type compliant configuration dictionary.
        :rtype: dict

        """


def make_default_config(configurable_iter: Iterable[Type[C]]) -> Dict[str, Union[None, str, Dict]]:
    """
    Generated default configuration dictionary for the given iterable of
    Configurable-inheriting types.

    For example, assuming the following simple class that descends from
    ``Configurable``, we would expect the following behavior:

    >>> # noinspection PyAbstractClass
    >>> class ExampleConfigurableType (Configurable):
    ...     def __init__(self, a, b):
    ...        ''' Dummy constructor '''
    >>> make_default_config([ExampleConfigurableType]) == {
    ...     'type': None,
    ...     'smqtk_core.configuration.ExampleConfigurableType': {
    ...         'a': None,
    ...         'b': None,
    ...     }
    ... }
    True

    Note that technically ``ExampleConfigurableType`` is still abstract as it
    does not implement ``get_config``.  The above call to
    ``make_default_config`` still functions because we only use the
    ``get_default_config`` class method and do not instantiate any types given
    to this function.  While functionally acceptable, it is generally not
    recommended to draw configurations from abstract classes.

    The ``"type"`` returned is ``None`` because we explicitly do not make any
    decisions about an appropriate default type.
    Additionally, this value stays ``None`` even when there is just one choice
    as we do not assume that is a valid choice as well as do not assume that
    the default configuration for that choice is valid for construction.
    This serves to cause the user to explicitly check that the multiple-choice
    configuration is set to point to a choice as well as that the choice is
    properly configured.

    :param configurable_iter:
        An iterable of class types class types that sub-class ``Configurable``.

    :return: Base configuration dictionary with an empty ``type`` field, and
        containing the types and initialization parameter specification for all
        implementation types available from the provided getter method.
    """
    d: Dict[str, Union[None, str, Dict]] = {"type": None}
    for cls in configurable_iter:
        assert isinstance(cls, type) and issubclass(cls, Configurable), \
            "Encountered invalid Configurable type: '{}' (type={})".format(
                cls, type(cls)
            )
        d[_type_to_key(cls)] = cls.get_default_config()
    return d


def cls_conf_to_config_dict(cls: Type, conf: Dict) -> Dict:
    """
    Helper function for creating the appropriate "standard" smqtk configuration
    dictionary given a `Configurable`-implementing class and a configuration
    for that class.

    This very simple function simply arranges a semantic class key and an
    associated dictionary into a normal pattern used for configuration
    in SMQTK::

    >>> class SomeClass (object):
    ...     pass
    >>> cls_conf_to_config_dict(SomeClass, {0: 0, 'a': 'b'}) == {
    ...     'type': 'smqtk_core.configuration.SomeClass',
    ...     'smqtk_core.configuration.SomeClass': {0: 0, 'a': 'b'}
    ... }
    True

    :param type[Configurable] cls:
        A class type implementing the `Configurable` interface.

    :param dict conf:
        SMQTK standard type-optioned configuration dictionary for the given
        class and dictionary pair.

    :return: "Standard" SMQTK JSON-compliant configuration dictionary
    :rtype: dict

    """
    cls_key = _type_to_key(cls)
    return {
        "type": cls_key,
        cls_key: conf
    }


def to_config_dict(c_inst: Configurable) -> Dict:
    """
    Helper function that transforms the configuration dictionary retrieved from
    ``configurable_inst`` into the "standard" SMQTK configuration dictionary
    format (see above module documentation).

    For example, with a simple Configurable derived class:

    >>> class SimpleConfig(Configurable):
    ...     def __init__(self, a=1, b='foo'):
    ...         self.a = a
    ...         self.b = b
    ...     def get_config(self):
    ...         return {'a': self.a, 'b': self.b}
    >>> e = SimpleConfig(a=2, b="bar")
    >>> to_config_dict(e) == {
    ...     "type": "smqtk_core.configuration.SimpleConfig",
    ...     "smqtk_core.configuration.SimpleConfig": {
    ...         "a": 2,
    ...         "b": "bar"
    ...     }
    ... }
    True

    :param Configurable c_inst:
        Instance of a class type that subclasses the ``Configurable`` interface.

    :return: Standard format configuration dictionary.
    :rtype: dict

    """
    c_class = c_inst.__class__
    if isinstance(c_inst, type) or not issubclass(c_class, Configurable):
        raise ValueError("c_inst must be an instance and its type must "
                         "subclass from Configurable. Was given '{}'."
                         .format(type(c_inst)))
    return cls_conf_to_config_dict(c_class, c_inst.get_config())


def cls_conf_from_config_dict(
    config: Dict,
    type_iter: Iterable[Type[T]]
) -> Tuple[Type[T], Dict]:
    """
    Helper function for getting the appropriate type and configuration
    sub-dictionary based on the provided "standard" SMQTK configuration
    dictionary format (see above module documentation).

    :param config:
        Configuration dictionary to draw from.

    :param type_iter:
        An iterable of class types to select from.

    :raises ValueError:
        This may be raised if:
            - type field not present in ``config``.
            - type field set to ``None``
            - type field did not match any available configuration in the given
              config.
            - Type field did not specify any implementation key.

    :return: Appropriate class type from ``type_iter`` that matches the
        configured type as well as the sub-dictionary from the configuration.
        From this return, ``type.from_config(config)`` should be callable.
    """
    if 'type' not in config:
        raise ValueError("Configuration dictionary given does not have an "
                         "implementation type specification.")
    conf_type_name = config['type']
    type_map: Dict[str, Type[T]] = dict(map(lambda t: (_type_to_key(t), t), type_iter))

    conf_type_options = set(config.keys()) - {'type'}
    # Type provided may either by None, not have a matching block in the
    # config, not have a matching implementation type, or match both.
    if conf_type_name is None:
        raise ValueError("No implementation type specified. Options: %s"
                         % list(conf_type_options))
    elif conf_type_name not in conf_type_options:
        raise ValueError("Implementation type specified as '%s', but no "
                         "configuration block was present for that type. "
                         "Available configuration block options: %s"
                         % (conf_type_name, list(conf_type_options)))
    elif conf_type_name not in type_map:
        raise ValueError("Implementation type specified as '%s', but no "
                         "plugin implementations are available for that type. "
                         "Available implementation types options: %s"
                         % (conf_type_name, list(type_map)))
    cls = type_map[conf_type_name]
    return cls, config[conf_type_name]


def from_config_dict(config: Dict,
                     type_iter: Iterable[Type[C]],
                     *args: Any) -> C:
    """
    Helper function for instantiating an instance of a class given the
    configuration dictionary ``config`` from available types provided by
    ``type_iter`` via the ``Configurable`` interface's ``from_config``
    class-method.

    ``args`` are additionally positional arguments to be passed to the type's
    ``from_config`` method on return.

    Example:
    >>> class SimpleConfig(Configurable):
    ...     def __init__(self, a=1, b='foo'):
    ...         self.a = a
    ...         self.b = b
    ...     def get_config(self):
    ...         return {'a': self.a, 'b': self.b}
    >>> example_config = {
    ...     'type': 'smqtk_core.configuration.SimpleConfig',
    ...     'smqtk_core.configuration.SimpleConfig': {
    ...         "a": 3,
    ...         "b": "baz"
    ...     },
    ... }
    >>> inst = from_config_dict(example_config, {SimpleConfig})
    >>> isinstance(inst, SimpleConfig)
    True
    >>> inst.a == 3
    True
    >>> inst.b == "baz"
    True

    :raises ValueError:
        This may be raised if:
            - type field not present in ``config``.
            - type field set to ``None``
            - type field did not match any available configuration in the given
              config.
            - Type field did not specify any implementation key.
    :raises AssertionError:
        This may be raised if the class specified as the configuration `type`,
        is present in the given ``type_iter`` but is not a subclass of the
        ``Configurable`` interface.
    :raises TypeError: Insufficient/incorrect initialization parameters were
        specified for the specified ``type``'s constructor.

    :param config:
        Configuration dictionary to draw from.

    :param type_iter:
        An iterable of class types to select from.

    :param object args:
        Other positional arguments to pass to the configured class'
        ``from_config`` class method.

    :return: Instance of the configured class type as specified in ``config``
        and as available in ``type_iter``.

    """
    cls, cls_conf = cls_conf_from_config_dict(config, type_iter)
    assert issubclass(cls, Configurable), \
        "Configured class type '%s' does not descend from `Configurable`." \
        % cls.__name__
    return cls.from_config(cls_conf, *args)


def configuration_test_helper(inst: C,
                              config_ignored_params: Union[Set, FrozenSet] = frozenset(),
                              from_config_args: Sequence = ()) -> Tuple[C, C, C]:
    """
    Helper function for testing the get_default_config/from_config/get_config
    methods for class types that in part implement the Configurable mixin
    class.  This function also tests that ``inst``'s parent class type's
    ``get_default_config`` returns a dictionary whose keys' match the
    constructor's inspected parameters (except "self" of course).

    This constructs 3 additional instances based on the given instance
    following the pattern::

         inst-1  ->  inst-2  ->  inst-3
                 ->  inst-4

    This refers to ``inst-2`` and ``inst-4`` being constructed from the config
    from ``inst``, and ``inst-3`` being constructed from the config of
    ``inst-2``.  The equivalence of each instance's config is cross-checked
    with the other instances.  This is intended to check that a configuration
    yields the same class configurations and that the config does not get
    mutated by nested instance construction.

    This function uses assert calls to check for consistency.

    We return all instances constructed in case the caller wants to make
    additional instance integrity checks.

    :param Configurable inst:
        Configurable-mixin inheriting class to test.
    :param set[str] config_ignored_params:
        Set of parameter names in the instance type's constructor that are
        ignored by ``get_default_config`` and ``from_config``. This is empty
        by default.
    :param tuple from_config_args:
        Optional additional positional arguments to the input
        ``inst.from_config`` method after the configuration dictionary.
    :returns: Instance 2, 3, and 4 as described above.
    :rtype: (Configurable,Configurable,Configurable)
    """
    assert not isinstance(inst, type), "Passed a type, expected instance."
    inst_T: Type[C] = inst.__class__

    # Parent class default config keys should match constructor keys.
    dflt_cfg = inst_T.get_default_config()
    init_param_map = _param_map_func(inst_T.__init__)
    # Check that keys returned in default config is equivalent to parameters
    # requested by the constructor, minus explicitly provided parameter names
    # to disregard.
    # - Disregarded params are usually for when some arguments are also
    #   required by ``from_config``, i.e. runtime required.
    args_intersect = \
        set(dflt_cfg) == (set(init_param_map) - config_ignored_params)
    assert args_intersect, \
        "Default configuration dictionary keys does not match the class' " \
        "constructor parameter."
    del args_intersect
    # Should be JSON serializable.
    try:
        assert json.loads(json.dumps(dflt_cfg)) == dflt_cfg, \
            "Default config JSON Serialize -> Deserialize did not match " \
            "original config."
    except TypeError:
        # dumps error
        raise AssertionError("Failed to serialize default config return for "
                             "type {}.".format(inst_T.__name__))
    except ValueError:
        # loads error
        raise AssertionError("Failed to load serialized default config.")

    # Instance config / from_config construction cycle equivalence test.
    # - Checking that configurations are JSON serializable at each step.
    inst_config = inst.get_config()

    # Keys in default and instance configurations should also match.
    assert set(dflt_cfg) == set(inst_config)

    inst2 = inst_T.from_config(inst_config, *from_config_args)
    inst2_config = inst2.get_config()
    inst3 = inst_T.from_config(inst_config, *from_config_args)
    inst3_config = inst3.get_config()
    inst4 = inst_T.from_config(inst2_config, *from_config_args)
    inst4_config = inst4.get_config()
    assert inst_config == inst2_config
    assert inst_config == inst3_config
    assert inst2_config == inst3_config
    assert inst_config == inst4_config
    assert inst3_config == inst4_config

    return inst2, inst3, inst4
