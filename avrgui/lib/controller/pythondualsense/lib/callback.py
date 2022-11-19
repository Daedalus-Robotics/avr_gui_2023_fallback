from typing import (
    Callable,
    Generic,
    TypeVar
)

ArgumentType = TypeVar('ArgumentType')


class Callback(Generic[ArgumentType]):
    def __init__(self) -> None:
        """
        Create a new Callback object
        """
        self._callback_list: list[Callable[[], None] | Callable[[ArgumentType], None]] = []

    def __call__(self, argument: ArgumentType = None) -> None:
        """
        Call all callables that have been registered

        :param argument: The argument pass to the callbacks, if set to None this won't pass an argument
        """
        for callback in self._callback_list:
            try:
                # Call with an argument if one is given
                if argument is not None:
                    callback(argument)
                else:
                    callback()
            except TypeError as e:
                print(e)

    def register(self, callback: Callable[[], None] | Callable[[ArgumentType], None]) -> None:
        """
        Register a callable to be called when this callback is called

        :param callback: The callable to be registered
        """
        self._callback_list.append(callback)

    def unregister(self, callback: Callable) -> None:
        """
        Unregister a callable

        :param callback: The callable to be unregistered
        """
        if callback in self._callback_list:
            self._callback_list.remove(callback)

    def __iadd__(self, other: Callable[[], None] | Callable[[ArgumentType], None]) -> None:
        if isinstance(other, Callable):
            self.register(other)

    def __isub__(self, other: Callable) -> None:
        if isinstance(other, Callable):
            self.unregister(other)
