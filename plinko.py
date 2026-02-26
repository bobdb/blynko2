import sys
import math
import pygame
import pymunk
import pymunk.pygame_util

# ── Constants ────────────────────────────────────────────────────────────────
WIDTH, HEIGHT = 800, 700
DROP_ZONE_HEIGHT = 80
BUCKET_HEIGHT = 80
PEG_AREA_TOP = DROP_ZONE_HEIGHT
PEG_AREA_BOTTOM = HEIGHT - BUCKET_HEIGHT  # y=620

PEG_RADIUS = 8
BALL_RADIUS = 12
BALL_MASS = 3
NUM_BUCKETS = 7
BUCKET_SCORES = [50, 100, 200, 500, 200, 100, 50]

GRAVITY = (0, 900)
DAMPING = 0.99
FPS = 60
SUBSTEPS = 3

# ── Colours ───────────────────────────────────────────────────────────────────
BG_COLOR        = (26,  26,  46)   # #1a1a2e  dark navy
DROP_ZONE_COLOR = (35,  35,  60)
PEG_COLOR       = (220, 220, 220)
PEG_GLOW_COLOR  = (180, 180, 255, 80)
BALL_COLOR      = (255, 215,   0)  # gold-yellow
WALL_COLOR      = (80,  80, 120)
DIVIDER_COLOR   = (200, 200, 200)
BUCKET_LABEL_COLOR  = (200, 200, 200)
BUCKET_HIT_COLOR    = (255, 200,   0)
SCORE_TEXT_COLOR    = (255, 230,  80)
UI_TEXT_COLOR       = (180, 180, 220)


