import os
import json
import glob
import time
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.modalview import ModalView
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.core.window import Window
from kivy.core.text import Label as CoreLabel
from kivy.clock import Clock

# ── tunables ──────────────────────────────────────────────────────────────────
RADIUS          = 36
BG_COLOR        = (0.10, 0.10, 0.14, 1)
CIRCLE_COLORS   = [
    (0.30, 0.70, 1.00, 1),
    (0.80, 0.35, 1.00, 1),
    (0.20, 0.90, 0.60, 1),
    (1.00, 0.55, 0.20, 1),
    (1.00, 0.30, 0.50, 1),
]
RING_COLOR      = (1, 1, 1, 0.25)
LABEL_COLOR     = (1, 1, 1, 0.35)
TEXT_COLOR      = (1, 1, 1, 1)
RED_RING_RADIUS = RADIUS * 2
TEXT_FONT_SIZE  = 26
TEXT_WRAP_PX    = int(TEXT_FONT_SIZE * 15)

BTN_W           = 140
BTN_H           = 56
BTN_FONT        = '16sp'
BTN_GAP         = 8          # px between toolbar buttons

FILE_EXT        = '.cir'
LONG_PRESS_SEC  = 0.55

# ── detect APK vs desktop ─────────────────────────────────────────────────────
def _is_apk():
    try:
        from android import mActivity  # only present inside compiled APK
        return True
    except Exception:
        return False

# Settings file on /sdcard survives reinstalls; falls back to ~ on desktop
def _settings_path():
    if _is_apk() and os.path.isdir('/sdcard'):
        return '/sdcard/.circles_settings.json'
    return os.path.join(os.path.expanduser('~'), '.circles_settings.json')

SETTINGS_PATH = _settings_path()

SAVE_LOCATIONS = [
    ('Home (~)',           os.path.expanduser('~')),
    ('Documents',         os.path.expanduser('~/Documents')),
    ('Downloads',         os.path.expanduser('~/Downloads')),
    ('/sdcard',           '/sdcard'),
    ('/sdcard/Download',  '/sdcard/Download'),
    ('/sdcard/Documents', '/sdcard/Documents'),
]

def _best_start_dir():
    for d in ('/sdcard', os.path.expanduser('~')):
        if os.path.isdir(d):
            return d
    return '/'


# ── Android runtime storage permission ───────────────────────────────────────
def _request_android_permissions():
    """Request READ/WRITE_EXTERNAL_STORAGE at runtime (Android 6+).
    Safe no-op on desktop / Pydroid 3."""
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
        ])
    except Exception:
        pass


