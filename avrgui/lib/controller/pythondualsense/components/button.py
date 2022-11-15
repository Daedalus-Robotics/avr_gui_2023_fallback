from ..lib.callback import Callback


class Button:
    def __init__(self) -> None:
        self.on_press = Callback()
        """
        This will be called once when the button is pressed
        """
        self.on_state = Callback[bool]()
        """
        This will be called once when the button is pressed and again when the button is
        released. The current state of the button will be passed as an argument to the callback.
        """

        self._pressed = False

    @property
    def pressed(self) -> bool:
        """
        Get the pressed state of the button

        :return: The state of the button
        """
        return self._pressed

    @pressed.setter
    def pressed(self, state: bool) -> None:
        """
        Update the pressed state of the button.
        This is not meant to be used by anything outside this library!

        :param state: The new state of the button
        """
        if state is not self._pressed:
            self._pressed = state
            if self._pressed:
                self.on_press()
            self.on_state(self._pressed)