# ─────────────────────────────────────────────────────────────────────────────
class PlinkoGame:

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Plinko")
        self.clock = pygame.time.Clock()

        self.font_large  = pygame.font.SysFont("Arial", 42, bold=True)
        self.font_medium = pygame.font.SysFont("Arial", 22, bold=True)
        self.font_small  = pygame.font.SysFont("Arial", 16)

        # pymunk space
        self.space = pymunk.Space()
        self.space.gravity = GRAVITY
        self.space.damping = DAMPING

        # game state
        self.pegs: list[tuple[pymunk.Body, pymunk.Shape]] = []
        self.ball_body:  pymunk.Body  | None = None
        self.ball_shape: pymunk.Shape | None = None
        self.score:          int | None = None
        self.scored_bucket:  int | None = None

        self._setup_walls()
        self._setup_buckets()
        self._setup_collision_handlers()

    # ── Space setup ───────────────────────────────────────────────────────────

    def _setup_walls(self):
        sb = self.space.static_body
        walls = [
            pymunk.Segment(sb, (0, 0), (0, HEIGHT), 2),
            pymunk.Segment(sb, (WIDTH, 0), (WIDTH, HEIGHT), 2),
        ]
        for w in walls:
            w.elasticity = 0.6
            w.friction   = 0.5
        self.space.add(*walls)

    def _setup_buckets(self):
        sb = self.space.static_body
        bucket_w = WIDTH / NUM_BUCKETS  # ~114.3 px each

        # Vertical dividers — 6 lines between 7 buckets
        self.divider_x: list[float] = []
        for i in range(1, NUM_BUCKETS):
            x = i * bucket_w
            self.divider_x.append(x)
            # pymunk coords: bottom of screen = y=0, top = y=HEIGHT
            seg = pymunk.Segment(
                sb,
                (x, 0),
                (x, BUCKET_HEIGHT),
                2,
            )
            seg.elasticity = 0.5
            seg.friction    = 0.8
            self.space.add(seg)

        # Invisible bucket sensors
        self.bucket_sensors: list[pymunk.Shape] = []
        for i in range(NUM_BUCKETS):
            x_left  = i * bucket_w
            x_right = (i + 1) * bucket_w
            x_center = (x_left + x_right) / 2
            # sensor box: spans full bucket width, bottom 80 px
            body  = pymunk.Body(body_type=pymunk.Body.STATIC)
            shape = pymunk.Poly.create_box_bb(
                body,
                pymunk.BB(x_left + 2, 0, x_right - 2, BUCKET_HEIGHT - 2),
            )
            shape.sensor         = True
            shape.collision_type = 2
            shape.bucket_index   = i          # custom attribute
            self.space.add(body, shape)
            self.bucket_sensors.append(shape)

    def _setup_collision_handlers(self):
        def begin(arbiter, space, data):
            for shape in arbiter.shapes:
                if shape.collision_type == 2:
                    idx = shape.bucket_index
                    if self.scored_bucket is None:   # record only first hit
                        self.scored_bucket = idx
                        self.score = BUCKET_SCORES[idx]

        self.space.on_collision(1, 2, begin=begin)

    # ── Peg management ────────────────────────────────────────────────────────

    def add_peg(self, pygame_pos: tuple[int, int]):
        px, py = pygame_pos
        # clamp strictly inside peg area
        if not (PEG_AREA_TOP + PEG_RADIUS < py < PEG_AREA_BOTTOM - PEG_RADIUS):
            return
        if not (PEG_RADIUS < px < WIDTH - PEG_RADIUS):
            return
        pm_pos = pymunk.pygame_util.from_pygame(pygame_pos, self.screen)
        body  = pymunk.Body(body_type=pymunk.Body.STATIC)
        body.position = pm_pos
        shape = pymunk.Circle(body, PEG_RADIUS)
        shape.elasticity = 0.8
        shape.friction    = 0.5
        self.space.add(body, shape)
        self.pegs.append((body, shape))

    def remove_nearest_peg(self, pygame_pos: tuple[int, int]):
        if not self.pegs:
            return
        px, py = pygame_pos
        best_dist = float("inf")
        best_idx  = -1
        for i, (body, _) in enumerate(self.pegs):
            bpx, bpy = pymunk.pygame_util.to_pygame(body.position, self.screen)
            d = math.hypot(px - bpx, py - bpy)
            if d < best_dist:
                best_dist = d
                best_idx  = i
        if best_dist <= 30:
            body, shape = self.pegs.pop(best_idx)
            self.space.remove(body, shape)

    # ── Ball management ───────────────────────────────────────────────────────

    def drop_ball(self, x_pygame: int):
        self.reset_ball()
        # Drop from y=60 in pygame → near top of screen
        pygame_pos = (x_pygame, DROP_ZONE_HEIGHT // 2 + 10)
        pm_pos = pymunk.pygame_util.from_pygame(pygame_pos, self.screen)

        moment = pymunk.moment_for_circle(BALL_MASS, 0, BALL_RADIUS)
        body   = pymunk.Body(BALL_MASS, moment)
        body.position = pm_pos
        shape = pymunk.Circle(body, BALL_RADIUS)
        shape.elasticity     = 0.75
        shape.friction        = 0.4
        shape.collision_type  = 1
        self.space.add(body, shape)
        self.ball_body  = body
        self.ball_shape = shape

    def reset_ball(self):
        if self.ball_body is not None:
            self.space.remove(self.ball_body, self.ball_shape)
            self.ball_body  = None
            self.ball_shape = None
        self.score         = None
        self.scored_bucket = None

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if event.button == 1:  # left-click
                    if my < DROP_ZONE_HEIGHT:
                        self.drop_ball(mx)
                    else:
                        self.add_peg(event.pos)
                elif event.button == 3:  # right-click
                    self.remove_nearest_peg(event.pos)

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.drop_ball(WIDTH // 2)
                elif event.key == pygame.K_r:
                    self.reset_ball()
                elif event.key == pygame.K_c:
                    for body, shape in self.pegs:
                        self.space.remove(body, shape)
                    self.pegs.clear()
                elif event.key == pygame.K_ESCAPE:
                    return False

        return True

    # ── Physics update ────────────────────────────────────────────────────────

    def update(self, dt: float):
        sub_dt = dt / SUBSTEPS
        for _ in range(SUBSTEPS):
            self.space.step(sub_dt)

        # Remove ball if it falls below bottom of screen
        if self.ball_body is not None:
            bx, by = pymunk.pygame_util.to_pygame(self.ball_body.position, self.screen)
            if by > HEIGHT + 50:
                self.reset_ball()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def draw(self):
        self.screen.fill(BG_COLOR)
        self._draw_drop_zone()
        self._draw_pegs()
        self._draw_ball()
        self._draw_bucket_area()
        self._draw_ui()
        pygame.display.flip()

    def _draw_drop_zone(self):
        rect = pygame.Rect(0, 0, WIDTH, DROP_ZONE_HEIGHT)
        pygame.draw.rect(self.screen, DROP_ZONE_COLOR, rect)
        label = self.font_small.render(
            "Click here or press Space to drop  •  R = reset ball  •  C = clear pegs",
            True, UI_TEXT_COLOR,
        )
        self.screen.blit(label, label.get_rect(center=(WIDTH // 2, DROP_ZONE_HEIGHT // 2)))

    def _draw_pegs(self):
        for body, _ in self.pegs:
            px, py = pymunk.pygame_util.to_pygame(body.position, self.screen)
            # glow ring
            glow_surf = pygame.Surface((PEG_RADIUS * 4, PEG_RADIUS * 4), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*PEG_GLOW_COLOR[:3], 60),
                               (PEG_RADIUS * 2, PEG_RADIUS * 2), PEG_RADIUS * 2)
            self.screen.blit(glow_surf, (px - PEG_RADIUS * 2, py - PEG_RADIUS * 2))
            pygame.draw.circle(self.screen, PEG_COLOR, (px, py), PEG_RADIUS)

    def _draw_ball(self):
        if self.ball_body is None:
            return
        px, py = pymunk.pygame_util.to_pygame(self.ball_body.position, self.screen)
        pygame.draw.circle(self.screen, BALL_COLOR, (px, py), BALL_RADIUS)
        # small highlight
        pygame.draw.circle(self.screen, (255, 255, 180), (px - 4, py - 4), 4)

    def _draw_bucket_area(self):
        bucket_w = WIDTH / NUM_BUCKETS
        bucket_top = PEG_AREA_BOTTOM  # pygame y=620

        # background strip
        pygame.draw.rect(
            self.screen, (20, 20, 40),
            pygame.Rect(0, bucket_top, WIDTH, BUCKET_HEIGHT),
        )

        # dividers
        for x in self.divider_x:
            pygame.draw.line(
                self.screen, DIVIDER_COLOR,
                (int(x), bucket_top),
                (int(x), HEIGHT),
                2,
            )

        # bucket labels / highlight
        for i in range(NUM_BUCKETS):
            cx = int((i + 0.5) * bucket_w)
            cy = bucket_top + BUCKET_HEIGHT // 2

            if self.scored_bucket == i:
                # gold highlight rectangle
                pygame.draw.rect(
                    self.screen, BUCKET_HIT_COLOR,
                    pygame.Rect(int(i * bucket_w) + 2, bucket_top + 2,
                                int(bucket_w) - 4, BUCKET_HEIGHT - 4),
                    border_radius=4,
                )
                color = (30, 30, 30)
            else:
                color = BUCKET_LABEL_COLOR

            label = self.font_medium.render(str(BUCKET_SCORES[i]), True, color)
            self.screen.blit(label, label.get_rect(center=(cx, cy)))

    def _draw_ui(self):
        if self.score is not None:
            banner = self.font_large.render(f"+ {self.score} points!", True, SCORE_TEXT_COLOR)
            self.screen.blit(banner, banner.get_rect(center=(WIDTH // 2, DROP_ZONE_HEIGHT // 2)))

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)  # cap to avoid tunnelling on freeze
            running = self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()
        sys.exit()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    PlinkoGame().run()
