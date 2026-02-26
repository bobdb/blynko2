# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Game

```bash
pip install -r requirements.txt
python plinko.py
```

## Architecture

All game logic lives in a single file, `plinko.py`, organized as one class `PlinkoGame` with clear method groupings:

- **Space setup** (`_setup_walls`, `_setup_buckets`, `_setup_collision_handlers`): Creates pymunk physics bodies. Buckets use invisible sensor shapes (`collision_type=2`) to detect scoring. The ball uses `collision_type=1`.
- **Peg/Ball management** (`add_peg`, `remove_nearest_peg`, `drop_ball`, `reset_ball`): Adds/removes pymunk bodies from `self.space`.
- **Event handling** (`handle_events`, `_handle_sidebar_click`): Keyboard and mouse input. Sidebar clicks are routed separately from game board clicks using `SIDEBAR_X` as the boundary.
- **Physics update** (`update`): Steps `self.space` with `SUBSTEPS=3` substeps per frame for stability. Removes ball if it falls off-screen.
- **Rendering** (`draw` and `_draw_*` methods): Pure drawing — no state mutation here.

## Coordinate System

Pymunk uses a **bottom-left origin** (y increases upward), while Pygame uses **top-left origin** (y increases downward). Conversions go through `pymunk.pygame_util.from_pygame()` / `to_pygame()` everywhere positions cross the boundary. This is a common source of bugs when adding new physics objects.

## Settings Controls

The sidebar settings (elasticity, gravity, damping, ball radius) are driven by the `self.settings_controls` list of dicts. Each dict has `attr`, `min`, `max`, `step`, and pre-computed `rect_dec`/`rect_inc` `pygame.Rect` objects. Adding a new setting means adding a new dict to this list with the correct Y coordinates.

- Settings marked `"sublabel": "live"` apply immediately to `self.space` on click.
- Settings marked `"sublabel": "next ball"` take effect on the next `drop_ball()` call.

## Key Constants

| Constant | Value | Purpose |
|---|---|---|
| `WIDTH` / `HEIGHT` | 800 / 700 | Game board area |
| `SIDEBAR_WIDTH` | 240 | Right sidebar |
| `DROP_ZONE_HEIGHT` | 80 | Top bar where balls drop |
| `BUCKET_HEIGHT` | 80 | Bottom scoring area |
| `SUBSTEPS` | 3 | Physics substeps per frame (increase for accuracy) |
