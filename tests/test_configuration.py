from typing import Any, Dict, Set, Type, TypeVar
import unittest.mock as mock

import pytest

from smqtk_core.configuration import (
    cls_conf_from_config_dict,
    cls_conf_to_config_dict,
    Configurable,
    make_default_config,
    to_config_dict,
    from_config_dict,
)


###############################################################################
# Helper classes for testing

class T1 (Configurable):

    def __init__(self, foo: int = 1, bar: str = 'baz') -> None:
        self.foo = foo
        self.bar = bar

    def get_config(self) -> Dict:
        return {
            'foo': self.foo,
            'bar': self.bar,
        }


D = TypeVar("D", bound="T2")


class T2 (Configurable):
    """
    Semi-standard way to implement nested algorithms.
    Usually, algorithms are associated to a plugin getter method that wraps a
    call to ``smqtk_core.plugin.get_plugins``, but I'm skipping that for now
    for simplicity.
    """

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        default = super(T2, cls).get_default_config()
        # Replace ``child``, which we know has a default value of type ``T1``
        # with its default config.
        default['child'] = default['child'].get_default_config()
        return default

    @classmethod
    def from_config(
        cls: Type[D],
        config: Dict,
        merge_default: bool = True
    ) -> D:
        config['child'] = T1.from_config(config['child'])
        return super().from_config(config, merge_default)

    def __init__(self, child: T1 = T1(), alpha: float = 0.0001,
                 beta: str = 'default') -> None:
        # Where child is supposed to be an instance of T1
        self.child = child
        self.alpha = alpha
        self.beta = beta

    def get_config(self) -> Dict[str, Any]:
        return {
            'child': self.child.get_config(),
            'alpha': self.alpha,
            'beta': self.beta
        }


# Set of "available" types for tests below.
T_CLASS_SET: Set[Type[Configurable]] = {T1, T2}


###############################################################################
# Tests

def test_configurable_default_config() -> None:
    """
    Test that constructor arguments are introspected automatically with None
    defaults.
    """
    # Only using class methods, thus noinspection.
    # noinspection PyAbstractClass
    class T (Configurable):
        # noinspection PyUnusedLocal
        def __init__(self, a: Any, b: Any, cat: Any):
            """ empty constructor """

    assert T.get_default_config() == {'a': None, 'b': None, 'cat': None}


def test_configurable_default_config_kwonlys() -> None:
    """
    Test properly getting constructor defaults when there are keyword-only
    arguments present (presence of the `*` in the parameter list).
    """
    # Only using class methods, thus noinspection.
    # noinspection PyAbstractClass
    class T (Configurable):
        # noinspection PyUnusedLocal
        def __init__(self, a: Any, *, b: int = 0):
            """ empty constructor """

    assert T.get_default_config() == dict(a=None, b=0)


def test_configurable_default_config_no_init() -> None:
    """
    Test that an empty dictionary is returned when a class has no ``__init__``
    defined.
    """
    # noinspection PyAbstractClass
    # - for testing a class method, don't need to instantiate.
    class NoInitExample (Configurable):
        pass

    assert NoInitExample.get_default_config() == {}


def test_configurable_default_config_with_star_args() -> None:
    """
    Test that star-stuff shouldn't change anything
    """
    # Only using class methods, thus noinspection.
    # noinspection PyAbstractClass
    class T (Configurable):
        # noinspection PyUnusedLocal
        def __init__(self, a: Any, b: Any, cat: Any, *args: Any, **kwargs: Any):
            """ empty constructor """

    assert T.get_default_config() == {'a': None, 'b': None, 'cat': None}


def test_configurable_default_config_with_default_values() -> None:
    """
    Test that default values are correctly introspected.
    """
    # Only using class methods, thus noinspection.
    # noinspection PyAbstractClass
    class T (Configurable):
        # noinspection PyUnusedLocal
        def __init__(self, a: Any, b: Any, c: int = 0, d: str = 'foobar'):
            """ empty constructor """

    assert T.get_default_config() == \
        {'a': None, 'b': None, 'c': 0, 'd': 'foobar'}


def test_configurable_default_config_with_default_values_with_star_args() -> None:
    """
    Test that star stuff shouldn't change anything when there are default
    values.
    """
    # Only using class methods, thus noinspection.
    # noinspection PyAbstractClass
    class T (Configurable):
        # noinspection PyUnusedLocal
        def __init__(self, a: Any, b: Any, c: int = 0, d: str = 'foobar',
                     *args: Any, **kwargs: Any):
            """ empty constructor """

    assert T.get_default_config() == \
        {'a': None, 'b': None, 'c': 0, 'd': 'foobar'}


def test_configurable_classmethod_override_getdefaultconfig() -> None:
    """
    Test overriding the class method get_default_config
    """
    assert T1.get_default_config() == {'foo': 1, 'bar': 'baz'}
    assert T2.get_default_config() == {
        'child': {'foo': 1, 'bar': 'baz'},
        'alpha': 0.0001,
        'beta': 'default'
    }


