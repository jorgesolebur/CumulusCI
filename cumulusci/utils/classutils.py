from typing import Any, Dict, Set, Type


def get_all_subclasses(cls: Type[Any]) -> Set[Type[Any]]:
    """Return all subclasses of the given class"""
    return set(cls.__subclasses__()).union(
        [s for c in cls.__subclasses__() for s in get_all_subclasses(c)]
    )


def namedtuple_as_simple_dict(self: Any) -> Dict[str, Any]:
    return {name: getattr(self, name, None) for name in self.__class__._fields}