# ── settings ──────────────────────────────────────────────────────────────────
def load_settings():
    try:
        with open(SETTINGS_PATH, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_settings(data):
    try:
        with open(SETTINGS_PATH, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def get_work_dir():
    saved = load_settings().get('work_dir')
    if saved and os.path.isdir(saved):
        return saved
    return _best_start_dir()

def set_work_dir(path):
    s = load_settings(); s['work_dir'] = path; save_settings(s)

def latest_cir_in(directory):
    files = glob.glob(os.path.join(directory, f'*{FILE_EXT}'))
    return max(files, key=os.path.getmtime) if files else None


# ── text helpers ──────────────────────────────────────────────────────────────
def _hit(cx, cy, tx, ty):
    return ((tx - cx) ** 2 + (ty - cy) ** 2) <= RADIUS ** 2

def _trash_pos(widget):
    """Centre of the trash circle: bottom-left corner of the canvas."""
    return (widget.pos[0] + RADIUS + 10,
            widget.pos[1] + RADIUS + 10)

def _over_trash(cx, cy, widget):
    """True when a circle centre is close enough to the trash to be deleted."""
    tx, ty = _trash_pos(widget)
    return ((cx - tx) ** 2 + (cy - ty) ** 2) <= (RADIUS * 2) ** 2


def _wrap_text(text, max_width_px, font_size=TEXT_FONT_SIZE):
    words = text.split()
    if not words:
        return []
    lines, current = [], ''
    for word in words:
        test = (current + ' ' + word).strip()
        lbl  = CoreLabel(text=test, font_size=font_size, color=TEXT_COLOR)
        lbl.refresh()
        if lbl.texture.size[0] <= max_width_px or not current:
            current = test
        else:
            lines.append(current); current = word
    if current:
        lines.append(current)
    textures = []
    for line in lines:
        lbl = CoreLabel(text=line, font_size=font_size, color=TEXT_COLOR)
        lbl.refresh()
        textures.append(lbl.texture)
    return textures


# ── serialise / deserialise ───────────────────────────────────────────────────
def collect_all_canvases(sm):
    data = {}
    for screen in sm.screens:
        cw = screen.cw
        circles_out = []
        for i, c in enumerate(cw.circles):
            circles_out.append({
                'x': round(c['x'], 1), 'y': round(c['y'], 1),
                'color_index': c['color_index'],
                'text': c.get('text', ''),
                'child_id': cw.children_ids[i],
            })
        data[screen.name] = {'parent_id': screen.parent_id, 'circles': circles_out}
    return data

def save_to_file(sm, filepath):
    data  = collect_all_canvases(sm)
    lines = ['CIRCLES APP SAVE FILE', '=' * 40, '']
    for canvas_id, info in data.items():
        lines.append(f'CANVAS: {canvas_id}')
        lines.append(f'  parent : {info["parent_id"] or "none (root)"}')
        if not info['circles']:
            lines.append('  (no circles)')
        for idx, c in enumerate(info['circles']):
            lines += [f'  circle {idx+1}:',
                      f'    x     = {c["x"]}', f'    y     = {c["y"]}',
                      f'    color = {c["color_index"]}',
                      f'    text  = {c["text"]}',
                      f'    child = {c["child_id"] or "none"}']
        lines.append('')
    lines += ['# --- raw JSON (used by Load) ---', json.dumps(data, indent=2)]
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def load_from_file(filepath, sm):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    data = json.loads(content.split('# --- raw JSON (used by Load) ---', 1)[1].strip())
    for screen in list(sm.screens):
        sm.remove_widget(screen)
    for canvas_id in (['root'] + [k for k in data if k != 'root']):
        if canvas_id not in data:
            continue
        info   = data[canvas_id]
        screen = CanvasScreen(canvas_id=canvas_id,
                              parent_id=info['parent_id'], sm=sm)
        cw = screen.cw
        for c in info['circles']:
            cw.circles.append({'x': c['x'], 'y': c['y'],
                                'color_index': c['color_index'], 'text': c['text']})
            cw.children_ids.append(c['child_id'])
            cw._line_textures.append([])
            cw._color_counter = max(cw._color_counter, c['color_index'] + 1)
        sm.add_widget(screen)
        # Seed _prev_size so rotation rescaling has a correct baseline
        from kivy.core.window import Window as _W
        cw._prev_size = (_W.width, _W.height)
    sm.current = 'root'


# ── shared dialog card background ─────────────────────────────────────────────
def _dark_card(root):
    with root.canvas.before:
        Color(0.14, 0.14, 0.20, 1)
        card = RoundedRectangle(radius=[14])
    root.bind(pos=lambda w, *_: setattr(card, 'pos', w.pos),
              size=lambda w, *_: setattr(card, 'size', w.size))


# ── dialogs ───────────────────────────────────────────────────────────────────
class InfoDialog(ModalView):
    def __init__(self, message='', **kwargs):
        super().__init__(size_hint=(0.82, None), height=150,
                         background_color=(0, 0, 0, 0), **kwargs)
        root = BoxLayout(orientation='vertical', spacing=8, padding=14)
        _dark_card(root)
        root.add_widget(Label(text=message, font_size='13sp',
                              color=(1, 1, 1, 0.9), halign='center',
                              text_size=(Window.width * 0.72, None)))
        b = Button(background_normal='', text='OK', size_hint_y=None, height=BTN_H,
                   background_color=(0.25, 0.55, 0.95, 1),
                   color=(1, 1, 1, 1), font_size=BTN_FONT)
        b.bind(on_release=lambda *_: self.dismiss())
        root.add_widget(b)
        self.add_widget(root)


class TextDialog(ModalView):
    """Circle label entry / edit."""
    def __init__(self, initial_text='', on_confirm=None, title='Circle label', **kwargs):
        super().__init__(size_hint=(0.88, None), height=200,
                         background_color=(0, 0, 0, 0), **kwargs)
        self._on_confirm = on_confirm
        root = BoxLayout(orientation='vertical', spacing=8, padding=14)
        _dark_card(root)
        root.add_widget(Label(text=title, font_size='15sp',
                              color=(1, 1, 1, 0.8), size_hint_y=None, height=30))
        self.ti = TextInput(text=initial_text, hint_text='Enter text…',
                            multiline=False, font_size='17sp',
                            foreground_color=(1, 1, 1, 1),
                            background_color=(0.22, 0.22, 0.30, 1),
                            cursor_color=(1, 1, 1, 1),
                            size_hint_y=None, height=52)
        self.ti.bind(on_text_validate=self._ok)
        root.add_widget(self.ti)
        btns = BoxLayout(size_hint_y=None, height=BTN_H, spacing=8)
        cb = Button(background_normal='', text='Cancel', background_color=(0.35, 0.35, 0.45, 1),
                    color=(1, 1, 1, 0.9), font_size=BTN_FONT)
        cb.bind(on_release=lambda *_: self.dismiss())
        ob = Button(background_normal='', text='OK', background_color=(0.20, 0.55, 0.20, 1),
                    color=(1, 1, 1, 1), font_size=BTN_FONT)
        ob.bind(on_release=self._ok)
        btns.add_widget(cb); btns.add_widget(ob)
        root.add_widget(btns)
        self.add_widget(root)
        self.bind(on_open=lambda *_: setattr(self.ti, 'focus', True))

    def _ok(self, *_):
        if self._on_confirm:
            self._on_confirm(self.ti.text.strip())
        self.dismiss()


class FolderBrowserDialog(ModalView):
    """
    Simple filesystem browser: shows folders and .cir files.
    on_confirm(path) is called with either a directory (for Settings)
    or a full file path (for Load), depending on mode.
    mode = 'dir'  → selecting a directory
    mode = 'load' → selecting a .cir file
    mode = 'save' → selecting a directory + typing filename
    """
    def __init__(self, start_dir=None, mode='dir', on_confirm=None, default_name='circles', **kwargs):
        super().__init__(size_hint=(0.96, 0.88),
                         background_color=(0, 0, 0, 0), **kwargs)
        self._on_confirm = on_confirm
        self._mode       = mode
        self._cur        = start_dir or get_work_dir()

        self._root = BoxLayout(orientation='vertical', spacing=4, padding=10)
        _dark_card(self._root)

        # ── title + current path ──────────────────────────────────────────────
        titles = {'dir': 'Choose Folder', 'load': 'Load File',
                  'save': 'Save As'}
        self._root.add_widget(Label(text=titles[mode], font_size='15sp',
                                    color=(1, 1, 1, 0.9),
                                    size_hint_y=None, height=32))
        self._path_lbl = Label(text='', font_size='11sp',
                               color=(1, 1, 1, 0.45), size_hint_y=None, height=20,
                               halign='left', text_size=(Window.width * 0.90, None))
        self._root.add_widget(self._path_lbl)

        # ── quick-jump bookmarks ──────────────────────────────────────────────
        bk_row = BoxLayout(size_hint_y=None, height=38, spacing=4)
        bookmarks = [('~', os.path.expanduser('~')), ('/sdcard', '/sdcard'),
                     ('DL', '/sdcard/Download'), ('Docs', '/sdcard/Documents')]
        for bk_label, bk_path in bookmarks:
            if os.path.isdir(bk_path):
                bk = Button(background_normal='', text=bk_label, font_size='12sp',
                            background_color=(0.25, 0.25, 0.38, 1),
                            color=(1, 1, 1, 0.9), size_hint_y=None, height=36)
                bk.bind(on_release=lambda b, p=bk_path: self._populate(p))
                bk_row.add_widget(bk)
        self._root.add_widget(bk_row)

        # ── filename row (save mode only) ─────────────────────────────────────
        if mode == 'save':
            row = BoxLayout(size_hint_y=None, height=50, spacing=6)
            row.add_widget(Label(text='Name:', font_size='13sp',
                                 color=(1, 1, 1, 0.7), size_hint_x=None, width=70))
            self._fname_ti = TextInput(
                text=default_name, multiline=False, font_size='15sp',
                foreground_color=(1, 1, 1, 1),
                background_color=(0.20, 0.20, 0.28, 1),
                cursor_color=(1, 1, 1, 1))
            row.add_widget(self._fname_ti)
            self._root.add_widget(row)

        # ── scrollable file list ──────────────────────────────────────────────
        self._scroll = ScrollView(size_hint=(1, 1))
        self._list   = BoxLayout(orientation='vertical', spacing=4,
                                 size_hint_y=None)
        self._list.bind(minimum_height=self._list.setter('height'))
        self._scroll.add_widget(self._list)
        self._root.add_widget(self._scroll)

        # ── bottom buttons ────────────────────────────────────────────────────
        btns = BoxLayout(size_hint_y=None, height=BTN_H, spacing=8)
        cb   = Button(background_normal='', text='Cancel', background_color=(0.35, 0.35, 0.45, 1),
                      color=(1, 1, 1, 0.9), font_size=BTN_FONT)
        cb.bind(on_release=lambda *_: self.dismiss())
        btns.add_widget(cb)
        if mode in ('dir', 'save'):
            ob = Button(background_normal='', text='Select This Folder',
                        background_color=(0.20, 0.55, 0.20, 1),
                        color=(1, 1, 1, 1), font_size=BTN_FONT)
            ob.bind(on_release=self._confirm_dir)
            btns.add_widget(ob)
        self._root.add_widget(btns)

        self.add_widget(self._root)
        self._populate(self._cur)

    def _populate(self, path):
        self._cur = path
        self._path_lbl.text = path
        self._list.clear_widgets()

        # Up button
        parent = os.path.dirname(path)
        if parent != path:
            up = Button(background_normal='', text='.. up', font_size='14sp',
                        background_color=(0.22, 0.22, 0.32, 1),
                        color=(1, 1, 1, 0.8), size_hint_y=None, height=48)
            up.bind(on_release=lambda *_: self._populate(parent))
            self._list.add_widget(up)

        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            self._list.add_widget(Label(text='Permission denied', font_size='13sp',
                                        color=(1, 0.3, 0.3, 1),
                                        size_hint_y=None, height=40))
            return

        for entry in entries:
            if entry.name.startswith('.'):
                continue
            is_dir  = entry.is_dir()
            is_cir  = entry.name.endswith(FILE_EXT)

            # In load mode show only dirs + .cir files
            if self._mode == 'load' and not is_dir and not is_cir:
                continue
            # In dir/save mode show only dirs
            if self._mode in ('dir', 'save') and not is_dir:
                continue

            icon = '[D] ' if is_dir else '[F] '
            bg   = (0.18, 0.30, 0.48, 1) if is_dir else (0.28, 0.18, 0.48, 1)
            btn  = Button(background_normal='', text=icon + entry.name, font_size='14sp',
                          background_color=bg, color=(1, 1, 1, 1),
                          size_hint_y=None, height=48,
                          halign='left', valign='middle')
            btn.text_size = (Window.width * 0.88, None)
            full = entry.path
            if is_dir:
                btn.bind(on_release=lambda b, p=full: self._populate(p))
            else:
                btn.bind(on_release=lambda b, p=full: self._pick_file(p))
            self._list.add_widget(btn)

    def _pick_file(self, path):
        if self._on_confirm:
            self._on_confirm(path)
        self.dismiss()

    def _confirm_dir(self, *_):
        if self._mode == 'save':
            fname = self._fname_ti.text.strip()
            if not fname:
                return
            if not fname.endswith(FILE_EXT):
                fname += FILE_EXT
            if self._on_confirm:
                self._on_confirm(os.path.join(self._cur, fname))
        else:
            if self._on_confirm:
                self._on_confirm(self._cur)
        self.dismiss()


# ── canvas widget ─────────────────────────────────────────────────────────────
class CanvasWidget(Widget):

    def __init__(self, canvas_id=0, sm=None, **kwargs):
        super().__init__(**kwargs)
        self.canvas_id      = canvas_id
        self.sm             = sm
        self.circles        = []
        self.children_ids   = []
        self._dragging      = None
        self._drag_offset   = (0, 0)
        self._color_counter = 0
        self._line_textures = []
        self._lp_event      = None
        self._lp_idx        = None
        self._touch_moved   = False
        self._prev_size     = None   # track last known size for rescaling
        self.bind(size=self._on_size, pos=self._redraw)

    def _on_size(self, instance, new_size):
        """Rescale all circle positions proportionally when canvas is resized."""
        w, h = new_size
        # Ignore layout passes where size is not yet real
        if w < 10 or h < 10:
            return
        if self._prev_size and self.circles:
            pw, ph = self._prev_size
            if pw >= 10 and ph >= 10 and (pw != w or ph != h):
                for c in self.circles:
                    c['x'] = c['x'] * w / pw
                    c['y'] = c['y'] * h / ph
        self._prev_size = (w, h)
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(*BG_COLOR)
            Rectangle(pos=self.pos, size=self.size)
            # fixed red ring at canvas centre
            Color(1, 0.15, 0.15, 0.85)
            Line(circle=(self.pos[0] + self.size[0] / 2,
                         self.pos[1] + self.size[1] / 2,
                         RED_RING_RADIUS), width=2.2)
            # trash bin: white circle in bottom-left corner
            _tx, _ty = _trash_pos(self)
            # turns red when a circle is being dragged over it
            if self._dragging is not None and _over_trash(
                    self.circles[self._dragging]['x'],
                    self.circles[self._dragging]['y'], self):
                Color(1, 0.2, 0.2, 1)
            else:
                Color(1, 1, 1, 0.55)
            Line(circle=(_tx, _ty, RADIUS), width=2.5)
            # X mark inside
            off = int(RADIUS * 0.45)
            Color(1, 1, 1, 0.55) if self._dragging is None or not _over_trash(
                self.circles[self._dragging]['x'],
                self.circles[self._dragging]['y'], self) else Color(1, 0.2, 0.2, 1)
            Line(points=[_tx - off, _ty - off, _tx + off, _ty + off], width=1.8)
            Line(points=[_tx + off, _ty - off, _tx - off, _ty + off], width=1.8)
            for i, c in enumerate(self.circles):
                cx, cy = c['x'], c['y']
                Color(*CIRCLE_COLORS[c['color_index'] % len(CIRCLE_COLORS)])
                Ellipse(pos=(cx - RADIUS, cy - RADIUS),
                        size=(RADIUS * 2, RADIUS * 2))
                Color(*RING_COLOR)
                Line(circle=(cx, cy, RADIUS), width=1.8)
                if self.children_ids[i] is not None:
                    Color(1, 1, 1, 0.9)
                    dot_r = 7
                    Ellipse(pos=(cx + RADIUS * 0.65 - dot_r,
                                 cy + RADIUS * 0.65 - dot_r),
                            size=(dot_r * 2, dot_r * 2))
                lines = self._line_textures[i]
                if not lines and c.get('text'):
                    lines = _wrap_text(c['text'], TEXT_WRAP_PX, font_size=TEXT_FONT_SIZE)
                    self._line_textures[i] = lines
                if lines:
                    y_start = cy - RADIUS - 4 - lines[0].size[1]
                    Color(1, 1, 1, 1)
                    for tex in lines:
                        tw, th = tex.size
                        Rectangle(texture=tex,
                                  pos=(cx - tw / 2, y_start), size=(tw, th))
                        y_start -= th + 2

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        tx, ty      = touch.pos
        self._touch_moved = False

        hit_idx = None
        for i in range(len(self.circles) - 1, -1, -1):
            if _hit(self.circles[i]['x'], self.circles[i]['y'], tx, ty):
                hit_idx = i; break

        if touch.is_double_tap:
            self._cancel_lp()
            if hit_idx is not None:
                self._open_child(hit_idx)
            else:
                self._prompt_add(tx, ty)
            return True

        # start long-press timer if on a circle
        if hit_idx is not None:
            self._lp_idx = hit_idx
            self._lp_event = Clock.schedule_once(
                lambda dt: self._do_long_press(), LONG_PRESS_SEC)
            # also start drag tracking
            self._dragging    = hit_idx
            c = self.circles[hit_idx]
            self._drag_offset = (c['x'] - tx, c['y'] - ty)

        return True

    def on_touch_move(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if abs(touch.dx) > 4 or abs(touch.dy) > 4:
            self._touch_moved = True
            self._cancel_lp()   # moved → not a long-press
        if self._dragging is None:
            return False
        ox, oy = self._drag_offset
        self.circles[self._dragging]['x'] = touch.x + ox
        self.circles[self._dragging]['y'] = touch.y + oy
        self._redraw()
        return True

    def _delete_circle_recursive(self, idx):
        """Delete circle at idx and recursively remove all its child canvases."""
        child_id = self.children_ids[idx]
        if child_id is not None:
            self._remove_canvas_tree(child_id)
        self.circles.pop(idx)
        self.children_ids.pop(idx)
        self._line_textures.pop(idx)

    def _remove_canvas_tree(self, canvas_id):
        """Recursively remove a canvas screen and all its descendants."""
        screen = next((s for s in self.sm.screens if s.name == canvas_id), None)
        if screen is None:
            return
        # recurse into children first
        for child_id in screen.cw.children_ids:
            if child_id is not None:
                self._remove_canvas_tree(child_id)
        self.sm.remove_widget(screen)

    def on_touch_up(self, touch):
        self._cancel_lp()
        if self._dragging is not None:
            idx = self._dragging
            self._dragging = None
            c = self.circles[idx]
            if _over_trash(c['x'], c['y'], self):
                self._delete_circle_recursive(idx)
            self._redraw()
            App.get_running_app().autosave()
            return True
        return False

    def _cancel_lp(self):
        if self._lp_event:
            self._lp_event.cancel()
            self._lp_event = None

    def _do_long_press(self):
        self._lp_event = None
        if self._touch_moved or self._lp_idx is None:
            return
        idx = self._lp_idx
        self._dragging = None   # cancel drag
        current_text   = self.circles[idx].get('text', '')
        def confirm(new_text):
            self.circles[idx]['text']    = new_text
            self._line_textures[idx]     = []   # invalidate cache
            self._redraw()
            App.get_running_app().autosave()
        TextDialog(initial_text=current_text, on_confirm=confirm,
                   title='Edit label').open()

    def _prompt_add(self, x, y):
        def confirm(text):
            self.circles.append({'x': x, 'y': y,
                                  'color_index': self._color_counter, 'text': text})
            self.children_ids.append(None)
            self._line_textures.append([])
            self._color_counter += 1
            self._redraw()
            App.get_running_app().autosave()
        TextDialog(initial_text='', on_confirm=confirm, title='Circle label').open()

    def _open_child(self, idx):
        child_id = self.children_ids[idx]
        if child_id is None:
            child_id = f"canvas_{id(self)}_{idx}"
            self.children_ids[idx] = child_id
            self.sm.add_widget(CanvasScreen(canvas_id=child_id,
                                            parent_id=self.sm.current, sm=self.sm))
            self._redraw()
        self.sm.transition = SlideTransition(direction='left')
        self.sm.current    = child_id


# ── toolbar button ────────────────────────────────────────────────────────────
class ToolButton(Widget):
    def __init__(self, text, on_tap, bg=(0.22, 0.22, 0.32, 1), **kwargs):
        super().__init__(size_hint=(None, None), size=(BTN_W, BTN_H), **kwargs)
        self._on_tap = on_tap
        with self.canvas:
            Color(*bg)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
        self._lbl = Label(text=text, font_size=BTN_FONT,
                          color=(1, 1, 1, 1), pos=self.pos, size=self.size)
        self.add_widget(self._lbl)
        self.bind(pos=self._s, size=self._s)

    def _s(self, *_):
        self._rect.pos = self.pos; self._rect.size = self.size
        self._lbl.pos  = self.pos; self._lbl.size  = self.size

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._on_tap(); return True
        return False


# ── back button ───────────────────────────────────────────────────────────────
class BackButton(Widget):
    def __init__(self, parent_id, sm, **kwargs):
        super().__init__(size_hint=(None, None), size=(BTN_W, BTN_H),
                         pos_hint={'x': 0.01, 'top': 0.99}, **kwargs)
        self.parent_id = parent_id; self.sm = sm
        with self.canvas:
            Color(1, 1, 1, 0.15)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
        self._lbl = Label(text='< Back', font_size=BTN_FONT,
                          color=(1, 1, 1, 0.90), pos=self.pos, size=self.size)
        self.add_widget(self._lbl)
        self.bind(pos=self._s, size=self._s)

    def _s(self, *_):
        self._bg.pos  = self.pos; self._bg.size  = self.size
        self._lbl.pos = self.pos; self._lbl.size = self.size

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.sm.transition = SlideTransition(direction='right')
            self.sm.current    = self.parent_id
            return True
        return False


# ── screen ────────────────────────────────────────────────────────────────────
class CanvasScreen(Screen):
    def __init__(self, canvas_id, parent_id, sm, **kwargs):
        super().__init__(name=canvas_id, **kwargs)
        self.parent_id = parent_id
        self._sm       = sm

        layout = FloatLayout()
        self.cw = CanvasWidget(canvas_id=canvas_id, sm=sm)
        layout.add_widget(self.cw)

        layout.add_widget(Label(
            text='double-tap empty → add  |  long-press circle → edit  |  double-tap circle → dive in',
            font_size='11sp', color=LABEL_COLOR,
            size_hint=(1, None), height=22, pos_hint={'x': 0, 'y': 0.01}))

        if parent_id is None:
            # Use an AnchorLayout so buttons stack correctly in any orientation
            from kivy.uix.anchorlayout import AnchorLayout
            anchor = AnchorLayout(
                anchor_x='right', anchor_y='top',
                padding=(6, 6, 6, 6),
                size_hint=(None, 1),
                width=BTN_W + 12,
                pos_hint={'right': 1.0, 'top': 1.0}
            )
            toolbar = BoxLayout(
                orientation='vertical',
                spacing=BTN_GAP,
                size_hint=(None, None),
                width=BTN_W,
            )
            # height computed from buttons; updated on window resize
            def _update_toolbar_height(*_):
                toolbar.height = 4 * BTN_H + 3 * BTN_GAP
            Window.bind(size=_update_toolbar_height)
            _update_toolbar_height()

            toolbar.add_widget(ToolButton(
                text='[New]', on_tap=self._do_new,
                bg=(0.45, 0.15, 0.15, 1)))
            toolbar.add_widget(ToolButton(
                text='[Save As]', on_tap=self._do_save,
                bg=(0.15, 0.42, 0.15, 1)))
            toolbar.add_widget(ToolButton(
                text='[Load]', on_tap=self._do_load,
                bg=(0.15, 0.30, 0.55, 1)))
            toolbar.add_widget(ToolButton(
                text='[Settings]', on_tap=self._do_settings,
                bg=(0.40, 0.28, 0.10, 1)))

            anchor.add_widget(toolbar)
            layout.add_widget(anchor)

        if parent_id is not None:
            layout.add_widget(BackButton(parent_id=parent_id, sm=sm))

        self.add_widget(layout)

    def _do_new(self):
        for screen in list(self._sm.screens):
            self._sm.remove_widget(screen)
        self._sm.add_widget(CanvasScreen(canvas_id='root',
                                         parent_id=None, sm=self._sm))
        self._sm.current = 'root'
        App.get_running_app()._current_file = None
        # no autosave — new canvas has no file yet

    def _do_save(self):
        def confirm(full_path):
            try:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                save_to_file(self._sm, full_path)
                App.get_running_app()._current_file = full_path
                InfoDialog(message=f'Saved:\n{full_path}').open()
            except Exception as e:
                InfoDialog(message=f'Save failed:\n{e}').open()
        app = App.get_running_app()
        cur = app._current_file
        default_name = os.path.splitext(os.path.basename(cur))[0] if cur else 'circles'
        FolderBrowserDialog(start_dir=get_work_dir(),
                            mode='save', on_confirm=confirm,
                            default_name=default_name).open()

    def _do_load(self):
        def confirm(full_path):
            try:
                load_from_file(full_path, self._sm)
                App.get_running_app()._current_file = full_path
                InfoDialog(message=f'Loaded:\n{full_path}').open()
            except Exception as e:
                InfoDialog(message=f'Load failed:\n{e}').open()
        FolderBrowserDialog(start_dir=get_work_dir(),
                            mode='load', on_confirm=confirm).open()

    def _do_settings(self):
        def confirm(chosen_dir):
            set_work_dir(chosen_dir)
            InfoDialog(message=f'Working directory:\n{chosen_dir}').open()
        FolderBrowserDialog(start_dir=get_work_dir(),
                            mode='dir', on_confirm=confirm).open()


# ── app ───────────────────────────────────────────────────────────────────────
class CirclesApp(App):
    def build(self):
        from kivy.config import Config
        Config.set('graphics', 'resizable', '1')
        Window.clearcolor = BG_COLOR
        self._current_file = None
        self.sm = ScreenManager()
        self.sm.add_widget(CanvasScreen(canvas_id='root',
                                        parent_id=None, sm=self.sm))
        return self.sm

    def on_start(self):
        # Request storage access on Android APK builds
        _request_android_permissions()
        # Small delay so permission dialog can resolve before we touch sdcard
        Clock.schedule_once(self._auto_load, 1.2)

    def _auto_load(self, dt):
        latest = latest_cir_in(get_work_dir())
        if latest:
            try:
                load_from_file(latest, self.sm)
                self._current_file = latest
            except Exception:
                pass

    def autosave(self):
        """Save to current file silently. Called after every user action."""
        if not self._current_file:
            self._current_file = os.path.join(get_work_dir(), 'default.cir')
        try:
            save_to_file(self.sm, self._current_file)
        except Exception:
            pass


if __name__ == '__main__':
    CirclesApp().run()