def test_make_default_config() -> None:
    """
    Test expected normal operation of ``make_default_config``.
    """
    expected = {
        'type': None,
        'tests.test_configuration.T1': T1.get_default_config(),
        'tests.test_configuration.T2': T2.get_default_config(),
    }
    assert make_default_config(T_CLASS_SET) == expected


def test_cls_conf_to_config_dict() -> None:
    """
    Test that ``to_config_dict`` correctly reflects the contents of the config
    return from the instance passed to it.
    """
    conf1 = {
        'foo': 1,
        'bar': 'baz',
    }
    c1 = cls_conf_to_config_dict(T1, conf1)
    expected1 = {
        'type': 'tests.test_configuration.T1',
        'tests.test_configuration.T1': {
            'foo': 1,
            'bar': 'baz',
        },
    }
    assert c1 == expected1

    # return should update with updates to
    conf2 = {
        'foo': 8,
        'bar': 'baz',
    }
    c2 = cls_conf_to_config_dict(T1, conf2)
    expected2 = {
        'type': 'tests.test_configuration.T1',
        'tests.test_configuration.T1': {
            'foo': 8,
            'bar': 'baz',
        },
    }
    assert c2 == expected2


def test_to_config_dict() -> None:
    """
    Test that the second-level helper function is called appropriately and
    directly returns.
    """
    # We will mock out the return of `cls_conf_to_config_dict` operation as
    # that is tested elsewhere. We more want to make sure the input to this
    # internal function is as expected.
    expected_ret_val = 'expected return value'

    with mock.patch('smqtk_core.configuration.cls_conf_to_config_dict') \
            as m_cctcd:
        m_cctcd.return_value = expected_ret_val

        i1 = T1()
        i1_expected_conf = {
            'foo': 1,
            'bar': 'baz',
        }
        r1 = to_config_dict(i1)
        m_cctcd.assert_called_once_with(T1, i1_expected_conf)
        assert r1 == expected_ret_val

    with mock.patch('smqtk_core.configuration.cls_conf_to_config_dict') \
            as m_cctcd:
        m_cctcd.return_value = expected_ret_val

        i2 = T1(foo=8)
        i2_expected_conf = {
            'foo': 8,
            'bar': 'baz',
        }
        r2 = to_config_dict(i2)
        m_cctcd.assert_called_once_with(T1, i2_expected_conf)
        assert r2 == expected_ret_val

    with mock.patch('smqtk_core.configuration.cls_conf_to_config_dict') \
            as m_cctcd:
        m_cctcd.return_value = expected_ret_val

        i3 = T2(T1(foo=12, bar='OK'), 0.3, 'not default')
        i3_expected_conf = {
            'child': {
                "foo": 12,
                "bar": "OK",
            },
            "alpha": 0.3,
            "beta": "not default",
        }
        r3 = to_config_dict(i3)
        m_cctcd.assert_called_once_with(T2, i3_expected_conf)
        assert r3 == expected_ret_val


def test_to_config_dict_given_type() -> None:
    """
    Test that ``to_config_dict`` errors when passed a type.
    """
    # Just with `object`.
    with pytest.raises(ValueError,
                       match="c_inst must be an instance and its type must "
                             r"subclass from Configurable\."):
        # noinspection PyTypeChecker
        to_config_dict(object)  # type: ignore

    # Literally the Configurable interface (abstract class)
    with pytest.raises(ValueError,
                       match="c_inst must be an instance and its type must "
                             r"subclass from Configurable\."):
        # noinspection PyTypeChecker
        to_config_dict(Configurable)  # type: ignore

    # New sub-class implementing Configurable, but passed as the type not an
    # instance.
    class SomeConfigurableType (Configurable):
        def get_config(self) -> Dict[str, Any]: ...

    with pytest.raises(ValueError):
        # noinspection PyTypeChecker
        to_config_dict(SomeConfigurableType)  # type: ignore


def test_to_config_dict_given_non_configurable() -> None:
    """
    Test that ``to_config_dict`` errors when passed an instance that does not
    descend from configurable.
    """
    class SomeOtherClassType (object):
        pass

    inst = SomeOtherClassType()
    with pytest.raises(ValueError,
                       match="c_inst must be an instance and its type must "
                             r"subclass from Configurable\."):
        # noinspection PyTypeChecker
        to_config_dict(inst)  # type: ignore


def test_cls_conf_from_config_dict() -> None:
    """
    Test that ``cls_conf_from_config_dict`` returns the correct type and
    sub-configuration requested.
    """
    test_config = {
        'type': 'tests.test_configuration.T1',
        'tests.test_configuration.T1': {
            'foo': 256,
            'bar': 'Some string value'
        },
        'tests.test_configuration.T2': {
            'child': {'foo': -1, 'bar': 'some other value'},
            'alpha': 1.0,
            'beta': 'euclidean',
        },
        'NotAnImpl': {}
    }
    cls, cls_conf = cls_conf_from_config_dict(test_config, T_CLASS_SET)
    assert cls == T1
    assert cls_conf == {'foo': 256, 'bar': 'Some string value'}

    test_config['type'] = 'tests.test_configuration.T2'
    cls, cls_conf = cls_conf_from_config_dict(test_config, T_CLASS_SET)
    assert cls == T2
    assert cls_conf == {
        'child': {'foo': -1, 'bar': 'some other value'},
        'alpha': 1.0,
        'beta': 'euclidean',
    }


