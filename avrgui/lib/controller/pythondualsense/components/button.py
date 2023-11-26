import asyncio

from ..lib.callback import Callback


class Button:
    def __init__(self, event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()) -> None:
        self.on_press = Callback(event_loop)
        """
        This will be called once when the button is pressed
        """
        self.on_state = Callback[bool]()
        """
        This will be called once when the button is pressed and again when the button is
        released. The current state of the button will be passed as an argument to the callback.
        """

        self._pressed = False

    def __bool__(self) -> bool:
        return self._pressed

    def __repr__(self) -> str:
        return f"Button: {self._pressed}"

    @property
    def pressed(self) -> bool:
        """
        Get the pressed state of the button

        :return: The state of the button
        """
        return self._pressed

    def update(self, state: bool) -> None:
        """
        Update the state of the button using the state from the controller.
        This is an internal method!

        :param state: The state of the button.
        """
        if state is not self._pressed:
            self._pressed = state
            if state:
                self.on_press()
            self.on_state(state)
