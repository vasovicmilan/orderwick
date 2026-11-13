"""Simple UI: text + widgets (button, spinner, focus group) in NATIVE pixels."""
from __future__ import annotations

from typing import Callable

import pygame

from ..view.colors import BTN_BAD, BTN_GOOD, BTN_SHADOW, BTN_TEXT, BTN_VALUE, DARK, DISABLED, GOLD, UI_DIM
from .audio import audio


def draw_text(surface: pygame.Surface, text: str, font: pygame.font.Font, color,
              pos: tuple[int, int], anchor: str = "topleft", shadow: bool = False) -> pygame.Rect:
    img = font.render(text, True, color)
    rect = img.get_rect(**{anchor: pos})
    if shadow:
        sh = font.render(text, True, (0, 0, 0))
        surface.blit(sh, rect.move(2, 2))
    surface.blit(img, rect)
    return rect


def wrap_text(text: str, font: pygame.font.Font, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        line = ""
        for w in words:
            trial = f"{line} {w}".strip()
            if font.size(trial)[0] <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = w
        lines.append(line)
    return lines


def dim_background(surface: pygame.Surface, alpha: int = 170) -> None:
    shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    shade.fill((0, 0, 0, alpha))
    surface.blit(shade, (0, 0))


class Widget:
    enabled = True

    def __init__(self) -> None:
        self.rect = pygame.Rect(0, 0, 0, 0)

    def handle_mouse(self, event: pygame.event.Event) -> bool:
        return False

    def handle_key(self, event: pygame.event.Event) -> bool:
        return False

    def handle_motion(self, event: pygame.event.Event) -> None: ...
    def handle_up(self, event: pygame.event.Event) -> None: ...

    def draw(self, surface: pygame.Surface, kit, focused: bool, hover: bool) -> None: ...


class Button(Widget):
    def __init__(self, text: str, on_click: Callable[[], None], hint: str = "", enabled: bool = True,
                 icon: str | None = None):
        super().__init__()
        self.text = text
        self.on_click = on_click
        self.hint = hint
        self.enabled = enabled
        self.icon = icon

    def handle_mouse(self, event: pygame.event.Event) -> bool:
        if (self.enabled and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.rect.collidepoint(event.pos)):
            audio.play("ui_click")
            self.on_click()
            return True
        return False

    def handle_key(self, event: pygame.event.Event) -> bool:
        if self.enabled and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            audio.play("ui_click")
            self.on_click()
            return True
        return False

    def draw(self, surface, kit, focused, hover) -> None:
        state = "disabled" if not self.enabled else "hover" if (focused or hover) else "normal"
        kit.draw_button(surface, self.rect, self.text, state, self.icon, self.hint)


class Spinner(Widget):
    """Number chooser with arrows (mouse, wheel or left/right)."""
    VALUE_W = 26                 # width of the value field between the arrows

    def __init__(self, label: str, value: int, lo: int, hi: int,
                 on_change: Callable[[int], None] | None = None):
        super().__init__()
        self.label = label
        self.value = value
        self.lo, self.hi = lo, hi
        self.on_change = on_change

    def set_range(self, lo: int, hi: int) -> None:
        self.lo, self.hi = lo, hi
        self.set_value(self.value)

    def set_value(self, value: int) -> None:
        value = max(self.lo, min(self.hi, value))
        if value != self.value:
            self.value = value
            if self.on_change:
                self.on_change(value)
        self.value = value

    def _arrows(self) -> tuple[pygame.Rect, pygame.Rect]:
        h = self.rect.height
        right = pygame.Rect(self.rect.right - 4 - 12, self.rect.y, 12, h)
        left = pygame.Rect(right.x - self.VALUE_W - 12, self.rect.y, 12, h)
        return left, right

    def handle_mouse(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 4, 5) and self.rect.collidepoint(event.pos):
            left, right = self._arrows()
            if event.button == 4 or (event.button == 1 and right.collidepoint(event.pos)):
                self.set_value(self.value + 1)
                return True
            if event.button == 5 or (event.button == 1 and left.collidepoint(event.pos)):
                self.set_value(self.value - 1)
                return True
        return False

    def handle_key(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_RIGHT:
            self.set_value(self.value + 1)
            return True
        if event.key == pygame.K_LEFT:
            self.set_value(self.value - 1)
            return True
        return False

    def draw(self, surface, kit, focused, hover) -> None:
        kit.draw_button(surface, self.rect, "", "hover" if (focused or hover) else "normal")
        cy = self.rect.y + (self.rect.h - 8) // 2
        kit.text(surface, self.label, (self.rect.x + 6, cy), BTN_TEXT, shadow_color=BTN_SHADOW)
        left, right = self._arrows()
        kit.text(surface, str(self.value), ((left.right + right.left) // 2, cy), BTN_VALUE, "midtop",
                 shadow_color=BTN_SHADOW)
        for r, direction in ((left, -1), (right, 1)):
            can = (self.value > self.lo) if direction < 0 else (self.value < self.hi)
            kit.draw_arrow(surface, r.center, direction, BTN_TEXT if can else UI_DIM)


class Toggle(Widget):
    """On / off (Enter, Space, left/right or click)."""

    def __init__(self, label: str, value: bool, on_change: Callable[[bool], None], icon_on: str, icon_off: str):
        super().__init__()
        self.label, self.value, self.on_change = label, value, on_change
        self.icon_on, self.icon_off = icon_on, icon_off

    def _flip(self) -> None:
        self.value = not self.value
        audio.play("ui_click")
        self.on_change(self.value)

    def handle_mouse(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self._flip()
            return True
        return False

    def handle_key(self, event) -> bool:
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_LEFT, pygame.K_RIGHT):
            self._flip()
            return True
        return False

    def draw(self, surface, kit, focused, hover) -> None:
        kit.draw_button(surface, self.rect, "", "hover" if (focused or hover) else "normal")
        surface.blit(kit.icons[self.icon_on if self.value else self.icon_off], (self.rect.x + 4, self.rect.y + 2))
        cy = self.rect.y + (self.rect.h - 8) // 2
        kit.text(surface, self.label, (self.rect.x + 20, cy), BTN_TEXT, shadow_color=BTN_SHADOW)
        kit.text(surface, "ON" if self.value else "OFF", (self.rect.right - 8, cy),
                 BTN_GOOD if self.value else BTN_BAD, "topright", shadow_color=BTN_SHADOW)


class Slider(Widget):
    """Volume 0-100 in steps of 10 (left/right, click or mouse drag)."""
    BLOCKS, BLOCK_W, BLOCK_GAP = 10, 6, 2

    def __init__(self, label: str, value: int, on_change: Callable[[int], None]):
        super().__init__()
        self.label, self.value, self.on_change = label, value, on_change
        self.dragging = False

    def _bar(self) -> pygame.Rect:
        w = self.BLOCKS * (self.BLOCK_W + self.BLOCK_GAP) - self.BLOCK_GAP
        return pygame.Rect(self.rect.right - 8 - w - 26, self.rect.y + 4, w, self.rect.h - 8)

    def _set(self, value: int) -> None:
        value = max(0, min(100, int(round(value / 10.0)) * 10))
        if value != self.value:
            self.value = value
            self.on_change(value)

    def _from_x(self, x: int) -> None:
        bar = self._bar()
        self._set((x - bar.x + 2) * 100 // max(1, bar.w))

    def handle_mouse(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self.dragging = True
            self._from_x(event.pos[0])
            return True
        return False

    def handle_motion(self, event) -> None:
        if self.dragging:
            self._from_x(event.pos[0])

    def handle_up(self, event) -> None:
        self.dragging = False

    def handle_key(self, event) -> bool:
        if event.key == pygame.K_RIGHT:
            self._set(self.value + 10)
            return True
        if event.key == pygame.K_LEFT:
            self._set(self.value - 10)
            return True
        return False

    def draw(self, surface, kit, focused, hover) -> None:
        kit.draw_button(surface, self.rect, "", "hover" if (focused or hover) else "normal")
        cy = self.rect.y + (self.rect.h - 8) // 2
        kit.text(surface, self.label, (self.rect.x + 20, cy), BTN_TEXT, shadow_color=BTN_SHADOW)
        bar = self._bar()
        lit = self.value // 10
        for i in range(self.BLOCKS):
            r = pygame.Rect(bar.x + i * (self.BLOCK_W + self.BLOCK_GAP), bar.y, self.BLOCK_W, bar.h)
            surface.fill(GOLD if i < lit else DARK, r)
        kit.text(surface, f"{self.value}", (self.rect.right - 8, cy), BTN_TEXT, "topright", shadow_color=BTN_SHADOW)


class Choice(Widget):
    """Pick one of several options with left/right (locked options are shown but cannot be chosen)."""
    FIELD_W = 64

    def __init__(self, label: str, options: list[tuple[str, str]], current: str,
                 on_change: Callable[[str], None], is_unlocked: Callable[[str], bool],
                 requirement: Callable[[str], str] = lambda _id: ""):
        super().__init__()
        self.label, self.options = label, options
        self.on_change, self.is_unlocked, self.requirement = on_change, is_unlocked, requirement
        self.pos = next((i for i, (oid, _n) in enumerate(options) if oid == current), 0)

    @property
    def shown_id(self) -> str:
        return self.options[self.pos][0]

    def hint(self) -> str:
        """Text for a locked option that is currently shown (how to unlock it)."""
        return "" if self.is_unlocked(self.shown_id) else self.requirement(self.shown_id)

    def _step(self, direction: int) -> None:
        self.pos = (self.pos + direction) % len(self.options)
        if self.is_unlocked(self.shown_id):
            audio.play("ui_click")
            self.on_change(self.shown_id)
        else:
            audio.play("invalid", 0.6)

    def handle_mouse(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            left_x = self.rect.right - 10 - 12 - self.FIELD_W
            self._step(-1 if event.pos[0] < left_x + 6 else 1)
            return True
        return False

    def handle_key(self, event) -> bool:
        if event.key in (pygame.K_RIGHT, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._step(1)
            return True
        if event.key == pygame.K_LEFT:
            self._step(-1)
            return True
        return False

    def draw(self, surface, kit, focused, hover) -> None:
        kit.draw_button(surface, self.rect, "", "hover" if (focused or hover) else "normal")
        cy = self.rect.y + (self.rect.h - 8) // 2
        kit.text(surface, self.label, (self.rect.x + 6, cy), BTN_TEXT, shadow_color=BTN_SHADOW)
        right_c = (self.rect.right - 10, self.rect.centery)
        left_c = (self.rect.right - 10 - 12 - self.FIELD_W, self.rect.centery)
        kit.draw_arrow(surface, left_c, -1, BTN_TEXT)
        kit.draw_arrow(surface, right_c, 1, BTN_TEXT)
        name = self.options[self.pos][1]
        mid = (left_c[0] + right_c[0]) // 2
        if self.is_unlocked(self.shown_id):
            kit.text(surface, name, (mid, cy), BTN_VALUE, "midtop", shadow_color=BTN_SHADOW)
        else:
            kit.text(surface, name, (mid + 6, cy), DISABLED, "midtop", shadow=False)
            surface.blit(kit.icons["lock"], (mid - kit.width(name) // 2 - 12, self.rect.y + 2))


class FocusGroup:
    """A group of widgets with focus (up/down/Tab) and mouse (native coordinates)."""

    def __init__(self, widgets: list[Widget]):
        self.widgets = widgets
        self.focus = 0
        self.hover: Widget | None = None

    def layout_column(self, center_x: int, top: int, width: int, height: int, gap: int) -> None:
        y = top
        for w in self.widgets:
            w.rect = pygame.Rect(center_x - width // 2, y, width, height)
            y += height + gap

    def _move(self, step: int) -> None:
        n = len(self.widgets)
        for _ in range(n):
            self.focus = (self.focus + step) % n
            if self.widgets[self.focus].enabled:
                return

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.hover = next((w for w in self.widgets if w.rect.collidepoint(event.pos)), None)
            if self.hover is not None and self.hover.enabled:
                idx = self.widgets.index(self.hover)
                if idx != self.focus:
                    audio.play("ui_move")
                self.focus = idx
            for w in self.widgets:
                w.handle_motion(event)
            return False
        if event.type == pygame.MOUSEBUTTONUP:
            for w in self.widgets:
                w.handle_up(event)
            return False
        if event.type == pygame.MOUSEBUTTONDOWN:
            for w in self.widgets:
                if w.handle_mouse(event):
                    return True
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN or (event.key == pygame.K_TAB and not event.mod & pygame.KMOD_SHIFT):
                self._move(1)
                audio.play("ui_move")
                return True
            if event.key == pygame.K_UP or event.key == pygame.K_TAB:
                self._move(-1)
                audio.play("ui_move")
                return True
            return self.widgets[self.focus].handle_key(event)
        return False

    def draw(self, surface: pygame.Surface, kit) -> None:
        for i, w in enumerate(self.widgets):
            w.draw(surface, kit, i == self.focus, w is self.hover)