def test_cls_conf_from_config_missing_type() -> None:
    """
    Test that ``from_config_dict`` throws an exception when no 'type' key is
    present.
    """
    test_config = {
        'T1': {'foo': 256, 'bar': 'Some string value'},
        'T2': {
            'child': {'foo': -1, 'bar': 'some other value'},
            'alpha': 1.0,
            'beta': 'euclidean',
        },
        'NotAnImpl': {}
    }
    with pytest.raises(ValueError,
                       match="Configuration dictionary given does not have an "
                             r"implementation type specification\."):
        cls_conf_from_config_dict(test_config, T_CLASS_SET)


def test_cls_conf_from_config_none_type() -> None:
    """
    Test that appropriate exception is raised when `type` key is None valued.
    """
    test_config: Dict[str, Any] = {
        'type': None,
        'T1': {'foo': 256, 'bar': 'Some string value'},
        'T2': {
            'child': {'foo': -1, 'bar': 'some other value'},
            'alpha': 1.0,
            'beta': 'euclidean',
        },
        'NotAnImpl': {}
    }
    with pytest.raises(ValueError, match=r"No implementation type specified\. "
                                         r"Options: \[.*\]"):
        cls_conf_from_config_dict(test_config, T_CLASS_SET)


def test_cls_conf_from_config_config_label_mismatch() -> None:
    test_config = {
        'type': 'not-present-label',
        'T1': {'foo': 256, 'bar': 'Some string value'},
        'T2': {
            'child': {'foo': -1, 'bar': 'some other value'},
            'alpha': 1.0,
            'beta': 'euclidean',
        },
        'NotAnImpl': {}
    }
    with pytest.raises(ValueError,
                       match="Implementation type specified as 'not-present-"
                             "label', but no configuration block was present "
                             r"for that type\. Available configuration block "
                             r"options: \[.*\]"):
        cls_conf_from_config_dict(test_config, T_CLASS_SET)


def test_cls_conf_from_config_impl_label_mismatch() -> None:
    test_config = {
        'type': 'NotAnImpl',
        'T1': {'foo': 256, 'bar': 'Some string value'},
        'T2': {
            'child': {'foo': -1, 'bar': 'some other value'},
            'alpha': 1.0,
            'beta': 'euclidean',
        },
        'NotAnImpl': {}
    }
    with pytest.raises(ValueError,
                       match="Implementation type specified as 'NotAnImpl', "
                             "but no plugin implementations are available for "
                             "that type. Available implementation types "
                             r"options: \[.*\]"):
        cls_conf_from_config_dict(test_config, T_CLASS_SET)


def test_from_config_dict() -> None:
    """
    Test that ``from_config_dict`` correctly creates an instance of the class
    requested by the configuration.
    """
    test_config = {
        'type': 'tests.test_configuration.T1',
        'tests.test_configuration.T1': {
            'foo': 256,
            'bar': 'Some string value'
        },
        'tests.test_configuration.T2': {
            'child': {'foo': -1, 'bar': 'some other value'},
            'alpha': 1.0,
            'beta': 'euclidean',
        },
        'NotAnImpl': {}
    }

    #: :type: DummyAlgo1
    i = from_config_dict(test_config, T_CLASS_SET)
    assert isinstance(i, T1)
    assert i.foo == 256
    assert i.bar == "Some string value"

    # Test other type instantiation
    test_config['type'] = 'tests.test_configuration.T2'
    i = from_config_dict(test_config, T_CLASS_SET)
    assert isinstance(i, T2)
    assert isinstance(i.child, T1)
    assert i.child.foo == -1
    assert i.child.bar == "some other value"
    assert i.alpha == 1.0
    assert i.beta == "euclidean"


def test_from_config_dict_assertion_error() -> None:
    """
    Test that assertion error is raised when a class is provided AND specified
    that does not descend from the Configurable interface.
    """
    class NotConfigurable (object):
        """ Not a configurable class. """

    test_class_set = T_CLASS_SET | {NotConfigurable}

    test_config: Dict[str, Any] = {
        'type': 'tests.test_configuration.NotConfigurable',
        'tests.test_configuration.T1': {
            'foo': 256,
            'bar': 'Some string value'
        },
        'tests.test_configuration.T2': {
            'child': {'foo': -1, 'bar': 'some other value'},
            'alpha': 1.0,
            'beta': 'euclidean',
        },
        'tests.test_configuration.NotConfigurable': {}
    }
    with pytest.raises(AssertionError,
                       match="Configured class type 'NotConfigurable' does not "
                             r"descend from `Configurable`\."):
        from_config_dict(test_config, test_class_set)  # type: ignore
