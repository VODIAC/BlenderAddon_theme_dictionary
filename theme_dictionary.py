bl_info = {
    "name": "theme dictionary",
    "author": "61+",
    "version": (0, 6, 1),
    "blender": (5, 0, 0),
    "location": "Top Bar / Alt+C",
    "description": "Search for related theme color entries based on color or mouse area",
    "category": "Interface",
}

import colorsys
import math
import os
import tempfile
import time
import xml.etree.ElementTree as ET

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatVectorProperty, IntProperty, StringProperty
from bpy.types import AddonPreferences, Menu, Operator, PropertyGroup, UIList


ADDON_ID = __name__
BOUNDARY_THRESHOLD = 12
POPUP_WIDTH = 200
POPUP_LIST_ROWS = 8
HISTORY_TIMER_INTERVAL = 0.35
SIMILAR_TOLERANCE_DEFAULT = 16
FALLBACK_MATCH_LIMIT = 24
FALLBACK_MATCH_TOLERANCE = 56
CANDIDATE_PREVIEW_DELAY = 0.0
CANDIDATE_PREVIEW_INTERVAL = 0.04
CANDIDATE_PREVIEW_CYCLE = 1.0
CANDIDATE_PREVIEW_VALUE_AMPLITUDE = 0.60
addon_keymaps = []
_theme_snapshot = None
_theme_history = []
_theme_redo_history = []
_last_theme_state = None
_last_theme_token = None
_history_timer_running = False
_suspend_history = False
_pending_history_before = None
_pending_history_after = None
_pending_history_last_change_time = 0.0
_pending_history_token = None
_pending_history_is_similar_sync = False
_history_commit_delay = 0.8
_probe_runtime = {}
_similar_seed_candidates = []
_similar_seed_signature = None
_similar_seed_path = ""
_sample_refresh_pending = False
_sample_refresh_time = 0.0
_sample_refresh_timer_running = False
_syncing_similar_colors = False
_candidate_preview_path = ""
_candidate_preview_original = None
_candidate_preview_last_written = None
_candidate_preview_start_time = 0.0
_candidate_preview_last_draw_time = 0.0
_candidate_preview_timer_running = False
_candidate_preview_auto_disabled_sync = False
_locked_candidate_paths = set()


PROBE_MODE_ITEMS = (
    ("AREA", "\u533a\u57df\u989c\u8272", "\u6839\u636e\u9f20\u6807\u6240\u5728\u533a\u57df\u63a8\u8350\u4e3b\u9898\u989c\u8272"),
    ("SIMILAR", "\u76f8\u4f3c\u989c\u8272", "\u6839\u636e\u5f53\u524d\u533a\u57df\u5019\u9009\u8272\u68c0\u7d22\u5168\u5c40\u76f8\u4f3c\u989c\u8272"),
)


SEMANTIC_MAP = {
    "GLOBAL_BOUNDARY": [
        ("\u9762\u677f\u8fb9\u6846", "user_interface.wcol_regular.outline"),
        ("\u5de5\u5177\u8fb9\u6846", "user_interface.wcol_tool.outline"),
        ("\u83dc\u5355\u8fb9\u6846", "user_interface.wcol_menu.outline"),
        ("\u5de5\u5177\u63d0\u793a\u8fb9\u6846", "user_interface.wcol_tooltip.outline"),
        ("\u5217\u8868\u9879\u8fb9\u6846", "user_interface.wcol_list_item.outline"),
    ],
    "MENU_UI": [
        ("\u83dc\u5355\u80cc\u666f", "user_interface.wcol_menu.inner"),
        ("\u83dc\u5355\u6587\u5b57", "user_interface.wcol_menu.text"),
        ("\u83dc\u5355\u9ad8\u4eae", "user_interface.wcol_menu.item"),
        ("\u83dc\u5355\u8f6e\u5ed3", "user_interface.wcol_menu.outline"),
        ("\u5de5\u5177\u63d0\u793a\u80cc\u666f", "user_interface.wcol_tooltip.inner"),
        ("\u5de5\u5177\u63d0\u793a\u6587\u5b57", "user_interface.wcol_tooltip.text"),
    ],
    "VIEW_3D": [
        ("3D \u89c6\u56fe\u6e10\u53d8\u9876\u90e8", "view_3d.space.gradients.high_gradient"),
        ("3D \u89c6\u56fe\u6e10\u53d8\u5e95\u90e8", "view_3d.space.gradients.gradient"),
        ("3D \u7f51\u683c", "view_3d.grid"),
        ("3D \u4e3b\u7f51\u683c", "view_3d.grid_major"),
        ("3D \u5750\u6807\u8f74 X", "user_interface.axis_x"),
        ("3D \u5750\u6807\u8f74 Y", "user_interface.axis_y"),
        ("3D \u5750\u6807\u8f74 Z", "user_interface.axis_z"),
        ("\u9009\u4e2d\u7269\u4f53\u8f6e\u5ed3", "view_3d.object_selected"),
        ("\u6d3b\u52a8\u7269\u4f53\u9ad8\u4eae", "view_3d.object_active"),
        ("3D \u6807\u9898\u6587\u5b57", "view_3d.space.title"),
        ("3D \u9762\u677f\u6807\u9898", "view_3d.space.header"),
        ("3D \u9762\u677f\u6587\u5b57", "view_3d.space.text"),
        ("3D \u9762\u677f\u6587\u5b57\u9ad8\u4eae", "view_3d.space.text_hi"),
    ],
    "PROPERTIES": [
        ("\u5c5e\u6027\u7f16\u8f91\u5668\u80cc\u666f", "properties.space.back"),
        ("\u5c5e\u6027\u6807\u9898", "properties.space.header"),
        ("\u5c5e\u6027\u6587\u5b57", "properties.space.text"),
        ("\u5c5e\u6027\u6587\u5b57\u9ad8\u4eae", "properties.space.text_hi"),
        ("\u5c5e\u6027\u6309\u94ae", "user_interface.wcol_regular.inner"),
        ("\u5c5e\u6027\u6309\u94ae\u6587\u5b57", "user_interface.wcol_regular.text"),
    ],
    "OUTLINER": [
        ("\u5927\u7eb2\u80cc\u666f", "outliner.space.back"),
        ("\u5927\u7eb2\u6807\u9898", "outliner.space.header"),
        ("\u5927\u7eb2\u6587\u5b57", "outliner.space.text"),
        ("\u5927\u7eb2\u6587\u5b57\u9ad8\u4eae", "outliner.space.text_hi"),
        ("\u5927\u7eb2\u884c\u9ad8\u4eae", "outliner.match"),
    ],
    "NODE_EDITOR": [
        ("\u8282\u70b9\u80cc\u666f", "node_editor.space.back"),
        ("\u8282\u70b9\u6807\u9898", "node_editor.space.header"),
        ("\u8282\u70b9\u6587\u5b57", "node_editor.space.text"),
        ("\u8282\u70b9\u6587\u5b57\u9ad8\u4eae", "node_editor.space.text_hi"),
        ("\u8282\u70b9\u7f51\u683c", "node_editor.grid"),
        ("\u8282\u70b9\u8fde\u63a5\u7ebf", "node_editor.wire"),
    ],
}


SHORTCUT_KEYS = [(chr(code), chr(code), "") for code in range(ord("A"), ord("Z") + 1)]


def addon_preferences():
    addon = bpy.context.preferences.addons.get(ADDON_ID)
    return addon.preferences if addon else None


def theme_root():
    prefs = bpy.context.preferences
    themes = getattr(prefs, "themes", None)
    if not themes:
        return None
    try:
        return themes[0]
    except Exception:
        return None


def iter_theme_paths(base, prefix=""):
    if base is None:
        return
    rna = getattr(base, "bl_rna", None)
    if rna is None:
        return
    for prop in rna.properties:
        ident = prop.identifier
        if ident == "rna_type":
            continue
        try:
            value = getattr(base, ident)
        except Exception:
            continue
        path = f"{prefix}.{ident}" if prefix else ident
        ptype = getattr(prop, "type", "")
        subtype = getattr(prop, "subtype", "")
        is_color = (
            ptype in {"FLOAT", "INT"}
            and getattr(prop, "is_array", False)
            and getattr(prop, "array_length", 0) in {3, 4}
            and subtype in {"COLOR", "COLOR_GAMMA"}
        )
        if is_color and not prop.is_readonly:
            yield path, value
        elif ptype == "POINTER" and value is not None:
            yield from iter_theme_paths(value, path)


def iter_theme_mode_color_groups(base=None, prefix=""):
    if base is None:
        base = theme_root()
    if base is None:
        return
    rna = getattr(base, "bl_rna", None)
    if rna is None:
        return

    enum_props = []
    color_props = []
    pointer_props = []
    for prop in rna.properties:
        ident = prop.identifier
        if ident == "rna_type":
            continue
        try:
            value = getattr(base, ident)
        except Exception:
            continue
        path = f"{prefix}.{ident}" if prefix else ident
        ptype = getattr(prop, "type", "")
        subtype = getattr(prop, "subtype", "")
        is_color = (
            ptype in {"FLOAT", "INT"}
            and getattr(prop, "is_array", False)
            and getattr(prop, "array_length", 0) in {3, 4}
            and subtype in {"COLOR", "COLOR_GAMMA"}
        )
        if ptype == "ENUM" and not prop.is_readonly:
            enum_props.append({"label": prop.name or ident, "path": path})
        elif is_color and not prop.is_readonly:
            color_props.append({"label": prop.name or ident, "path": path})
        elif ptype == "POINTER" and value is not None:
            pointer_props.append((value, path))

    if enum_props and color_props:
        yield {
            "label": getattr(rna, "name", "") or prefix.split(".")[-1],
            "prefix": prefix,
            "enums": enum_props,
            "colors": color_props,
        }
    for value, path in pointer_props:
        yield from iter_theme_mode_color_groups(value, path)


