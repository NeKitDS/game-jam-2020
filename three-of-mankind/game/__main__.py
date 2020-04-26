import logging

import arcade
from .gamestate import GameState
from .effects import VCRDistortionWindow

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
SCREEN_TITLE = "lemon is epic"

format_string = "%(asctime)s | %(filename)s#%(lineno)d | %(levelname)s | %(message)s"
logging.basicConfig(format=format_string, level=logging.DEBUG)


class Game(VCRDistortionWindow):
    """Main game object."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.ingame = False
        self.gamestate = None

    def on_update(self, delta_time: float) -> None:
        """Send update event to the gamestate."""
        if not self.ingame:  # Temporarily automatically start the game if it isn't running
            self.start_game()
        if self.gamestate:
            self.gamestate.on_update(delta_time)

        self.elapsed_time += delta_time

    def render(self) -> None:
        """Send draw event to the gamestate."""
        if self.gamestate:
            self.gamestate.on_draw()

    def on_key_press(self, symbol: int, modifiers: int):
        """Send keypress event to the gamestate."""
        if self.gamestate:
            self.gamestate.on_key_press(symbol, modifiers)

    def on_key_release(self, symbol: int, modifiers: int):
        """Send keyrelease event to the gamestate."""
        if self.gamestate:
            self.gamestate.on_key_release(symbol, modifiers)

    def start_game(self) -> None:
        self.ingame = True
        self.gamestate = GameState(game=self)


# Start game
game = Game(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, resizable=True)

try:
    arcade.run()
except KeyboardInterrupt:
    pass
