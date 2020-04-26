import logging

import arcade

from PIL import Image

from .constants import (
    AIR_CONTROL,
    BLOCK_LEN,
    DASH_COUNT,
    DASH_DISTANCE,
    GRAVITY,
    GROUND_CONTROL,
    JUMP_COUNT,
    JUMP_FORCE,
    JUMP_VELOCITY_BONUS,
    LEFT,
    PLAYER_MOVEMENT_SPEED,
    RIGHT,
    TEXTURE_SIZE,
    VIEWPORT_MARGIN,
)
from .player import Player
from .sprite import Sprite
from .tile_image import tiles
from .utils import dash_emitter_factory, is_touching, sweep_trace


class GameState:
    """Represent the state of the current game, and manage it."""

    def __init__(self, game):
        self.view_left = 0
        self.view_bottom = 0
        self.game = game
        self.level = 0

        self.level_geometry = arcade.SpriteList()  # Have collisions
        self.level_objects = arcade.SpriteList()  # Doesn't have collision
        self.colored_geometry = {
            "red": arcade.SpriteList(),
            "green": arcade.SpriteList(),
            "blue": arcade.SpriteList(),
            "white": arcade.SpriteList(),
        }

        self.player = Player(scale=0.99)
        for tile in (
            tiles.player_white,
            tiles.player_red,
            tiles.player_green,
            tiles.player_blue,
        ):
            self.player.append_texture(tile.texture)
        self.player.set_texture(0)

        self.player.center_x = 200
        self.player.center_y = 200

        self.load_level(self.level)

        self.engine = arcade.PhysicsEnginePlatformer(
            self.player, self.level_geometry, GRAVITY
        )

        self.dash_emitters = []

    def load_level(self, level_id: int) -> bool:
        try:
            image = Image.open(f"levels/level_{level_id}.png")
        except OSError:
            return False

        self.level_objects = arcade.SpriteList()
        self.level_geometry = arcade.SpriteList()
        self.danger = arcade.SpriteList()
        self.saves = arcade.SpriteList()
        self.start, self.end = None, None
        self.colored_geometry = {
            "red": arcade.SpriteList(),
            "green": arcade.SpriteList(),
            "blue": arcade.SpriteList(),
            "white": arcade.SpriteList(),
        }

        w, h = image.size
        pixels = image.load()

        color_map = {
            0xFFFFFFFF: "W",
            0xFF0000FF: "R",
            0x00FF00FF: "G",
            0x0000FFFF: "B",
            0x00FFFFFF: "L",
            0xFF00FFFF: "P",
            0x000000FF: "D",
            0x00000000: "E",
        }

        def to_int(r: int, g: int, b: int, a: int) -> int:
            return (r << 24) + (g << 16) + (b << 8) + a

        def gen_colors():
            for yi in range(y - 2, y + 1):
                for xi in range(x, x + 3):
                    yield color_map.get(to_int(*pixels[xi, yi]), "E")

        left, bottom = 0, 0

        for y in range(h - 1, -1, -3):
            for x in range(0, w, 3):
                colors = "".join(gen_colors())

                try:
                    tile = tiles[colors]

                except KeyError:
                    pass

                else:
                    sprite = Sprite.from_texture(tile.texture)

                    sprite.left, sprite.bottom = left, bottom

                    if tile.name.startswith(("block", "danger")):
                        self.level_geometry.append(sprite)

                    else:
                        self.level_objects.append(sprite)

                    if tile.name.endswith(("white", "red", "green", "blue")):
                        self.colored_geometry[tile.name.rsplit("_", 1)[-1]].append(sprite)

                    if tile.name.startswith("save"):
                        self.saves.append(sprite)

                    if tile.name.startswith("danger"):
                        self.danger.append(sprite)

                    if tile.name.startswith("level"):
                        if tile.name.endswith("start"):
                            self.start = sprite
                        else:
                            self.end = sprite

                left += TEXTURE_SIZE

            left = 0
            bottom += TEXTURE_SIZE

        if not self.start:
            raise RuntimeError("Start is not set.")
        elif not self.end:
            raise RuntimeError("End is not set.")

        self.move_to_start()

        return True

    def move_to_start(self) -> None:
        self.player.left, self.player.bottom = self.start.left, self.start.bottom

    def on_update(self, delta_time: float) -> None:
        """Handle update event."""
        if self.engine.can_jump():
            self.player.movement_control = GROUND_CONTROL
        else:
            self.player.movement_control = AIR_CONTROL

        if self.player.collides_with_sprite(self.end):
            self.level += 1
            if self.load_level(self.level):
                logging.info("NEXT LEVEL")
            else:
                logging.info("LAST LEVEL")

        saves = self.player.collides_with_list(self.saves)

        if saves:
            self.start = saves.pop()

        if is_touching(self.player, self.danger):
            self.move_to_start()

        colors = {"red", "green", "blue"}
        colors.discard(self.player.str_color)
        for color in colors:
            if is_touching(self.player, self.colored_geometry[color]):
                self.move_to_start()

        self.player.update()
        self.engine.update()
        self.level_objects.update()

        self.update_screen()

    def on_draw(self) -> None:
        """Handle draw event."""
        arcade.start_render()
        self.level_geometry.draw()
        self.level_objects.draw()
        self.player.draw()
        for emitter in self.dash_emitters:
            emitter.draw()
        self.player.draw()
        self.level_geometry.draw()
        self.level_objects.draw()

    def on_key_press(self, key, modifiers):
        """Called whenever a key is pressed."""
        # Change color
        colors = {
            arcade.key.F: "white",
            arcade.key.R: "red",
            arcade.key.G: "green",
            arcade.key.B: "blue",
        }
        if key == arcade.key.E:
            all_colors = ("white", "red", "green", "blue")
            self.player.set_color(
                all_colors[(all_colors.index(self.player.str_color) + 1) % len(all_colors)]
            )
        if key in colors:
            self.player.set_color(colors[key])

        # Pre
        if self.engine.can_jump():
            self.player.dash_count = 0
            self.player.jump_count = 0

        # Dashing
        if key == arcade.key.LSHIFT:
            if not sweep_trace(self.player, DASH_DISTANCE, 0, self.level_geometry):
                can_dash = True

                if not self.engine.can_jump():
                    if self.player.dash_count < DASH_COUNT:
                        self.player.dash_count += 1

                    else:
                        can_dash = False

                if can_dash:
                    self.player.left += DASH_DISTANCE * self.player.direction
                    old_pos = self.player.center_x, self.player.center_y
                    # make player dash
                    self.player.left += DASH_DISTANCE * self.player.direction
                    # create a particle emitter
                    new_pos = self.player.center_x, self.player.center_y
                    self.dash_emitters.extend(
                        dash_emitter_factory(self.player.color, old_pos, new_pos)
                    )

        # Jumping
        if key == arcade.key.SPACE:
            self.player.jump_count += 1
            if self.player.jump_count <= JUMP_COUNT:
                self.player.change_y = 0
                self.player.is_jumping = True
                self.player.jump_force = (
                    JUMP_FORCE + abs(self.player.velocity[0]) * JUMP_VELOCITY_BONUS
                )

        # Moving
        if key == arcade.key.LEFT or key == arcade.key.A:
            self.player.movement_x = -PLAYER_MOVEMENT_SPEED
            self.player.direction = LEFT
        if key == arcade.key.RIGHT or key == arcade.key.D:
            self.player.movement_x = PLAYER_MOVEMENT_SPEED
            self.player.direction = RIGHT

    def on_key_release(self, key, modifiers):
        """Called when the user releases a key."""
        # Jumping
        if key == arcade.key.SPACE:
            self.player.is_jumping = False

        # Moving
        if key == arcade.key.LEFT or key == arcade.key.A:
            if self.player.movement_x < 0:
                self.player.movement_x = 0
        elif key == arcade.key.RIGHT or key == arcade.key.D:
            if self.player.movement_x > 0:
                self.player.movement_x = 0

    def update_screen(self):
        """Update viewport and scroll camera.

        From https://arcade.academy/examples/sprite_move_scrolling.html#sprite-move-scrolling"""
        # Keep track of if we changed the boundary. We don't want to call the
        # set_viewport command if we didn't change the view port.
        changed = False

        # Scroll left
        left_boundary = self.view_left + VIEWPORT_MARGIN
        if self.player.left < left_boundary:
            self.view_left -= left_boundary - self.player.left
            changed = True

        # Scroll right
        right_boundary = self.view_left + self.game.width - VIEWPORT_MARGIN
        if self.player.right > right_boundary:
            self.view_left += self.player.right - right_boundary
            changed = True

        # Scroll up
        top_boundary = self.view_bottom + self.game.height - VIEWPORT_MARGIN
        if self.player.top > top_boundary:
            self.view_bottom += self.player.top - top_boundary
            changed = True

        # Scroll down
        bottom_boundary = self.view_bottom + VIEWPORT_MARGIN
        if self.player.bottom < bottom_boundary:
            self.view_bottom -= bottom_boundary - self.player.bottom
            changed = True

        # Make sure our boundaries are integer values. While the view port does
        # support floating point numbers, for this application we want every pixel
        # in the view port to map directly onto a pixel on the screen. We don't want
        # any rounding errors.
        self.view_left = int(self.view_left)
        self.view_bottom = int(self.view_bottom)

        # If we changed the boundary values, update the view port to match
        if changed:
            arcade.set_viewport(
                self.view_left,
                self.game.width + self.view_left,
                self.view_bottom,
                self.game.height + self.view_bottom,
            )