def build_theme_index():
    root = theme_root()
    if root is None:
        return {}
    return {path: value for path, value in iter_theme_paths(root)}


def build_mode_color_groups():
    return list(iter_theme_mode_color_groups())


class ThemeFieldScanner:
    @staticmethod
    def scan():
        return build_theme_index()


def resolve_theme_path(path):
    root = theme_root()
    if root is None or not path:
        return None, None
    current = root
    parts = path.split(".")
    for attr in parts[:-1]:
        if not hasattr(current, attr):
            return None, None
        current = getattr(current, attr)
    attr = parts[-1]
    if not hasattr(current, attr):
        return None, None
    return current, attr


def color_to_list(value):
    try:
        return [float(channel) for channel in value]
    except Exception:
        return None


def clamp(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, value))


def clamp_hsv_triplet(hue, sat, val):
    return (
        clamp(hue, 0.0, 1.0),
        clamp(sat, 0.0, 1.0),
        clamp(val, 0.0, 1.0),
    )


def color_signature(value):
    color = color_to_list(value)
    if color is None:
        return None
    return tuple(max(0, min(255, int(round(channel * 255)))) for channel in color)


def signature_from_color(color):
    try:
        channels = list(color)
    except Exception:
        return None
    if len(channels) < 3:
        return None
    return tuple(max(0, min(255, int(round(channel * 255)))) for channel in channels[:4])


def color_from_signature(signature):
    if signature is None or len(signature) < 3:
        return None
    alpha = signature[3] if len(signature) >= 4 else 255
    return tuple(channel / 255.0 for channel in (signature[0], signature[1], signature[2], alpha))


def color_priority(color):
    red, green, blue = color[:3]
    hue, sat, val = colorsys.rgb_to_hsv(red, green, blue)
    return sat * 3.2 + abs(val - 0.5) * 0.25 + val * 0.08


def append_sample_log(message):
    log_path = os.path.join(tempfile.gettempdir(), "theme_probe_sample_debug.log")
    try:
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%H:%M:%S')} {message}\n")
    except Exception:
        pass


def best_color_around(pixels, width, height, center_x, center_y, radius):
    best = None
    best_score = -1e9
    cx = max(0, min(width - 1, int(center_x)))
    cy = max(0, min(height - 1, int(center_y)))
    center_index = (cy * width + cx) * 4
    center = tuple(pixels[center_index:center_index + 4]) if center_index + 3 < len(pixels) else (0.0, 0.0, 0.0, 1.0)
    for py in range(max(0, cy - radius), min(height, cy + radius + 1)):
        for px in range(max(0, cx - radius), min(width, cx + radius + 1)):
            index = (py * width + px) * 4
            color = tuple(pixels[index:index + 4])
            if len(color) != 4:
                continue
            distance = abs(px - cx) + abs(py - cy)
            score = color_priority(color) * 10.0 - distance * 0.2 - sum(abs(color[i] - center[i]) for i in range(3)) * 0.25
            if score > best_score:
                best_score = score
                best = color
    return best, best_score


def sample_screen_color(context, mouse_x, mouse_y, radius=5):
    filepath = os.path.join(tempfile.gettempdir(), "theme_probe_sample.png")
    image = None
    try:
        bpy.ops.screen.screenshot(filepath=filepath)
        image = bpy.data.images.load(filepath, check_existing=False)
        width, height = image.size
        if width <= 0 or height <= 0:
            return None

        win_w = max(1, int(getattr(context.window, "width", 1)))
        win_h = max(1, int(getattr(context.window, "height", 1)))
        scale_x = width / float(win_w)
        scale_y = height / float(win_h)
        append_sample_log(
            f"window={win_w}x{win_h} image={width}x{height} mouse=({mouse_x},{mouse_y}) scale=({scale_x:.3f},{scale_y:.3f})"
        )

        pixels = image.pixels[:]
        x_scaled = int(mouse_x * scale_x)
        y_scaled = int(mouse_y * scale_y)
        candidates = [
            (x_scaled, height - 1 - y_scaled, "scaled_flip"),
            (x_scaled, y_scaled, "scaled_raw"),
            (int(mouse_x), height - 1 - int(mouse_y), "raw_flip"),
            (int(mouse_x), int(mouse_y), "raw_raw"),
        ]
        best_color = None
        best_score = -1e9
        best_tag = ""
        for cx, cy, tag in candidates:
            color, score = best_color_around(pixels, width, height, cx, cy, radius)
            append_sample_log(f"candidate={tag} point=({cx},{cy}) score={score:.3f} color={color}")
            if color is not None and score > best_score:
                best_score = score
                best_color = color
                best_tag = tag
        append_sample_log(f"selected={best_tag} score={best_score:.3f} color={best_color}")
        return best_color
    except Exception as exc:
        print(f"Theme Probe screen sample failed: {exc}")
        append_sample_log(f"sample_failed: {exc}")
        return None
    finally:
        if image is not None:
            try:
                bpy.data.images.remove(image)
            except Exception:
                pass
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass


def color_hex(signature):
    if signature is None:
        return ""
    if len(signature) >= 4:
        return "#{:02X}{:02X}{:02X}{:02X}".format(*signature[:4])
    if len(signature) >= 3:
        return "#{:02X}{:02X}{:02X}".format(*signature[:3])
    return ""


def color_tolerance_distance(first, second):
    if first is None or second is None:
        return None
    channels = min(len(first), len(second))
    if channels == 0:
        return None
    return max(abs(first[index] - second[index]) for index in range(channels))


def color_match_distance(signature, seed_signature, tolerance):
    if signature is None or seed_signature is None:
        return None
    if len(signature) < 3 or len(seed_signature) < 3:
        return None

    rgb_delta = max(abs(signature[index] - seed_signature[index]) for index in range(3))
    if tolerance <= 0:
        return rgb_delta if rgb_delta <= 1 else None
    if rgb_delta > tolerance:
        return None

    rgb = [channel / 255.0 for channel in signature[:3]]
    seed_rgb = [channel / 255.0 for channel in seed_signature[:3]]
    hue, sat, val = colorsys.rgb_to_hsv(*rgb)
    seed_hue, seed_sat, seed_val = colorsys.rgb_to_hsv(*seed_rgb)
    normalized = tolerance / 255.0
    hue_delta = min(abs(hue - seed_hue), 1.0 - abs(hue - seed_hue)) * 360.0
    sat_delta = abs(sat - seed_sat)
    val_delta = abs(val - seed_val)

    if sat > 0.08 and seed_sat > 0.08 and hue_delta > normalized * 60.0:
        return None
    if sat_delta > normalized:
        return None
    if val_delta > normalized:
        return None
    return rgb_delta + hue_delta / 6.0 + sat_delta * 32.0 + val_delta * 64.0


def visual_color_distance(signature, seed_signature):
    if signature is None or seed_signature is None:
        return None
    if len(signature) < 3 or len(seed_signature) < 3:
        return None
    rgb_delta = [abs(signature[index] - seed_signature[index]) for index in range(3)]
    return max(rgb_delta) + sum(rgb_delta) / 6.0


def semantic_label_for_path(path):
    for entries in SEMANTIC_MAP.values():
        for label_text, entry_path in entries:
            if entry_path == path:
                return label_text
    return path.split(".")[-1]


def get_theme_value(path):
    owner, attr = resolve_theme_path(path)
    if owner is None:
        return None
    try:
        value = getattr(owner, attr)
    except Exception:
        return None
    color = color_to_list(value)
    if color is not None:
        return tuple(round(channel, 6) for channel in color)
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception:
        return None


def theme_token():
    root = theme_root()
    if root is None:
        return None
    return (
        getattr(root, "name", "") or "active-theme",
        getattr(root, "filepath", "") or "",
    )


def snapshot_theme_values():
    values = {}
    for path in build_theme_index():
        values[path] = get_theme_value(path)
    for group in build_mode_color_groups():
        for item in group["enums"]:
            values[item["path"]] = get_theme_value(item["path"])
    return values


def restore_theme_values(values):
    global _suspend_history
    _suspend_history = True
    try:
        for path, value in values.items():
            owner, attr = resolve_theme_path(path)
            if owner is None or value is None:
                continue
            try:
                setattr(owner, attr, value)
            except Exception:
                pass
    finally:
        _suspend_history = False
    tag_redraw_all()


def changed_value_count(previous, current):
    if previous is None or current is None:
        return 0
    keys = set(previous.keys()) | set(current.keys())
    return sum(1 for key in keys if previous.get(key) != current.get(key))


def _push_undo_state(state):
    if state is None:
        return
    _theme_history.append(dict(state))
    del _theme_history[:-50]


def _push_redo_state(state):
    if state is None:
        return
    _theme_redo_history.append(dict(state))
    del _theme_redo_history[:-50]


def _clear_history_stacks():
    _theme_history.clear()
    _theme_redo_history.clear()


def _clear_pending_history():
    global _pending_history_before, _pending_history_after, _pending_history_last_change_time, _pending_history_token
    global _pending_history_is_similar_sync
    _pending_history_before = None
    _pending_history_after = None
    _pending_history_last_change_time = 0.0
    _pending_history_token = None
    _pending_history_is_similar_sync = False


def commit_pending_theme_history(force=False):
    global _pending_history_before, _pending_history_after, _pending_history_last_change_time, _pending_history_token
    if _pending_history_before is None or _pending_history_after is None:
        return False

    current_token = theme_token()
    if _pending_history_token != current_token:
        _clear_pending_history()
        return False

    if not force and (time.time() - _pending_history_last_change_time) < _history_commit_delay:
        return False

    changed_count = changed_value_count(_pending_history_before, _pending_history_after)
    if changed_count and (
        _pending_history_is_similar_sync
        or changed_count <= max(24, len(_pending_history_after) // 4)
    ):
        _push_undo_state(_pending_history_before)
        _theme_redo_history.clear()

    _clear_pending_history()
    return True


def reset_theme_history(context=None):
    global _last_theme_state, _last_theme_token
    _clear_history_stacks()
    _clear_pending_history()
    _last_theme_state = snapshot_theme_values()
    _last_theme_token = theme_token()
    if context is not None:
        tag_redraw_all()


def sync_theme_history_to_current_state():
    global _last_theme_state, _last_theme_token
    _clear_pending_history()
    _last_theme_state = snapshot_theme_values()
    _last_theme_token = theme_token()


def restore_theme_state_for_history(values):
    restore_theme_values(values)


def monitor_theme_history():
    global _last_theme_state, _last_theme_token, _history_timer_running
    global _pending_history_before, _pending_history_after, _pending_history_last_change_time, _pending_history_token
    global _pending_history_is_similar_sync
    if not _history_timer_running:
        return None
    if _suspend_history:
        return HISTORY_TIMER_INTERVAL

    commit_pending_theme_history(force=False)

    current_token = theme_token()
    raw_current_state = snapshot_theme_values()
    preview_state_active = state_has_candidate_preview_value(raw_current_state)
    current_state = normalized_candidate_preview_state(raw_current_state)
    if _last_theme_state is None:
        _last_theme_state = current_state
        _last_theme_token = current_token
        _clear_pending_history()
        return HISTORY_TIMER_INTERVAL

    if current_token != _last_theme_token:
        _clear_history_stacks()
        _clear_pending_history()
        _last_theme_state = current_state
        _last_theme_token = current_token
        return HISTORY_TIMER_INTERVAL

    changed_count = changed_value_count(_last_theme_state, current_state)
    if changed_count:
        similar_sync_applied = False
        if not preview_state_active:
            current_state, similar_sync_applied = apply_similar_hsv_offset_from_change(bpy.context, _last_theme_state, current_state)
        changed_count = changed_value_count(_last_theme_state, current_state)
        if changed_count > max(24, len(current_state) // 4) and not similar_sync_applied:
            _clear_history_stacks()
            _clear_pending_history()
        else:
            if _pending_history_before is None:
                _pending_history_before = dict(_last_theme_state)
            _pending_history_after = dict(current_state)
            _pending_history_last_change_time = time.time()
            _pending_history_token = current_token
            _pending_history_is_similar_sync = _pending_history_is_similar_sync or similar_sync_applied
        _last_theme_state = current_state

    commit_pending_theme_history(force=False)
    return HISTORY_TIMER_INTERVAL


def ensure_history_timer():
    global _history_timer_running, _last_theme_state, _last_theme_token
    if _last_theme_state is None:
        _last_theme_state = snapshot_theme_values()
        _last_theme_token = theme_token()
    if not _history_timer_running:
        _history_timer_running = True
        bpy.app.timers.register(monitor_theme_history, first_interval=HISTORY_TIMER_INTERVAL)


def stop_history_timer():
    global _history_timer_running
    _history_timer_running = False


def undo_theme_change():
    global _last_theme_state, _last_theme_token
    restore_candidate_preview()
    commit_pending_theme_history(force=True)
    current_token = theme_token()
    current_state = snapshot_theme_values()
    if current_token != _last_theme_token:
        reset_theme_history()
        return False
    if _last_theme_state is not None and changed_value_count(_last_theme_state, current_state):
        _push_undo_state(_last_theme_state)
        _last_theme_state = current_state
    if not _theme_history:
        return False
    previous = _theme_history.pop()
    _push_redo_state(current_state)
    restore_theme_state_for_history(previous)
    _last_theme_state = snapshot_theme_values()
    return True


def redo_theme_change():
    global _last_theme_state, _last_theme_token
    restore_candidate_preview()
    commit_pending_theme_history(force=True)
    current_token = theme_token()
    current_state = snapshot_theme_values()
    if current_token != _last_theme_token:
        reset_theme_history()
        return False
    if not _theme_redo_history:
        return False
    next_state = _theme_redo_history.pop()
    _push_undo_state(current_state)
    restore_theme_state_for_history(next_state)
    _last_theme_state = snapshot_theme_values()
    return True


def candidate_color_paths_from_window_manager(wm):
    paths = []
    for item in getattr(wm, "theme_probe_candidates", []):
        path = getattr(item, "path", "")
        if path and path not in paths and is_color_theme_path(path):
            paths.append(path)
    return paths


def candidate_path_locked(path):
    return bool(path and path in _locked_candidate_paths)


def candidate_path_lock_icon(path):
    return "LOCKED" if candidate_path_locked(path) else "UNLOCKED"


def unlocked_candidate_color_paths_from_window_manager(wm):
    return [
        path for path in candidate_color_paths_from_window_manager(wm)
        if not candidate_path_locked(path)
    ]


def similar_sync_enabled(context):
    if context is None:
        return True
    wm = context.window_manager
    return bool(getattr(wm, "theme_probe_sync_similar", True))


def auto_disable_similar_sync_for_preview(context):
    global _candidate_preview_auto_disabled_sync
    if context is None:
        return
    wm = context.window_manager
    if (
        getattr(wm, "theme_probe_mode", "AREA") == "SIMILAR"
        and getattr(wm, "theme_probe_sync_similar", True)
    ):
        wm.theme_probe_sync_similar = False
        _candidate_preview_auto_disabled_sync = True


def restore_auto_disabled_similar_sync(context):
    global _candidate_preview_auto_disabled_sync
    if not _candidate_preview_auto_disabled_sync:
        return False
    if context is not None:
        context.window_manager.theme_probe_sync_similar = True
    _candidate_preview_auto_disabled_sync = False
    return True


def hsv_offset_color(color, hsv_delta):
    if color is None or len(color) < 3:
        return None
    hue, sat, val = colorsys.rgb_to_hsv(*color[:3])
    hue, sat, val = clamp_hsv_triplet(
        hue + hsv_delta[0],
        sat + hsv_delta[1],
        val + hsv_delta[2],
    )
    red, green, blue = colorsys.hsv_to_rgb(hue, sat, val)
    result = [clamp(red), clamp(green), clamp(blue)]
    if len(color) >= 4:
        result.append(clamp(color[3]))
    return tuple(result)


def value_offset_color(color, value_delta):
    if color is None or len(color) < 3:
        return None
    hue, sat, val = colorsys.rgb_to_hsv(*color[:3])
    red, green, blue = colorsys.hsv_to_rgb(hue, sat, clamp(val + value_delta))
    result = [clamp(red), clamp(green), clamp(blue)]
    if len(color) >= 4:
        result.append(clamp(color[3]))
    return tuple(result)


def preview_pulse_color(color, phase):
    if color is None or len(color) < 3:
        return None
    hue, sat, val = colorsys.rgb_to_hsv(*color[:3])
    span = CANDIDATE_PREVIEW_VALUE_AMPLITUDE
    half_span = span * 0.5
    lower = val - half_span
    upper = val + half_span
    if upper > 1.0:
        upper = 1.0
        lower = max(0.0, upper - span)
    elif lower < 0.0:
        lower = 0.0
        upper = min(1.0, lower + span)
    center = (lower + upper) * 0.5
    amplitude = (upper - lower) * 0.5
    pulse_value = center + math.cos(phase * math.tau) * amplitude
    red, green, blue = colorsys.hsv_to_rgb(hue, sat, clamp(pulse_value))
    result = [clamp(red), clamp(green), clamp(blue)]
    if len(color) >= 4:
        result.append(clamp(color[3]))
    return tuple(result)


def colors_close(first, second, epsilon=0.0005):
    if first is None or second is None:
        return False
    if len(first) != len(second):
        return False
    return all(abs(first[index] - second[index]) <= epsilon for index in range(len(first)))


def active_candidate_color_path(context):
    wm = context.window_manager
    items = getattr(wm, "theme_probe_candidates", None)
    if not items:
        return ""
    index = getattr(wm, "theme_probe_candidate_preview_index", -1)
    if index < 0 or index >= len(items):
        return ""
    path = getattr(items[index], "path", "")
    if candidate_path_locked(path):
        return ""
    return path if is_color_theme_path(path) else ""


def restore_candidate_preview():
    global _candidate_preview_path, _candidate_preview_original, _candidate_preview_last_written, _candidate_preview_start_time
    global _candidate_preview_last_draw_time
    if _candidate_preview_path and _candidate_preview_original is not None:
        current = color_value_for_path(_candidate_preview_path)
        if _candidate_preview_last_written is None or colors_close(current, _candidate_preview_last_written):
            set_color_value_for_path_without_history(_candidate_preview_path, _candidate_preview_original)
    _candidate_preview_path = ""
    _candidate_preview_original = None
    _candidate_preview_last_written = None
    _candidate_preview_start_time = 0.0
    _candidate_preview_last_draw_time = 0.0


def stop_candidate_preview_from_mouse(context):
    restore_candidate_preview()
    if _candidate_preview_auto_disabled_sync:
        sync_theme_history_to_current_state()
    restored_sync = restore_auto_disabled_similar_sync(context)
    if context is not None:
        context.window_manager.theme_probe_candidate_preview_index = -1
    return restored_sync


def set_color_value_for_path_without_history(path, color):
    global _suspend_history
    was_suspended = _suspend_history
    _suspend_history = True
    try:
        return set_color_value_for_path(path, color)
    finally:
        _suspend_history = was_suspended


def normalized_candidate_preview_state(state):
    if (
        state is None
        or not _candidate_preview_path
        or _candidate_preview_original is None
        or _candidate_preview_last_written is None
    ):
        return state
    current_value = state.get(_candidate_preview_path)
    if colors_close(current_value, _candidate_preview_last_written):
        normalized = dict(state)
        normalized[_candidate_preview_path] = tuple(round(channel, 6) for channel in _candidate_preview_original)
        return normalized
    return state


def state_has_candidate_preview_value(state):
    if (
        state is None
        or not _candidate_preview_path
    ):
        return False
    current_value = state.get(_candidate_preview_path)
    if _candidate_preview_last_written is not None and colors_close(current_value, _candidate_preview_last_written):
        return True
    return False


def schedule_candidate_preview(context):
    global _candidate_preview_path, _candidate_preview_original, _candidate_preview_start_time
    global _candidate_preview_last_draw_time, _candidate_preview_timer_running, _candidate_preview_last_written
    path = active_candidate_color_path(context)
    now = time.time()
    _candidate_preview_last_draw_time = now
    if not path:
        restore_candidate_preview()
        return
    if path != _candidate_preview_path:
        restore_candidate_preview()
        _candidate_preview_path = path
        _candidate_preview_original = color_value_for_path(path)
        _candidate_preview_last_written = _candidate_preview_original
        _candidate_preview_start_time = now
        _candidate_preview_last_draw_time = now
    if not _candidate_preview_timer_running:
        _candidate_preview_timer_running = True
        bpy.app.timers.register(candidate_preview_timer, first_interval=CANDIDATE_PREVIEW_INTERVAL)


def candidate_preview_timer():
    global _candidate_preview_timer_running, _candidate_preview_last_written
    if not _candidate_preview_path or _candidate_preview_original is None:
        _candidate_preview_timer_running = False
        return None

    now = time.time()
    if active_candidate_color_path(bpy.context) != _candidate_preview_path:
        restore_candidate_preview()
        _candidate_preview_timer_running = False
        tag_redraw_all()
        return None

    elapsed = now - _candidate_preview_start_time
    if elapsed < CANDIDATE_PREVIEW_DELAY:
        return CANDIDATE_PREVIEW_INTERVAL

    current_color = color_value_for_path(_candidate_preview_path)
    if _candidate_preview_last_written is not None and not colors_close(current_color, _candidate_preview_last_written):
        restore_candidate_preview()
        _candidate_preview_timer_running = False
        tag_redraw_all()
        return None

    phase = (elapsed - CANDIDATE_PREVIEW_DELAY) / CANDIDATE_PREVIEW_CYCLE
    preview_color = preview_pulse_color(_candidate_preview_original, phase)
    if preview_color is not None:
        set_color_value_for_path_without_history(_candidate_preview_path, preview_color)
        _candidate_preview_last_written = color_value_for_path(_candidate_preview_path)
        tag_redraw_all()
    return CANDIDATE_PREVIEW_INTERVAL


def update_candidate_index(self, context):
    if context is not None:
        wm = context.window_manager
        preview_index = getattr(wm, "theme_probe_candidate_preview_index", -1)
        active_index = getattr(wm, "theme_probe_candidate_index", -1)
        items = getattr(wm, "theme_probe_candidates", None)
        if preview_index >= 0:
            if items and 0 <= active_index < len(items):
                if preview_index != active_index:
                    restore_candidate_preview()
                    wm.theme_probe_candidate_preview_index = active_index
            else:
                restore_candidate_preview()
                wm.theme_probe_candidate_preview_index = -1
        schedule_candidate_preview(context)


def apply_similar_hsv_offset_from_change(context, previous_state, current_state):
    global _syncing_similar_colors
    if _syncing_similar_colors:
        return current_state, False
    if context is None:
        return current_state, False

    wm = context.window_manager
    if getattr(wm, "theme_probe_mode", "AREA") != "SIMILAR":
        return current_state, False
    if not similar_sync_enabled(context):
        return current_state, False

    candidate_paths = unlocked_candidate_color_paths_from_window_manager(wm)
    if len(candidate_paths) < 2:
        return current_state, False

    changed_paths = [
        path for path in candidate_paths
        if previous_state.get(path) != current_state.get(path)
        and previous_state.get(path) is not None
        and current_state.get(path) is not None
    ]
    if len(changed_paths) != 1:
        return current_state, False

    source_path = changed_paths[0]
    source_before = previous_state.get(source_path)
    source_after = current_state.get(source_path)
    if len(source_before) < 3 or len(source_after) < 3:
        return current_state, False

    before_hsv = colorsys.rgb_to_hsv(*source_before[:3])
    after_hsv = colorsys.rgb_to_hsv(*source_after[:3])
    hsv_delta = tuple(after_hsv[index] - before_hsv[index] for index in range(3))
    if not any(abs(delta) > 1e-9 for delta in hsv_delta):
        return current_state, False

    updated_state = dict(current_state)
    _syncing_similar_colors = True
    try:
        for path in candidate_paths:
            if path == source_path:
                continue
            original_color = previous_state.get(path)
            if original_color is None:
                continue
            shifted_color = hsv_offset_color(original_color, hsv_delta)
            if shifted_color is None:
                continue
            if set_color_value_for_path(path, shifted_color):
                updated_state[path] = get_theme_value(path)
    finally:
        _syncing_similar_colors = False

    similar_sync_applied = updated_state != current_state
    if similar_sync_applied:
        tag_redraw_all()
    return updated_state, similar_sync_applied


def ensure_snapshot():
    global _theme_snapshot
    if _theme_snapshot is not None:
        return
    refresh_snapshot()


def refresh_snapshot():
    global _theme_snapshot
    snapshot = {}
    for path, value in build_theme_index().items():
        color = color_to_list(value)
        if color is not None:
            snapshot[path] = color
    _theme_snapshot = snapshot


def restore_snapshot():
    if not _theme_snapshot:
        return False
    for path, color in _theme_snapshot.items():
        owner, attr = resolve_theme_path(path)
        if owner is None:
            continue
        try:
            setattr(owner, attr, color)
        except Exception:
            pass
    tag_redraw_all()
    return True


class ThemeSnapshotManager:
    @staticmethod
    def ensure_snapshot():
        ensure_snapshot()

    @staticmethod
    def restore():
        return restore_snapshot()


def tag_redraw_all():
    wm = bpy.context.window_manager
    for window in wm.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            area.tag_redraw()


def point_inside_region(area, region, x, y):
    boxes = (
        (region.x, region.y, region.width, region.height),
        (area.x + region.x, area.y + region.y, region.width, region.height),
    )
    return any(rx <= x <= rx + width and ry <= y <= ry + height for rx, ry, width, height in boxes)


def region_priority(region):
    priorities = {
        "HEADER": 0,
        "TOOL_HEADER": 1,
        "TOOLS": 2,
        "UI": 3,
        "NAVIGATION_BAR": 4,
        "HUD": 5,
        "WINDOW": 20,
    }
    return priorities.get(region.type, 10)


def find_area_region(screen, mouse_x, mouse_y):
    for area in screen.areas:
        if area.x <= mouse_x <= area.x + area.width and area.y <= mouse_y <= area.y + area.height:
            matching_regions = []
            for region in area.regions:
                if region.width > 1 and region.height > 1 and point_inside_region(area, region, mouse_x, mouse_y):
                    matching_regions.append(region)
            if matching_regions:
                matching_regions.sort(key=region_priority)
                return area, matching_regions[0]
            return area, None
    return None, None


def screen_top_area_type(screen, mouse_y):
    if screen is None:
        return ""
    try:
        top_area = max(screen.areas, key=lambda item: item.y + item.height)
    except ValueError:
        return ""
    if mouse_y >= top_area.y and top_area.type in {"TOPBAR", "STATUSBAR"}:
        return top_area.type
    return ""


def classify_probe_zone(screen, area, region, mouse_x, mouse_y):
    if area is None:
        return "NONE"
    if area.type == "TOPBAR":
        return "TOPBAR"
    top_type = screen_top_area_type(screen, mouse_y)
    if top_type == "TOPBAR":
        return "TOPBAR"
    if area.type == "VIEW_3D":
        region_type = region.type if region else ""
        if region_type == "HEADER":
            return "VIEW_3D_HEADER"
        if region_type == "TOOL_HEADER":
            return "VIEW_3D_TOOL_HEADER"
        if region_type == "TOOLS":
            return "VIEW_3D_TOOLBAR"
        if region_type == "UI":
            return "VIEW_3D_SIDEBAR"
        if region_type == "WINDOW":
            return "VIEW_3D_CONTENT"
    return f"{area.type}_{region.type}" if region else area.type


def display_zone_label(zone):
    labels = {
        "TOPBAR": "\u9876\u90e8\u4e3b\u83dc\u5355/\u5de5\u4f5c\u533a\u680f",
        "VIEW_3D_HEADER": "3D View Header",
        "VIEW_3D_TOOL_HEADER": "3D View Tool Header",
        "VIEW_3D_TOOLBAR": "3D View \u5de6\u4fa7\u5de5\u5177\u680f",
        "VIEW_3D_SIDEBAR": "3D View \u53f3\u4fa7 Sidebar",
        "VIEW_3D_CONTENT": "\u7eaf 3D View \u5185\u5bb9\u533a",
        "FALLBACK_TOP_CHROME": "\u9876\u90e8\u754c\u9762\u533a",
        "FALLBACK_BOTTOM_STATUS": "\u5e95\u90e8\u72b6\u6001\u680f",
        "FALLBACK_AREA_SEPARATOR": "\u533a\u57df\u5206\u9694/\u8fb9\u754c",
        "FALLBACK_SCREEN": "\u622a\u56fe\u53cd\u67e5\u533a",
    }
    return labels.get(zone, zone)


def screen_area_bounds(screen):
    areas = list(getattr(screen, "areas", []))
    if not areas:
        return None
    return {
        "left": min(area.x for area in areas),
        "right": max(area.x + area.width for area in areas),
        "bottom": min(area.y for area in areas),
        "top": max(area.y + area.height for area in areas),
    }


def distance_to_area(area, mouse_x, mouse_y):
    left = area.x
    right = area.x + area.width
    bottom = area.y
    top = area.y + area.height
    dx = max(left - mouse_x, 0, mouse_x - right)
    dy = max(bottom - mouse_y, 0, mouse_y - top)
    return dx + dy


def nearest_screen_area(screen, mouse_x, mouse_y):
    areas = list(getattr(screen, "areas", []))
    if not areas:
        return None
    return min(areas, key=lambda area: distance_to_area(area, mouse_x, mouse_y))


def boundary_flags_from_point(area, mouse_x, mouse_y):
    if area is None:
        return {}
    distances = {
        "left": abs(mouse_x - area.x),
        "right": abs(mouse_x - (area.x + area.width)),
        "bottom": abs(mouse_y - area.y),
        "top": abs(mouse_y - (area.y + area.height)),
    }
    nearest = min(distances, key=distances.get)
    return {
        "left": nearest == "left",
        "right": nearest == "right",
        "bottom": nearest == "bottom",
        "top": nearest == "top",
        "near_any": True,
    }


def classify_fallback_zone(screen, mouse_x, mouse_y, nearest_area):
    bounds = screen_area_bounds(screen)
    if bounds is None:
        return "FALLBACK_SCREEN"
    if mouse_y >= bounds["top"]:
        return "FALLBACK_TOP_CHROME"
    if mouse_y <= bounds["bottom"]:
        return "FALLBACK_BOTTOM_STATUS"
    if nearest_area is not None:
        if nearest_area.type == "TOPBAR":
            return "FALLBACK_TOP_CHROME"
        if nearest_area.type == "STATUSBAR":
            return "FALLBACK_BOTTOM_STATUS"
    return "FALLBACK_AREA_SEPARATOR"


def fallback_preferred_groups(zone, nearest_area):
    groups = []
    if zone == "FALLBACK_TOP_CHROME":
        groups.extend(["MENU_UI", "GLOBAL_BOUNDARY"])
    elif zone == "FALLBACK_BOTTOM_STATUS":
        groups.extend(["MENU_UI", "GLOBAL_BOUNDARY"])
    elif zone == "FALLBACK_AREA_SEPARATOR":
        groups.extend(["GLOBAL_BOUNDARY", "MENU_UI"])
    if nearest_area is not None:
        groups.append(nearest_area.type)
    return groups


def semantic_paths_for_groups(groups):
    paths = []
    for group in groups:
        for _label, path in SEMANTIC_MAP.get(group, []):
            if path not in paths:
                paths.append(path)
    return paths


def collect_visual_color_candidates(sample_color, zone, nearest_area=None):
    seed_signature = signature_from_color(sample_color)
    if seed_signature is None:
        return []
    preferred_paths = semantic_paths_for_groups(fallback_preferred_groups(zone, nearest_area))
    preferred_index = {path: index for index, path in enumerate(preferred_paths)}
    matches = []
    for path, value in build_theme_index().items():
        signature = color_signature(value)
        distance = visual_color_distance(signature, seed_signature)
        if distance is None or distance > FALLBACK_MATCH_TOLERANCE:
            continue
        semantic_bonus = 0.0
        if path in preferred_index:
            semantic_bonus = 18.0 - min(12.0, preferred_index[path] * 1.5)
        matches.append({
            "label": semantic_label_for_path(path),
            "path": path,
            "distance": max(0.0, distance - semantic_bonus),
        })
    matches.sort(key=lambda item: (item["distance"], item["path"]))
    return matches[:FALLBACK_MATCH_LIMIT]


def boundary_flags(area, mouse_x, mouse_y):
    if area is None:
        return {}
    return {
        "left": abs(mouse_x - area.x) <= BOUNDARY_THRESHOLD,
        "right": abs(mouse_x - (area.x + area.width)) <= BOUNDARY_THRESHOLD,
        "bottom": abs(mouse_y - area.y) <= BOUNDARY_THRESHOLD,
        "top": abs(mouse_y - (area.y + area.height)) <= BOUNDARY_THRESHOLD,
        "near_any": (
            abs(mouse_x - area.x) <= BOUNDARY_THRESHOLD
            or abs(mouse_x - (area.x + area.width)) <= BOUNDARY_THRESHOLD
            or abs(mouse_y - area.y) <= BOUNDARY_THRESHOLD
            or abs(mouse_y - (area.y + area.height)) <= BOUNDARY_THRESHOLD
        ),
    }


def collect_candidates(area, region):
    theme_index = build_theme_index()
    groups = []
    prefs = addon_preferences()
    assist_enabled = prefs is None or prefs.enable_current_screen_assist
    zone = _probe_runtime.get("zone", "")
    if zone in {"TOPBAR", "VIEW_3D_HEADER", "VIEW_3D_TOOL_HEADER"}:
        groups.append("MENU_UI")
    elif zone in {"VIEW_3D_TOOLBAR", "VIEW_3D_SIDEBAR"}:
        groups.extend(["MENU_UI", "PROPERTIES"])
    if region and region.type in {"HEADER", "TOOL_HEADER", "NAVIGATION_BAR", "HUD", "MENU"}:
        groups.append("MENU_UI")
    if area is not None:
        groups.append(area.type)
    if assist_enabled and _probe_runtime.get("boundary", {}).get("near_any", False):
        groups.append("GLOBAL_BOUNDARY")
    if assist_enabled and "MENU_UI" not in groups:
        groups.append("MENU_UI")

    candidates = []
    seen = set()
    for group in groups:
        for label_text, path in SEMANTIC_MAP.get(group, []):
            if path not in theme_index or path in seen:
                continue
            seen.add(path)
            candidates.append({"label": label_text, "path": path})

    if not candidates:
        for path in sorted(theme_index.keys())[:20]:
            candidates.append({"label": path.split(".")[-1], "path": path})
    return candidates


def collect_similar_candidates(seed_signature, tolerance):
    theme_index = build_theme_index()
    if seed_signature is None:
        return []

    matches = []
    for path, value in theme_index.items():
        signature = color_signature(value)
        if signature is None:
            continue
        distance = color_match_distance(signature, seed_signature, tolerance)
        if distance is not None:
            matches.append({
                "label": semantic_label_for_path(path),
                "path": path,
                "distance": distance,
            })
    matches.sort(key=lambda item: (item["distance"], item["path"]))
    return matches


def is_color_theme_path(path):
    owner, attr = resolve_theme_path(path)
    if owner is None:
        return False
    try:
        return color_to_list(getattr(owner, attr)) is not None
    except Exception:
        return False


def active_probe_candidates(context):
    wm = context.window_manager
    candidates = _probe_runtime.get("candidates", [])
    if getattr(wm, "theme_probe_mode", "AREA") == "SIMILAR":
        tolerance = getattr(wm, "theme_probe_tolerance", SIMILAR_TOLERANCE_DEFAULT)
        return collect_similar_candidates(_similar_seed_signature, tolerance)
    return candidates


def update_similar_seed_from_candidates(candidates):
    global _similar_seed_candidates, _similar_seed_signature, _similar_seed_path
    _similar_seed_candidates = list(candidates)
    theme_index = build_theme_index()
    for item in _similar_seed_candidates:
        signature = color_signature(theme_index.get(item["path"]))
        if signature is not None:
            _similar_seed_signature = signature
            _similar_seed_path = item["path"]
            return
    _similar_seed_signature = None
    _similar_seed_path = ""


def update_similar_seed_from_sample(context):
    global _similar_seed_candidates, _similar_seed_signature, _similar_seed_path
    wm = context.window_manager
    signature = signature_from_color(getattr(wm, "theme_probe_sample_color", (0.0, 0.0, 0.0, 1.0)))
    _similar_seed_candidates = []
    _similar_seed_signature = signature
    _similar_seed_path = "window_manager.theme_probe_sample_color"
    tag_redraw_all()


def set_sample_color(context, color, refresh_list=True):
    if color is None:
        return False
    wm = context.window_manager
    wm.theme_probe_sample_color = tuple(clamp(channel) for channel in color[:4])
    if refresh_list:
        update_similar_seed_from_sample(context)
        populate_candidate_collection(context)
        tag_redraw_all()
    return True


def schedule_sample_refresh(context):
    global _sample_refresh_pending, _sample_refresh_time, _sample_refresh_timer_running
    _sample_refresh_pending = True
    _sample_refresh_time = time.time()
    if not _sample_refresh_timer_running:
        _sample_refresh_timer_running = True
        bpy.app.timers.register(sample_refresh_timer, first_interval=0.15)


def sample_refresh_timer():
    global _sample_refresh_pending, _sample_refresh_timer_running
    if not _sample_refresh_pending:
        _sample_refresh_timer_running = False
        return None
    if time.time() - _sample_refresh_time < 0.35:
        return 0.15
    _sample_refresh_pending = False
    context = bpy.context
    if getattr(context.window_manager, "theme_probe_mode", "AREA") == "SIMILAR":
        populate_candidate_collection(context)
        tag_redraw_all()
    _sample_refresh_timer_running = False
    return None


def probe_at_position(context, mouse_x, mouse_y):
    area, region = find_area_region(context.screen, mouse_x, mouse_y)
    if area is None:
        sample_color = sample_screen_color(context, mouse_x, mouse_y)
        nearest_area = nearest_screen_area(context.screen, mouse_x, mouse_y)
        zone = classify_fallback_zone(context.screen, mouse_x, mouse_y, nearest_area)
        candidates = collect_visual_color_candidates(sample_color, zone, nearest_area)
        if not candidates:
            return False
        _probe_runtime.clear()
        _probe_runtime["area_type"] = "SCREEN"
        _probe_runtime["region_type"] = "VISUAL"
        _probe_runtime["zone"] = zone
        _probe_runtime["boundary"] = boundary_flags_from_point(nearest_area, mouse_x, mouse_y)
        _probe_runtime["candidates"] = candidates
        _probe_runtime["sample_color"] = sample_color
        return True
    _probe_runtime.clear()
    _probe_runtime["area_type"] = area.type
    _probe_runtime["region_type"] = region.type if region else ""
    _probe_runtime["zone"] = classify_probe_zone(context.screen, area, region, mouse_x, mouse_y)
    _probe_runtime["boundary"] = boundary_flags(area, mouse_x, mouse_y)
    _probe_runtime["candidates"] = collect_candidates(area, region)
    return True


def populate_candidate_collection(context, candidates=None):
    wm = context.window_manager
    collection = getattr(wm, "theme_probe_candidates", None)
    if collection is None:
        return
    if candidates is None:
        candidates = active_probe_candidates(context)
    collection.clear()
    candidate_paths = {item["path"] for item in candidates}
    group_candidate_paths = set() if getattr(wm, "theme_probe_mode", "AREA") == "SIMILAR" else candidate_paths
    label_by_path = {item["path"]: item["label"] for item in candidates}
    grouped_paths = set()
    number = 1
    for group in build_mode_color_groups():
        group_color_paths = {item["path"] for item in group["colors"]}
        if not group_candidate_paths.intersection(group_color_paths):
            continue
        for item in group["enums"] + group["colors"]:
            if resolve_theme_path(item["path"])[0] is None:
                continue
            entry = collection.add()
            label_text = label_by_path.get(item["path"]) or ("背景类型" if item["path"].endswith(".background_type") else item["label"])
            entry.name = label_text
            entry.label = label_text
            entry.path = item["path"]
            entry.number = number
            number += 1
        grouped_paths.update(group_color_paths)

    for item in candidates:
        if item["path"] in grouped_paths:
            continue
        if getattr(wm, "theme_probe_mode", "AREA") == "SIMILAR" and not is_color_theme_path(item["path"]):
            continue
        entry = collection.add()
        entry.name = item["label"]
        entry.label = item["label"]
        entry.path = item["path"]
        entry.number = number
        number += 1
    restore_candidate_preview()
    wm.theme_probe_candidate_index = 0 if len(collection) else -1
    wm.theme_probe_candidate_preview_index = -1


def draw_theme_color_row(layout, label_text, theme_path):
    owner, attr = resolve_theme_path(theme_path)
    if owner is None:
        return False
    row = layout.row(align=True)
    split = row.split(factor=0.58, align=True)
    split.label(text=label_text)
    split.prop(owner, attr, text="")
    return True


def current_candidate_color_paths(context):
    paths = []
    for item in getattr(context.window_manager, "theme_probe_candidates", []):
        if is_color_theme_path(item.path) and item.path not in paths:
            paths.append(item.path)
    return paths


def color_value_for_path(path):
    owner, attr = resolve_theme_path(path)
    if owner is None:
        return None
    try:
        value = getattr(owner, attr)
    except Exception:
        return None
    color = color_to_list(value)
    if color is None or len(color) < 3:
        return None
    if len(color) == 3:
        color.append(1.0)
    return tuple(clamp(channel) for channel in color[:4])


def set_color_value_for_path(path, color):
    owner, attr = resolve_theme_path(path)
    if owner is None:
        return False
    try:
        current = getattr(owner, attr)
        length = len(current)
        setattr(owner, attr, tuple(color[:length]))
        return True
    except Exception:
        return False


class ThemeCandidateResolver:
    @staticmethod
    def resolve(area, region):
        return collect_candidates(area, region)


def prepare_candidate_collection(context):
    populate_candidate_collection(context)


def update_probe_list_settings(self, context):
    if context is not None:
        prepare_candidate_collection(context)
        tag_redraw_all()


def update_sample_color(self, context):
    if context is not None and getattr(context.window_manager, "theme_probe_mode", "AREA") == "SIMILAR":
        update_similar_seed_from_sample(context)
        schedule_sample_refresh(context)


def export_current_theme_xml(filepath, name_hint=None):
    import _rna_xml as rna_xml

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    root = theme_root()
    if root is not None and name_hint:
        root.name = name_hint
    preset_map = bpy.types.USERPREF_MT_interface_theme_presets.preset_xml_map
    rna_xml.xml_file_write(bpy.context, filepath, preset_map)
    if root is not None:
        root.filepath = filepath
    return filepath


def default_theme_preset_dir():
    return bpy.utils.user_resource("SCRIPTS", path=os.path.join("presets", "interface_theme"), create=True)


def current_theme_filepath():
    root = theme_root()
    if root is None:
        return ""
    return getattr(root, "filepath", "") or ""


def current_theme_save_path():
    filepath = current_theme_filepath()
    if filepath and not os.path.isdir(filepath):
        return filepath
    return os.path.join(default_theme_preset_dir(), "theme_probe_current.xml")


def open_theme_preset_folder():
    folder = default_theme_preset_dir()
    os.makedirs(folder, exist_ok=True)
    bpy.ops.wm.path_open(filepath=folder)
    return folder


def sync_keymaps():
    while addon_keymaps:
        km, kmi = addon_keymaps.pop()
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    prefs = addon_preferences()
    if prefs is None:
        return
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return
    km = kc.keymaps.new(name="Window", space_type="EMPTY")
    kmi = km.keymap_items.new(
        THEMEPROBE_OT_probe.bl_idname,
        prefs.shortcut_key,
        "PRESS",
        alt=prefs.shortcut_alt,
        ctrl=prefs.shortcut_ctrl,
        shift=prefs.shortcut_shift,
    )
    addon_keymaps.append((km, kmi))


def update_keymap_pref(self, context):
    sync_keymaps()


class THEMEPROBE_OT_probe(Operator):
    bl_idname = "theme_probe.probe"
    bl_label = "Theme Probe"
    bl_description = "Probe the current UI area and list candidate theme colors"

    mouse_x: IntProperty(options={"SKIP_SAVE"})
    mouse_y: IntProperty(options={"SKIP_SAVE"})

    def invoke(self, context, event):
        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y
        return self.execute(context)

    def execute(self, context):
        ensure_snapshot()
        ensure_history_timer()
        if not probe_at_position(context, self.mouse_x, self.mouse_y):
            self.report({"WARNING"}, "No UI area found under cursor")
            return {"CANCELLED"}
        if context.window_manager.theme_probe_mode == "SIMILAR":
            if not set_sample_color(context, sample_screen_color(context, self.mouse_x, self.mouse_y), refresh_list=True):
                update_similar_seed_from_candidates(_probe_runtime.get("candidates", []))
        populate_candidate_collection(context)
        bpy.ops.theme_probe.show_candidates("INVOKE_DEFAULT")
        return {"FINISHED"}


class THEMEPROBE_OT_edit_color(Operator):
    bl_idname = "theme_probe.edit_color"
    bl_label = "Edit Theme Color"
    bl_description = "Edit the selected theme color with Blender's native color picker"

    label_text: StringProperty()
    theme_path: StringProperty()

    def invoke(self, context, event):
        ensure_snapshot()
        ensure_history_timer()
        return context.window_manager.invoke_popup(self, width=440)

    def execute(self, context):
        tag_redraw_all()
        return {"FINISHED"}

    def check(self, context):
        tag_redraw_all()
        return True

    def draw(self, context):
        layout = self.layout
        owner, attr = resolve_theme_path(self.theme_path)
        layout.label(text=self.label_text or "\u989c\u8272")
        layout.label(text=self.theme_path)
        if owner is None:
            layout.label(text="\u8be5\u989c\u8272\u5b57\u6bb5\u5728\u5f53\u524d Blender \u7248\u672c\u4e2d\u4e0d\u5b58\u5728\u3002", icon="ERROR")
            return
        box = layout.box()
        box.use_property_split = True
        box.prop(owner, attr, text="\u989c\u8272")

    def cancel(self, context):
        tag_redraw_all()


class THEMEPROBE_OT_restore_session(Operator):
    bl_idname = "theme_probe.restore_session"
    bl_label = "\u91cd\u7f6e\u5f53\u524d\u4e3b\u9898"
    bl_description = "\u5c06\u5f53\u524d\u4e3b\u9898\u91cd\u7f6e\u4e3a\u672c\u6b21\u63a2\u6d4b\u5f00\u59cb\u524d\u7684\u5feb\u7167\u72b6\u6001"

    def execute(self, context):
        if restore_snapshot():
            self.report({"INFO"}, "\u5f53\u524d\u4e3b\u9898\u5df2\u91cd\u7f6e")
            return {"FINISHED"}
        self.report({"WARNING"}, "No session snapshot available")
        return {"CANCELLED"}


class THEMEPROBE_OT_undo_theme_change(Operator):
    bl_idname = "theme_probe.undo_theme_change"
    bl_label = "Undo Theme Probe Change"
    bl_description = "Undo the last theme change recorded by Theme Probe"

    def execute(self, context):
        if undo_theme_change():
            self.report({"INFO"}, "Theme Probe change undone")
            return {"FINISHED"}
        self.report({"WARNING"}, "No Theme Probe change history")
        return {"CANCELLED"}


class THEMEPROBE_OT_redo_theme_change(Operator):
    bl_idname = "theme_probe.redo_theme_change"
    bl_label = "Redo Theme Probe Change"
    bl_description = "Redo the last undone theme change recorded by Theme Probe"

    def execute(self, context):
        if redo_theme_change():
            self.report({"INFO"}, "Theme Probe change redone")
            return {"FINISHED"}
        self.report({"WARNING"}, "No Theme Probe redo history")
        return {"CANCELLED"}


class THEMEPROBE_OT_save_current(Operator):
    bl_idname = "theme_probe.save_current"
    bl_label = "\u4fdd\u5b58\u5f53\u524d\u4e3b\u9898"
    bl_description = "Save the current theme preset"

    def execute(self, context):
        ensure_snapshot()
        filepath = current_theme_save_path()
        root = theme_root()
        export_current_theme_xml(filepath, getattr(root, "name", "") or "Theme Probe Current")
        refresh_snapshot()
        self.report({"INFO"}, f"Theme saved to {filepath}")
        tag_redraw_all()
        return {"FINISHED"}


class THEMEPROBE_OT_save_as(Operator):
    bl_idname = "theme_probe.save_as"
    bl_label = "\u53e6\u5b58\u4e3a\u4e3b\u9898"
    bl_description = "Export the current theme to the interface_theme preset folder"

    preset_name: StringProperty(name="Theme Name", default="Theme Probe Custom")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        self.layout.prop(self, "preset_name", text="\u540d\u79f0")

    def execute(self, context):
        ensure_snapshot()
        file_name = bpy.path.clean_name(self.preset_name) or "theme_probe_custom"
        filepath = os.path.join(default_theme_preset_dir(), f"{file_name}.xml")
        export_current_theme_xml(filepath, self.preset_name)
        refresh_snapshot()
        self.report({"INFO"}, f"Theme exported to {filepath}")
        tag_redraw_all()
        return {"FINISHED"}


class THEMEPROBE_OT_open_theme_folder(Operator):
    bl_idname = "theme_probe.open_theme_folder"
    bl_label = "\u6253\u5f00\u4e3b\u9898\u6587\u4ef6\u5939"
    bl_description = "Open Blender's interface_theme preset folder"

    def execute(self, context):
        folder = open_theme_preset_folder()
        self.report({"INFO"}, f"Opened {folder}")
        return {"FINISHED"}


class THEMEPROBE_OT_pick_probe_target(Operator):
    bl_idname = "theme_probe.pick_probe_target"
    bl_label = "\u5438\u53d6\u63a2\u6d4b\u76ee\u6807"
    bl_description = "\u533a\u57df\u6a21\u5f0f\u4e0b\u91cd\u65b0\u63a2\u6d4b\u70b9\u51fb\u533a\u57df\uff1b\u76f8\u4f3c\u989c\u8272\u6a21\u5f0f\u4e0b\u4f7f\u7528\u70b9\u51fb\u533a\u57df\u989c\u8272\u4f5c\u4e3a\u76f8\u4f3c\u68c0\u7d22\u6837\u672c"

    def invoke(self, context, event):
        if context.window_manager.theme_probe_mode == "SIMILAR":
            try:
                return bpy.ops.ui.eyedropper_color(
                    "INVOKE_DEFAULT",
                    prop_data_path="window_manager.theme_probe_sample_color",
                )
            except TypeError:
                return bpy.ops.ui.eyedropper_color(
                    "INVOKE_DEFAULT",
                    prop_data_path="bpy.context.window_manager.theme_probe_sample_color",
                )
        context.window.cursor_modal_set("EYEDROPPER")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"}:
            context.window.cursor_modal_restore()
            return {"CANCELLED"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            context.window.cursor_modal_restore()
            if not probe_at_position(context, event.mouse_x, event.mouse_y):
                self.report({"WARNING"}, "No UI area found under cursor")
                return {"CANCELLED"}
            if context.window_manager.theme_probe_mode == "SIMILAR":
                update_similar_seed_from_candidates(_probe_runtime.get("candidates", []))
            populate_candidate_collection(context)
            return {"FINISHED"}
        return {"RUNNING_MODAL"}


class THEMEPROBE_OT_toggle_candidate_selection(Operator):
    bl_idname = "theme_probe.toggle_candidate_selection"
    bl_label = "\u5207\u6362\u5019\u9009\u9879\u9009\u4e2d"
    bl_description = "\u9009\u4e2d\u6216\u53d6\u6d88\u9009\u4e2d\u8be5\u989c\u8272\u5019\u9009\u9879"

    index: IntProperty(default=-1)

    def execute(self, context):
        wm = context.window_manager
        if _candidate_preview_auto_disabled_sync:
            stop_candidate_preview_from_mouse(context)
            tag_redraw_all()
            return {"FINISHED"}
        if getattr(wm, "theme_probe_candidate_preview_index", -1) == self.index:
            stop_candidate_preview_from_mouse(context)
        else:
            restore_candidate_preview()
            auto_disable_similar_sync_for_preview(context)
            wm.theme_probe_candidate_preview_index = self.index
            wm.theme_probe_candidate_index = self.index
            schedule_candidate_preview(context)
        tag_redraw_all()
        return {"FINISHED"}


class THEMEPROBE_OT_toggle_candidate_lock(Operator):
    bl_idname = "theme_probe.toggle_candidate_lock"
    bl_label = "\u5207\u6362\u5019\u9009\u9879\u9501\u5b9a"
    bl_description = "\u9501\u5b9a\u6216\u89e3\u9501\u8be5\u76f8\u4f3c\u8272\u5019\u9009\u9879"

    index: IntProperty(default=-1)

    def execute(self, context):
        wm = context.window_manager
        items = getattr(wm, "theme_probe_candidates", None)
        if not items or self.index < 0 or self.index >= len(items):
            return {"CANCELLED"}

        path = getattr(items[self.index], "path", "")
        if not path:
            return {"CANCELLED"}

        if candidate_path_locked(path):
            _locked_candidate_paths.discard(path)
        else:
            restore_candidate_preview()
            _locked_candidate_paths.add(path)
            if getattr(wm, "theme_probe_candidate_preview_index", -1) == self.index:
                wm.theme_probe_candidate_preview_index = -1
        tag_redraw_all()
        return {"FINISHED"}


class THEMEPROBE_OT_unlock_all_candidates(Operator):
    bl_idname = "theme_probe.unlock_all_candidates"
    bl_label = "\u5168\u90e8\u89e3\u9501"
    bl_description = "\u6e05\u9664\u4e3b\u9898\u63a2\u6d4b\u5217\u8868\u4e2d\u7684\u6240\u6709\u9501\u5b9a\u72b6\u6001"

    def execute(self, context):
        _locked_candidate_paths.clear()
        tag_redraw_all()
        return {"FINISHED"}


class THEMEPROBE_CandidateItem(PropertyGroup):
    label: StringProperty()
    path: StringProperty()
    number: IntProperty()


class THEMEPROBE_UL_candidates(UIList):
    bl_idname = "THEMEPROBE_UL_candidates"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        owner, attr = resolve_theme_path(item.path)
        row = layout.row(align=False)
        if owner is None:
            row.label(text=f"{item.number}. {item.label}", icon="ERROR")
            return
        content_row = row
        locked = candidate_path_locked(item.path)
        if getattr(context.window_manager, "theme_probe_mode", "AREA") == "SIMILAR":
            lock_split = row.split(factor=0.13, align=False)
            lock_part = lock_split.row(align=True)
            lock_part.alignment = "CENTER"
            lock_op = lock_part.operator(
                THEMEPROBE_OT_toggle_candidate_lock.bl_idname,
                text="",
                icon=candidate_path_lock_icon(item.path),
                emboss=False,
            )
            lock_op.index = index
            content_row = lock_split.row(align=False)
            content_row.enabled = not locked
        split = content_row.split(factor=0.56, align=False)
        select_part = split.row(align=True)
        select_part.alignment = "CENTER"
        select_op = select_part.operator(
            THEMEPROBE_OT_toggle_candidate_selection.bl_idname,
            text=item.label,
            emboss=False,
        )
        select_op.index = index
        color_part = split.row(align=False)
        color_part.prop(owner, attr, text="")


class THEMEPROBE_OT_show_candidates(Operator):
    bl_idname = "theme_probe.show_candidates"
    bl_label = "Theme Probe Candidates"
    bl_description = "Show a compact list of likely theme colors"

    def invoke(self, context, event):
        prepare_candidate_collection(context)
        width = getattr(context.window_manager, "theme_probe_popup_width", POPUP_WIDTH)
        return context.window_manager.invoke_popup(self, width=width)

    def execute(self, context):
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        area_type = _probe_runtime.get("area_type", "UNKNOWN")
        region_type = _probe_runtime.get("region_type", "")
        zone = _probe_runtime.get("zone", "")
        boundary = _probe_runtime.get("boundary", {})
        wm = context.window_manager

        header = layout.row(align=True)
        header.operator(THEMEPROBE_OT_pick_probe_target.bl_idname, text="", icon="EYEDROPPER")
        if wm.theme_probe_mode == "SIMILAR":
            title = color_hex(_similar_seed_signature) or "\u672a\u53d6\u6837"
        elif area_type == "SCREEN":
            title = display_zone_label(zone)
        else:
            title = f"{area_type} / {region_type or 'NONE'}"
        if wm.theme_probe_mode == "SIMILAR":
            split = header.split(factor=0.58, align=True)
            sample_row = split.row(align=True)
            sample_row.label(text=title)
            swatch = sample_row.row(align=True)
            swatch.scale_x = 0.42
            swatch.prop(wm, "theme_probe_sample_color", text="")
            folder_row = split.row(align=True)
            folder_row.alignment = "RIGHT"
            folder_row.operator(THEMEPROBE_OT_open_theme_folder.bl_idname, text="", icon="FILE_FOLDER")
        else:
            header.label(text=title)
            header.operator(THEMEPROBE_OT_open_theme_folder.bl_idname, text="", icon="FILE_FOLDER")
        if boundary.get("near_any"):
            layout.label(text="\u9760\u8fd1\u8fb9\u754c", icon="MOD_EDGESPLIT")

        layout.prop(wm, "theme_probe_mode", text="\u6a21\u5f0f")
        controls = layout.row(align=True)
        controls.prop(wm, "theme_probe_popup_width", text="\u5bbd\u5ea6")
        tolerance_row = controls.row(align=True)
        tolerance_row.enabled = wm.theme_probe_mode == "SIMILAR"
        tolerance_row.prop(wm, "theme_probe_tolerance", text="\u5bb9\u5dee", slider=True)
        if wm.theme_probe_mode == "SIMILAR":
            tools_row = layout.row(align=True)
            unlock_row = tools_row.row(align=True)
            unlock_row.operator(THEMEPROBE_OT_unlock_all_candidates.bl_idname, text="\u5168\u90e8\u89e3\u9501", icon="UNLOCKED")
            sync_row = tools_row.row(align=True)
            sync_row.alignment = "RIGHT"
            sync_row.label(text="\u540c\u6b65\u4fee\u6539")
            sync_row.prop(wm, "theme_probe_sync_similar", text="")
        layout.separator()

        if not wm.theme_probe_candidates:
            layout.label(text="\u6ca1\u6709\u627e\u5230\u53ef\u7528\u5019\u9009\u9879", icon="INFO")

        list_items = wm.theme_probe_candidates
        if list_items:
            layout.template_list(
                "THEMEPROBE_UL_candidates",
                "",
                wm,
                "theme_probe_candidates",
                wm,
                "theme_probe_candidate_index",
                rows=min(POPUP_LIST_ROWS, max(1, len(list_items))),
                maxrows=POPUP_LIST_ROWS,
            )
            schedule_candidate_preview(context)
        layout.separator()
        preset_row = layout.row(align=True)
        root = theme_root()
        filepath = current_theme_filepath()
        preset_label = os.path.splitext(os.path.basename(filepath))[0] if filepath else (getattr(root, "name", "") if root else "Presets")
        preset_row.menu("USERPREF_MT_interface_theme_presets", text=preset_label or "Presets")
        preset_row.operator("wm.interface_theme_preset_add", text="", icon="ADD")
        preset_row.operator("wm.interface_theme_preset_remove", text="", icon="REMOVE")
        preset_row.operator(THEMEPROBE_OT_save_current.bl_idname, text="", icon="FILE_TICK")

        footer = layout.row(align=True)
        footer.scale_y = 1.05
        footer.operator(
            THEMEPROBE_OT_restore_session.bl_idname,
            text="\u91cd\u7f6e\u5f53\u524d\u4e3b\u9898",
            icon="FILE_REFRESH",
        )
        footer.operator(
            THEMEPROBE_OT_undo_theme_change.bl_idname,
            text="",
            icon="BACK",
        )
        footer.operator(
            THEMEPROBE_OT_redo_theme_change.bl_idname,
            text="",
            icon="FORWARD",
        )


class THEMEPROBE_Preferences(AddonPreferences):
    bl_idname = ADDON_ID

    enable_current_screen_assist: BoolProperty(
        name="Enable Current Screen Assist",
        default=True,
    )
    shortcut_key: EnumProperty(
        name="Shortcut Key",
        items=SHORTCUT_KEYS,
        default="C",
        update=update_keymap_pref,
    )
    shortcut_alt: BoolProperty(name="Alt", default=True, update=update_keymap_pref)
    shortcut_ctrl: BoolProperty(name="Ctrl", default=False, update=update_keymap_pref)
    shortcut_shift: BoolProperty(name="Shift", default=False, update=update_keymap_pref)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "enable_current_screen_assist")
        row = layout.row(align=True)
        row.label(text="\u5feb\u6377\u952e")
        row.prop(self, "shortcut_ctrl", toggle=True)
        row.prop(self, "shortcut_alt", toggle=True)
        row.prop(self, "shortcut_shift", toggle=True)
        row.prop(self, "shortcut_key", text="")


ThemeProbeOperator = THEMEPROBE_OT_probe
ThemeProbePopup = THEMEPROBE_OT_show_candidates
ThemeProbePreferences = THEMEPROBE_Preferences


classes = (
    THEMEPROBE_OT_probe,
    THEMEPROBE_OT_edit_color,
    THEMEPROBE_OT_restore_session,
    THEMEPROBE_OT_undo_theme_change,
    THEMEPROBE_OT_redo_theme_change,
    THEMEPROBE_OT_save_current,
    THEMEPROBE_OT_save_as,
    THEMEPROBE_OT_open_theme_folder,
    THEMEPROBE_OT_pick_probe_target,
    THEMEPROBE_OT_toggle_candidate_selection,
    THEMEPROBE_OT_toggle_candidate_lock,
    THEMEPROBE_OT_unlock_all_candidates,
    THEMEPROBE_CandidateItem,
    THEMEPROBE_UL_candidates,
    THEMEPROBE_OT_show_candidates,
    THEMEPROBE_Preferences,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.theme_probe_candidates = CollectionProperty(type=THEMEPROBE_CandidateItem)
    bpy.types.WindowManager.theme_probe_candidate_index = IntProperty(default=0, min=-1, update=update_candidate_index)
    bpy.types.WindowManager.theme_probe_candidate_preview_index = IntProperty(default=-1, min=-1)
    bpy.types.WindowManager.theme_probe_mode = EnumProperty(
        name="\u63a2\u6d4b\u6a21\u5f0f",
        items=PROBE_MODE_ITEMS,
        default="AREA",
        update=update_probe_list_settings,
    )
    bpy.types.WindowManager.theme_probe_tolerance = IntProperty(
        name="\u5bb9\u5dee\u503c",
        default=SIMILAR_TOLERANCE_DEFAULT,
        min=0,
        max=255,
        update=update_probe_list_settings,
    )
    bpy.types.WindowManager.theme_probe_sync_similar = BoolProperty(
        name="\u540c\u6b65\u4fee\u6539",
        default=True,
    )
    bpy.types.WindowManager.theme_probe_popup_width = IntProperty(
        name="\u5f39\u7a97\u5bbd\u5ea6",
        default=POPUP_WIDTH,
        min=160,
        max=720,
        description="\u62d6\u52a8\u6570\u503c\u540e\u91cd\u65b0\u547c\u51fa\u63a2\u6d4b\u9762\u677f\u751f\u6548",
    )
    bpy.types.WindowManager.theme_probe_sample_color = FloatVectorProperty(
        name="\u53d6\u6837\u989c\u8272",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(1.0, 1.0, 1.0, 1.0),
        update=update_sample_color,
    )
    sync_keymaps()
    ensure_history_timer()


def unregister():
    restore_candidate_preview()
    _locked_candidate_paths.clear()
    stop_history_timer()
    while addon_keymaps:
        km, kmi = addon_keymaps.pop()
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    stop_history_timer()
    for prop_name in (
        "theme_probe_tolerance",
        "theme_probe_sync_similar",
        "theme_probe_mode",
        "theme_probe_popup_width",
        "theme_probe_sample_color",
        "theme_probe_candidate_preview_index",
        "theme_probe_candidate_index",
        "theme_probe_candidates",
    ):
        if hasattr(bpy.types.WindowManager, prop_name):
            delattr(bpy.types.WindowManager, prop_name)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
