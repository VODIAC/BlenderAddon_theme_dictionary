bl_info = {
    "name": "theme dictionary",
    "author": "61+, Witty.Ming",
    "version": (0, 6, 4),
    "blender": (5, 0, 0),
    "location": "Top Bar / Alt+C",
    "description": "Search for related theme color entries based on color or mouse area",
    "category": "Interface",
}

import colorsys
import importlib.util
import math
import os
import tempfile
import time

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatVectorProperty, IntProperty, StringProperty
from bpy.types import AddonPreferences, Menu, Operator, PropertyGroup, UIList

try:
    from . import translation
except Exception:
    translation_path = os.path.join(os.path.dirname(__file__), "translation.py")
    translation_spec = importlib.util.spec_from_file_location(f"{__name__}.translation", translation_path)
    if translation_spec and translation_spec.loader:
        translation = importlib.util.module_from_spec(translation_spec)
        translation_spec.loader.exec_module(translation)
    else:
        translation = None


ADDON_ID = __name__
BOUNDARY_THRESHOLD = 6
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
EDIT_HISTORY_LIMIT = 60
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
_edit_history_paths = []
_candidate_preview_suppressed_values = {}
_history_ignored_preview_paths = set()


PROBE_MODE_ITEMS = (
    ("AREA", "Area Detect", "Detect theme colors from the area under the mouse"),
    ("SIMILAR", "Similar Color", "Search globally for colors similar to the current sample"),
    ("EDIT_HISTORY", "Edit History", "Show theme colors manually edited in this session"),
)


SEMANTIC_MAP = {
    'MD_01': [
        ('User Interface Menu Widget Inner', 'user_interface.wcol_menu.inner'),
        ('User Interface Menu Widget Inner Selected', 'user_interface.wcol_menu.inner_sel'),
        ('User Interface Menu Widget Item', 'user_interface.wcol_menu.item'),
        ('User Interface Menu Widget Outline', 'user_interface.wcol_menu.outline'),
        ('User Interface Menu Widget Outline Selected', 'user_interface.wcol_menu.outline_sel'),
        ('User Interface Menu Widget Text', 'user_interface.wcol_menu.text'),
        ('User Interface Menu Widget Text Selected', 'user_interface.wcol_menu.text_sel'),
        ('User Interface Menu Backdrop Inner', 'user_interface.wcol_menu_back.inner'),
        ('User Interface Menu Backdrop Inner Selected', 'user_interface.wcol_menu_back.inner_sel'),
        ('User Interface Menu Backdrop Item', 'user_interface.wcol_menu_back.item'),
        ('User Interface Menu Backdrop Outline', 'user_interface.wcol_menu_back.outline'),
        ('User Interface Menu Backdrop Outline Selected', 'user_interface.wcol_menu_back.outline_sel'),
        ('User Interface Menu Backdrop Text', 'user_interface.wcol_menu_back.text'),
        ('User Interface Menu Backdrop Text Selected', 'user_interface.wcol_menu_back.text_sel'),
        ('User Interface Menu Item Inner', 'user_interface.wcol_menu_item.inner'),
        ('User Interface Menu Item Inner Selected', 'user_interface.wcol_menu_item.inner_sel'),
        ('User Interface Menu Item Item', 'user_interface.wcol_menu_item.item'),
        ('User Interface Menu Item Outline', 'user_interface.wcol_menu_item.outline'),
        ('User Interface Menu Item Outline Selected', 'user_interface.wcol_menu_item.outline_sel'),
        ('User Interface Menu Item Text', 'user_interface.wcol_menu_item.text'),
        ('User Interface Menu Item Text Selected', 'user_interface.wcol_menu_item.text_sel'),
        ('User Interface Pie Menu Inner', 'user_interface.wcol_pie_menu.inner'),
        ('User Interface Pie Menu Inner Selected', 'user_interface.wcol_pie_menu.inner_sel'),
        ('User Interface Pie Menu Item', 'user_interface.wcol_pie_menu.item'),
        ('User Interface Pie Menu Outline', 'user_interface.wcol_pie_menu.outline'),
        ('User Interface Pie Menu Outline Selected', 'user_interface.wcol_pie_menu.outline_sel'),
        ('User Interface Pie Menu Text', 'user_interface.wcol_pie_menu.text'),
        ('User Interface Pie Menu Text Selected', 'user_interface.wcol_pie_menu.text_sel'),
        ('User Interface Pulldown Widget Inner', 'user_interface.wcol_pulldown.inner'),
        ('User Interface Pulldown Widget Inner Selected', 'user_interface.wcol_pulldown.inner_sel'),
        ('User Interface Pulldown Widget Item', 'user_interface.wcol_pulldown.item'),
        ('User Interface Pulldown Widget Outline', 'user_interface.wcol_pulldown.outline'),
        ('User Interface Pulldown Widget Outline Selected', 'user_interface.wcol_pulldown.outline_sel'),
        ('User Interface Pulldown Widget Text', 'user_interface.wcol_pulldown.text'),
        ('User Interface Pulldown Widget Text Selected', 'user_interface.wcol_pulldown.text_sel'),
        ('User Interface Tooltip Inner', 'user_interface.wcol_tooltip.inner'),
        ('User Interface Tooltip Inner Selected', 'user_interface.wcol_tooltip.inner_sel'),
        ('User Interface Tooltip Item', 'user_interface.wcol_tooltip.item'),
        ('User Interface Tooltip Outline', 'user_interface.wcol_tooltip.outline'),
        ('User Interface Tooltip Outline Selected', 'user_interface.wcol_tooltip.outline_sel'),
        ('User Interface Tooltip Text', 'user_interface.wcol_tooltip.text'),
        ('User Interface Tooltip Text Selected', 'user_interface.wcol_tooltip.text_sel'),
        ('User Interface Curve Widget Inner', 'user_interface.wcol_curve.inner'),
        ('User Interface Curve Widget Inner Selected', 'user_interface.wcol_curve.inner_sel'),
        ('User Interface Curve Widget Item', 'user_interface.wcol_curve.item'),
        ('User Interface Curve Widget Outline', 'user_interface.wcol_curve.outline'),
        ('User Interface Curve Widget Outline Selected', 'user_interface.wcol_curve.outline_sel'),
        ('User Interface Curve Widget Text', 'user_interface.wcol_curve.text'),
        ('User Interface Curve Widget Text Selected', 'user_interface.wcol_curve.text_sel'),
        ('User Interface Number Widget Inner', 'user_interface.wcol_num.inner'),
        ('User Interface Number Widget Inner Selected', 'user_interface.wcol_num.inner_sel'),
        ('User Interface Number Widget Item', 'user_interface.wcol_num.item'),
        ('User Interface Number Widget Outline', 'user_interface.wcol_num.outline'),
        ('User Interface Number Widget Outline Selected', 'user_interface.wcol_num.outline_sel'),
        ('User Interface Number Widget Text', 'user_interface.wcol_num.text'),
        ('User Interface Number Widget Text Selected', 'user_interface.wcol_num.text_sel'),
        ('User Interface Slider Widget Inner', 'user_interface.wcol_numslider.inner'),
        ('User Interface Slider Widget Inner Selected', 'user_interface.wcol_numslider.inner_sel'),
        ('User Interface Slider Widget Item', 'user_interface.wcol_numslider.item'),
        ('User Interface Slider Widget Outline', 'user_interface.wcol_numslider.outline'),
        ('User Interface Slider Widget Outline Selected', 'user_interface.wcol_numslider.outline_sel'),
        ('User Interface Slider Widget Text', 'user_interface.wcol_numslider.text'),
        ('User Interface Slider Widget Text Selected', 'user_interface.wcol_numslider.text_sel'),
        ('User Interface Option Widget Inner', 'user_interface.wcol_option.inner'),
        ('User Interface Option Widget Inner Selected', 'user_interface.wcol_option.inner_sel'),
        ('User Interface Option Widget Item', 'user_interface.wcol_option.item'),
        ('User Interface Option Widget Outline', 'user_interface.wcol_option.outline'),
        ('User Interface Option Widget Outline Selected', 'user_interface.wcol_option.outline_sel'),
        ('User Interface Option Widget Text', 'user_interface.wcol_option.text'),
        ('User Interface Option Widget Text Selected', 'user_interface.wcol_option.text_sel'),
        ('User Interface Progress Bar Inner', 'user_interface.wcol_progress.inner'),
        ('User Interface Progress Bar Inner Selected', 'user_interface.wcol_progress.inner_sel'),
        ('User Interface Progress Bar Item', 'user_interface.wcol_progress.item'),
        ('User Interface Progress Bar Outline', 'user_interface.wcol_progress.outline'),
        ('User Interface Progress Bar Outline Selected', 'user_interface.wcol_progress.outline_sel'),
        ('User Interface Progress Bar Text', 'user_interface.wcol_progress.text'),
        ('User Interface Progress Bar Text Selected', 'user_interface.wcol_progress.text_sel'),
        ('User Interface Radio Widget Inner', 'user_interface.wcol_radio.inner'),
        ('User Interface Radio Widget Inner Selected', 'user_interface.wcol_radio.inner_sel'),
        ('User Interface Radio Widget Item', 'user_interface.wcol_radio.item'),
        ('User Interface Radio Widget Outline', 'user_interface.wcol_radio.outline'),
        ('User Interface Radio Widget Outline Selected', 'user_interface.wcol_radio.outline_sel'),
        ('User Interface Radio Widget Text', 'user_interface.wcol_radio.text'),
        ('User Interface Radio Widget Text Selected', 'user_interface.wcol_radio.text_sel'),
        ('User Interface Regular Widget Inner', 'user_interface.wcol_regular.inner'),
        ('User Interface Regular Widget Inner Selected', 'user_interface.wcol_regular.inner_sel'),
        ('User Interface Regular Widget Item', 'user_interface.wcol_regular.item'),
        ('User Interface Regular Widget Outline', 'user_interface.wcol_regular.outline'),
        ('User Interface Regular Widget Outline Selected', 'user_interface.wcol_regular.outline_sel'),
        ('User Interface Regular Widget Text', 'user_interface.wcol_regular.text'),
        ('User Interface Regular Widget Text Selected', 'user_interface.wcol_regular.text_sel'),
        ('User Interface State Error', 'user_interface.wcol_state.error'),
        ('User Interface State Info', 'user_interface.wcol_state.info'),
        ('User Interface State Inner Anim', 'user_interface.wcol_state.inner_anim'),
        ('User Interface State Inner Anim Sel', 'user_interface.wcol_state.inner_anim_sel'),
        ('User Interface State Inner Changed', 'user_interface.wcol_state.inner_changed'),
        ('User Interface State Inner Changed Sel', 'user_interface.wcol_state.inner_changed_sel'),
        ('User Interface State Inner Driven', 'user_interface.wcol_state.inner_driven'),
        ('User Interface State Inner Driven Sel', 'user_interface.wcol_state.inner_driven_sel'),
        ('User Interface State Inner Key', 'user_interface.wcol_state.inner_key'),
        ('User Interface State Inner Key Sel', 'user_interface.wcol_state.inner_key_sel'),
        ('User Interface State Inner Overridden', 'user_interface.wcol_state.inner_overridden'),
        ('User Interface State Inner Overridden Sel', 'user_interface.wcol_state.inner_overridden_sel'),
        ('User Interface State Success', 'user_interface.wcol_state.success'),
        ('User Interface State Warning', 'user_interface.wcol_state.warning'),
        ('User Interface Text Widget Inner', 'user_interface.wcol_text.inner'),
        ('User Interface Text Widget Inner Selected', 'user_interface.wcol_text.inner_sel'),
        ('User Interface Text Widget Item', 'user_interface.wcol_text.item'),
        ('User Interface Text Widget Outline', 'user_interface.wcol_text.outline'),
        ('User Interface Text Widget Outline Selected', 'user_interface.wcol_text.outline_sel'),
        ('User Interface Text Widget Text', 'user_interface.wcol_text.text'),
        ('User Interface Text Widget Text Selected', 'user_interface.wcol_text.text_sel'),
        ('User Interface Toggle Widget Inner', 'user_interface.wcol_toggle.inner'),
        ('User Interface Toggle Widget Inner Selected', 'user_interface.wcol_toggle.inner_sel'),
        ('User Interface Toggle Widget Item', 'user_interface.wcol_toggle.item'),
        ('User Interface Toggle Widget Outline', 'user_interface.wcol_toggle.outline'),
        ('User Interface Toggle Widget Outline Selected', 'user_interface.wcol_toggle.outline_sel'),
        ('User Interface Toggle Widget Text', 'user_interface.wcol_toggle.text'),
        ('User Interface Toggle Widget Text Selected', 'user_interface.wcol_toggle.text_sel'),
        ('User Interface Widget Emboss', 'user_interface.widget_emboss'),
        ('User Interface Text Cursor', 'user_interface.widget_text_cursor'),
    ],
    'MD_02': [
        ('Status Bar Space Background', 'statusbar.space.back'),
        ('Status Bar Space Header', 'statusbar.space.header'),
        ('Status Bar Space Header Text', 'statusbar.space.header_text'),
        ('Status Bar Space Header Text Hi', 'statusbar.space.header_text_hi'),
        ('Status Bar Space Text', 'statusbar.space.text'),
        ('Status Bar Space Text Hi', 'statusbar.space.text_hi'),
        ('Status Bar Space Title', 'statusbar.space.title'),
        ('Top Bar Space Background', 'topbar.space.back'),
        ('Top Bar Space Header', 'topbar.space.header'),
        ('Top Bar Space Header Text', 'topbar.space.header_text'),
        ('Top Bar Space Header Text Hi', 'topbar.space.header_text_hi'),
        ('Top Bar Space Text', 'topbar.space.text'),
        ('Top Bar Space Text Hi', 'topbar.space.text_hi'),
        ('Top Bar Space Title', 'topbar.space.title'),
        ('User Interface Editor Border', 'user_interface.editor_border'),
        ('User Interface Editor Outline', 'user_interface.editor_outline'),
        ('User Interface Editor Outline Active', 'user_interface.editor_outline_active'),
        ('User Interface Icon Autokey', 'user_interface.icon_autokey'),
        ('User Interface Icon Collection', 'user_interface.icon_collection'),
        ('User Interface Icon Folder', 'user_interface.icon_folder'),
        ('User Interface Icon Modifier', 'user_interface.icon_modifier'),
        ('User Interface Icon Object', 'user_interface.icon_object'),
        ('User Interface Icon Object Data', 'user_interface.icon_object_data'),
        ('User Interface Icon Scene', 'user_interface.icon_scene'),
        ('User Interface Icon Shading', 'user_interface.icon_shading'),
        ('User Interface Curve Widget Inner', 'user_interface.wcol_curve.inner'),
        ('User Interface Curve Widget Inner Selected', 'user_interface.wcol_curve.inner_sel'),
        ('User Interface Curve Widget Item', 'user_interface.wcol_curve.item'),
        ('User Interface Curve Widget Outline', 'user_interface.wcol_curve.outline'),
        ('User Interface Curve Widget Outline Selected', 'user_interface.wcol_curve.outline_sel'),
        ('User Interface Curve Widget Text', 'user_interface.wcol_curve.text'),
        ('User Interface Curve Widget Text Selected', 'user_interface.wcol_curve.text_sel'),
        ('User Interface Menu Widget Inner', 'user_interface.wcol_menu.inner'),
        ('User Interface Menu Widget Inner Selected', 'user_interface.wcol_menu.inner_sel'),
        ('User Interface Menu Widget Item', 'user_interface.wcol_menu.item'),
        ('User Interface Menu Widget Outline', 'user_interface.wcol_menu.outline'),
        ('User Interface Menu Widget Outline Selected', 'user_interface.wcol_menu.outline_sel'),
        ('User Interface Menu Widget Text', 'user_interface.wcol_menu.text'),
        ('User Interface Menu Widget Text Selected', 'user_interface.wcol_menu.text_sel'),
        ('User Interface Menu Backdrop Inner', 'user_interface.wcol_menu_back.inner'),
        ('User Interface Menu Backdrop Inner Selected', 'user_interface.wcol_menu_back.inner_sel'),
        ('User Interface Menu Backdrop Item', 'user_interface.wcol_menu_back.item'),
        ('User Interface Menu Backdrop Outline', 'user_interface.wcol_menu_back.outline'),
        ('User Interface Menu Backdrop Outline Selected', 'user_interface.wcol_menu_back.outline_sel'),
        ('User Interface Menu Backdrop Text', 'user_interface.wcol_menu_back.text'),
        ('User Interface Menu Backdrop Text Selected', 'user_interface.wcol_menu_back.text_sel'),
        ('User Interface Menu Item Inner', 'user_interface.wcol_menu_item.inner'),
        ('User Interface Menu Item Inner Selected', 'user_interface.wcol_menu_item.inner_sel'),
        ('User Interface Menu Item Item', 'user_interface.wcol_menu_item.item'),
        ('User Interface Menu Item Outline', 'user_interface.wcol_menu_item.outline'),
        ('User Interface Menu Item Outline Selected', 'user_interface.wcol_menu_item.outline_sel'),
        ('User Interface Menu Item Text', 'user_interface.wcol_menu_item.text'),
        ('User Interface Menu Item Text Selected', 'user_interface.wcol_menu_item.text_sel'),
        ('User Interface Number Widget Inner', 'user_interface.wcol_num.inner'),
        ('User Interface Number Widget Inner Selected', 'user_interface.wcol_num.inner_sel'),
        ('User Interface Number Widget Item', 'user_interface.wcol_num.item'),
        ('User Interface Number Widget Outline', 'user_interface.wcol_num.outline'),
        ('User Interface Number Widget Outline Selected', 'user_interface.wcol_num.outline_sel'),
        ('User Interface Number Widget Text', 'user_interface.wcol_num.text'),
        ('User Interface Number Widget Text Selected', 'user_interface.wcol_num.text_sel'),
        ('User Interface Slider Widget Inner', 'user_interface.wcol_numslider.inner'),
        ('User Interface Slider Widget Inner Selected', 'user_interface.wcol_numslider.inner_sel'),
        ('User Interface Slider Widget Item', 'user_interface.wcol_numslider.item'),
        ('User Interface Slider Widget Outline', 'user_interface.wcol_numslider.outline'),
        ('User Interface Slider Widget Outline Selected', 'user_interface.wcol_numslider.outline_sel'),
        ('User Interface Slider Widget Text', 'user_interface.wcol_numslider.text'),
        ('User Interface Slider Widget Text Selected', 'user_interface.wcol_numslider.text_sel'),
        ('User Interface Option Widget Inner', 'user_interface.wcol_option.inner'),
        ('User Interface Option Widget Inner Selected', 'user_interface.wcol_option.inner_sel'),
        ('User Interface Option Widget Item', 'user_interface.wcol_option.item'),
        ('User Interface Option Widget Outline', 'user_interface.wcol_option.outline'),
        ('User Interface Option Widget Outline Selected', 'user_interface.wcol_option.outline_sel'),
        ('User Interface Option Widget Text', 'user_interface.wcol_option.text'),
        ('User Interface Option Widget Text Selected', 'user_interface.wcol_option.text_sel'),
        ('User Interface Pie Menu Inner', 'user_interface.wcol_pie_menu.inner'),
        ('User Interface Pie Menu Inner Selected', 'user_interface.wcol_pie_menu.inner_sel'),
        ('User Interface Pie Menu Item', 'user_interface.wcol_pie_menu.item'),
        ('User Interface Pie Menu Outline', 'user_interface.wcol_pie_menu.outline'),
        ('User Interface Pie Menu Outline Selected', 'user_interface.wcol_pie_menu.outline_sel'),
        ('User Interface Pie Menu Text', 'user_interface.wcol_pie_menu.text'),
        ('User Interface Pie Menu Text Selected', 'user_interface.wcol_pie_menu.text_sel'),
        ('User Interface Pulldown Widget Inner', 'user_interface.wcol_pulldown.inner'),
        ('User Interface Pulldown Widget Inner Selected', 'user_interface.wcol_pulldown.inner_sel'),
        ('User Interface Pulldown Widget Item', 'user_interface.wcol_pulldown.item'),
        ('User Interface Pulldown Widget Outline', 'user_interface.wcol_pulldown.outline'),
        ('User Interface Pulldown Widget Outline Selected', 'user_interface.wcol_pulldown.outline_sel'),
        ('User Interface Pulldown Widget Text', 'user_interface.wcol_pulldown.text'),
        ('User Interface Pulldown Widget Text Selected', 'user_interface.wcol_pulldown.text_sel'),
        ('User Interface Radio Widget Inner', 'user_interface.wcol_radio.inner'),
        ('User Interface Radio Widget Inner Selected', 'user_interface.wcol_radio.inner_sel'),
        ('User Interface Radio Widget Item', 'user_interface.wcol_radio.item'),
        ('User Interface Radio Widget Outline', 'user_interface.wcol_radio.outline'),
        ('User Interface Radio Widget Outline Selected', 'user_interface.wcol_radio.outline_sel'),
        ('User Interface Radio Widget Text', 'user_interface.wcol_radio.text'),
        ('User Interface Radio Widget Text Selected', 'user_interface.wcol_radio.text_sel'),
        ('User Interface Regular Widget Inner', 'user_interface.wcol_regular.inner'),
        ('User Interface Regular Widget Inner Selected', 'user_interface.wcol_regular.inner_sel'),
        ('User Interface Regular Widget Item', 'user_interface.wcol_regular.item'),
        ('User Interface Regular Widget Outline', 'user_interface.wcol_regular.outline'),
        ('User Interface Regular Widget Outline Selected', 'user_interface.wcol_regular.outline_sel'),
        ('User Interface Regular Widget Text', 'user_interface.wcol_regular.text'),
        ('User Interface Regular Widget Text Selected', 'user_interface.wcol_regular.text_sel'),
        ('User Interface Text Widget Inner', 'user_interface.wcol_text.inner'),
        ('User Interface Text Widget Inner Selected', 'user_interface.wcol_text.inner_sel'),
        ('User Interface Text Widget Item', 'user_interface.wcol_text.item'),
        ('User Interface Text Widget Outline', 'user_interface.wcol_text.outline'),
        ('User Interface Text Widget Outline Selected', 'user_interface.wcol_text.outline_sel'),
        ('User Interface Text Widget Text', 'user_interface.wcol_text.text'),
        ('User Interface Text Widget Text Selected', 'user_interface.wcol_text.text_sel'),
        ('User Interface Toggle Widget Inner', 'user_interface.wcol_toggle.inner'),
        ('User Interface Toggle Widget Inner Selected', 'user_interface.wcol_toggle.inner_sel'),
        ('User Interface Toggle Widget Item', 'user_interface.wcol_toggle.item'),
        ('User Interface Toggle Widget Outline', 'user_interface.wcol_toggle.outline'),
        ('User Interface Toggle Widget Outline Selected', 'user_interface.wcol_toggle.outline_sel'),
        ('User Interface Toggle Widget Text', 'user_interface.wcol_toggle.text'),
        ('User Interface Toggle Widget Text Selected', 'user_interface.wcol_toggle.text_sel'),
        ('User Interface Tooltip Inner', 'user_interface.wcol_tooltip.inner'),
        ('User Interface Tooltip Inner Selected', 'user_interface.wcol_tooltip.inner_sel'),
        ('User Interface Tooltip Item', 'user_interface.wcol_tooltip.item'),
        ('User Interface Tooltip Outline', 'user_interface.wcol_tooltip.outline'),
        ('User Interface Tooltip Outline Selected', 'user_interface.wcol_tooltip.outline_sel'),
        ('User Interface Tooltip Text', 'user_interface.wcol_tooltip.text'),
        ('User Interface Tooltip Text Selected', 'user_interface.wcol_tooltip.text_sel'),
        ('User Interface Widget Emboss', 'user_interface.widget_emboss'),
        ('User Interface Text Cursor', 'user_interface.widget_text_cursor'),
    ],
    'MD_03': [
        ('Regions Sidebars Background', 'regions.sidebars.back'),
        ('Regions Sidebars Navigation/Tabs Background', 'regions.sidebars.tab_back'),
        ('User Interface Panel Active', 'user_interface.panel_active'),
        ('User Interface Panel Back', 'user_interface.panel_back'),
        ('User Interface Panel Header', 'user_interface.panel_header'),
        ('User Interface Panel Outline', 'user_interface.panel_outline'),
        ('User Interface Panel Sub Back', 'user_interface.panel_sub_back'),
        ('User Interface Panel Text', 'user_interface.panel_text'),
        ('User Interface Panel Title', 'user_interface.panel_title'),
        ('User Interface Box Inner', 'user_interface.wcol_box.inner'),
        ('User Interface Box Inner Selected', 'user_interface.wcol_box.inner_sel'),
        ('User Interface Box Item', 'user_interface.wcol_box.item'),
        ('User Interface Box Outline', 'user_interface.wcol_box.outline'),
        ('User Interface Box Outline Selected', 'user_interface.wcol_box.outline_sel'),
        ('User Interface Box Text', 'user_interface.wcol_box.text'),
        ('User Interface Box Text Selected', 'user_interface.wcol_box.text_sel'),
        ('User Interface Curve Widget Inner', 'user_interface.wcol_curve.inner'),
        ('User Interface Curve Widget Inner Selected', 'user_interface.wcol_curve.inner_sel'),
        ('User Interface Curve Widget Item', 'user_interface.wcol_curve.item'),
        ('User Interface Curve Widget Outline', 'user_interface.wcol_curve.outline'),
        ('User Interface Curve Widget Outline Selected', 'user_interface.wcol_curve.outline_sel'),
        ('User Interface Curve Widget Text', 'user_interface.wcol_curve.text'),
        ('User Interface Curve Widget Text Selected', 'user_interface.wcol_curve.text_sel'),
        ('User Interface List Item Inner', 'user_interface.wcol_list_item.inner'),
        ('User Interface List Item Inner Selected', 'user_interface.wcol_list_item.inner_sel'),
        ('User Interface List Item Item', 'user_interface.wcol_list_item.item'),
        ('User Interface List Item Outline', 'user_interface.wcol_list_item.outline'),
        ('User Interface List Item Outline Selected', 'user_interface.wcol_list_item.outline_sel'),
        ('User Interface List Item Text', 'user_interface.wcol_list_item.text'),
        ('User Interface List Item Text Selected', 'user_interface.wcol_list_item.text_sel'),
        ('User Interface Number Widget Inner', 'user_interface.wcol_num.inner'),
        ('User Interface Number Widget Inner Selected', 'user_interface.wcol_num.inner_sel'),
        ('User Interface Number Widget Item', 'user_interface.wcol_num.item'),
        ('User Interface Number Widget Outline', 'user_interface.wcol_num.outline'),
        ('User Interface Number Widget Outline Selected', 'user_interface.wcol_num.outline_sel'),
        ('User Interface Number Widget Text', 'user_interface.wcol_num.text'),
        ('User Interface Number Widget Text Selected', 'user_interface.wcol_num.text_sel'),
        ('User Interface Slider Widget Inner', 'user_interface.wcol_numslider.inner'),
        ('User Interface Slider Widget Inner Selected', 'user_interface.wcol_numslider.inner_sel'),
        ('User Interface Slider Widget Item', 'user_interface.wcol_numslider.item'),
        ('User Interface Slider Widget Outline', 'user_interface.wcol_numslider.outline'),
        ('User Interface Slider Widget Outline Selected', 'user_interface.wcol_numslider.outline_sel'),
        ('User Interface Slider Widget Text', 'user_interface.wcol_numslider.text'),
        ('User Interface Slider Widget Text Selected', 'user_interface.wcol_numslider.text_sel'),
        ('User Interface Option Widget Inner', 'user_interface.wcol_option.inner'),
        ('User Interface Option Widget Inner Selected', 'user_interface.wcol_option.inner_sel'),
        ('User Interface Option Widget Item', 'user_interface.wcol_option.item'),
        ('User Interface Option Widget Outline', 'user_interface.wcol_option.outline'),
        ('User Interface Option Widget Outline Selected', 'user_interface.wcol_option.outline_sel'),
        ('User Interface Option Widget Text', 'user_interface.wcol_option.text'),
        ('User Interface Option Widget Text Selected', 'user_interface.wcol_option.text_sel'),
        ('User Interface Progress Bar Inner', 'user_interface.wcol_progress.inner'),
        ('User Interface Progress Bar Inner Selected', 'user_interface.wcol_progress.inner_sel'),
        ('User Interface Progress Bar Item', 'user_interface.wcol_progress.item'),
        ('User Interface Progress Bar Outline', 'user_interface.wcol_progress.outline'),
        ('User Interface Progress Bar Outline Selected', 'user_interface.wcol_progress.outline_sel'),
        ('User Interface Progress Bar Text', 'user_interface.wcol_progress.text'),
        ('User Interface Progress Bar Text Selected', 'user_interface.wcol_progress.text_sel'),
        ('User Interface Radio Widget Inner', 'user_interface.wcol_radio.inner'),
        ('User Interface Radio Widget Inner Selected', 'user_interface.wcol_radio.inner_sel'),
        ('User Interface Radio Widget Item', 'user_interface.wcol_radio.item'),
        ('User Interface Radio Widget Outline', 'user_interface.wcol_radio.outline'),
        ('User Interface Radio Widget Outline Selected', 'user_interface.wcol_radio.outline_sel'),
        ('User Interface Radio Widget Text', 'user_interface.wcol_radio.text'),
        ('User Interface Radio Widget Text Selected', 'user_interface.wcol_radio.text_sel'),
        ('User Interface Regular Widget Inner', 'user_interface.wcol_regular.inner'),
        ('User Interface Regular Widget Inner Selected', 'user_interface.wcol_regular.inner_sel'),
        ('User Interface Regular Widget Item', 'user_interface.wcol_regular.item'),
        ('User Interface Regular Widget Outline', 'user_interface.wcol_regular.outline'),
        ('User Interface Regular Widget Outline Selected', 'user_interface.wcol_regular.outline_sel'),
        ('User Interface Regular Widget Text', 'user_interface.wcol_regular.text'),
        ('User Interface Regular Widget Text Selected', 'user_interface.wcol_regular.text_sel'),
        ('User Interface Scroll Widget Inner', 'user_interface.wcol_scroll.inner'),
        ('User Interface Scroll Widget Inner Selected', 'user_interface.wcol_scroll.inner_sel'),
        ('User Interface Scroll Widget Item', 'user_interface.wcol_scroll.item'),
        ('User Interface Scroll Widget Outline', 'user_interface.wcol_scroll.outline'),
        ('User Interface Scroll Widget Outline Selected', 'user_interface.wcol_scroll.outline_sel'),
        ('User Interface Scroll Widget Text', 'user_interface.wcol_scroll.text'),
        ('User Interface Scroll Widget Text Selected', 'user_interface.wcol_scroll.text_sel'),
        ('User Interface State Error', 'user_interface.wcol_state.error'),
        ('User Interface State Info', 'user_interface.wcol_state.info'),
        ('User Interface State Inner Anim', 'user_interface.wcol_state.inner_anim'),
        ('User Interface State Inner Anim Sel', 'user_interface.wcol_state.inner_anim_sel'),
        ('User Interface State Inner Changed', 'user_interface.wcol_state.inner_changed'),
        ('User Interface State Inner Changed Sel', 'user_interface.wcol_state.inner_changed_sel'),
        ('User Interface State Inner Driven', 'user_interface.wcol_state.inner_driven'),
        ('User Interface State Inner Driven Sel', 'user_interface.wcol_state.inner_driven_sel'),
        ('User Interface State Inner Key', 'user_interface.wcol_state.inner_key'),
        ('User Interface State Inner Key Sel', 'user_interface.wcol_state.inner_key_sel'),
        ('User Interface State Inner Overridden', 'user_interface.wcol_state.inner_overridden'),
        ('User Interface State Inner Overridden Sel', 'user_interface.wcol_state.inner_overridden_sel'),
        ('User Interface State Success', 'user_interface.wcol_state.success'),
        ('User Interface State Warning', 'user_interface.wcol_state.warning'),
        ('User Interface Tab Inner', 'user_interface.wcol_tab.inner'),
        ('User Interface Tab Inner Selected', 'user_interface.wcol_tab.inner_sel'),
        ('User Interface Tab Item', 'user_interface.wcol_tab.item'),
        ('User Interface Tab Outline', 'user_interface.wcol_tab.outline'),
        ('User Interface Tab Outline Selected', 'user_interface.wcol_tab.outline_sel'),
        ('User Interface Tab Text', 'user_interface.wcol_tab.text'),
        ('User Interface Tab Text Selected', 'user_interface.wcol_tab.text_sel'),
        ('User Interface Text Widget Inner', 'user_interface.wcol_text.inner'),
        ('User Interface Text Widget Inner Selected', 'user_interface.wcol_text.inner_sel'),
        ('User Interface Text Widget Item', 'user_interface.wcol_text.item'),
        ('User Interface Text Widget Outline', 'user_interface.wcol_text.outline'),
        ('User Interface Text Widget Outline Selected', 'user_interface.wcol_text.outline_sel'),
        ('User Interface Text Widget Text', 'user_interface.wcol_text.text'),
        ('User Interface Text Widget Text Selected', 'user_interface.wcol_text.text_sel'),
        ('User Interface Toggle Widget Inner', 'user_interface.wcol_toggle.inner'),
        ('User Interface Toggle Widget Inner Selected', 'user_interface.wcol_toggle.inner_sel'),
        ('User Interface Toggle Widget Item', 'user_interface.wcol_toggle.item'),
        ('User Interface Toggle Widget Outline', 'user_interface.wcol_toggle.outline'),
        ('User Interface Toggle Widget Outline Selected', 'user_interface.wcol_toggle.outline_sel'),
        ('User Interface Toggle Widget Text', 'user_interface.wcol_toggle.text'),
        ('User Interface Toggle Widget Text Selected', 'user_interface.wcol_toggle.text_sel'),
        ('User Interface Widget Emboss', 'user_interface.widget_emboss'),
        ('User Interface Text Cursor', 'user_interface.widget_text_cursor'),
    ],
    'TOP_BAR_AREA': [
        ('Top Bar Space Background', 'topbar.space.back'),
        ('Top Bar Space Header', 'topbar.space.header'),
        ('Top Bar Space Header Text', 'topbar.space.header_text'),
        ('Top Bar Space Header Text Hi', 'topbar.space.header_text_hi'),
        ('Top Bar Space Text', 'topbar.space.text'),
        ('Top Bar Space Text Hi', 'topbar.space.text_hi'),
        ('Top Bar Space Title', 'topbar.space.title'),
    ],
    'STATUS_BAR_AREA': [
        ('Status Bar Space Background', 'statusbar.space.back'),
        ('Status Bar Space Header', 'statusbar.space.header'),
        ('Status Bar Space Header Text', 'statusbar.space.header_text'),
        ('Status Bar Space Header Text Hi', 'statusbar.space.header_text_hi'),
        ('Status Bar Space Text', 'statusbar.space.text'),
        ('Status Bar Space Text Hi', 'statusbar.space.text_hi'),
        ('Status Bar Space Title', 'statusbar.space.title'),
    ],
    'SCREEN_BOUNDARY_AREA': [
        ('User Interface Editor Border', 'user_interface.editor_border'),
        ('User Interface Editor Outline', 'user_interface.editor_outline'),
        ('User Interface Editor Outline Active', 'user_interface.editor_outline_active'),
    ],
    'MD_04': [
        ('User Interface Tool Widget Inner', 'user_interface.wcol_tool.inner'),
        ('User Interface Tool Widget Inner Selected', 'user_interface.wcol_tool.inner_sel'),
        ('User Interface Tool Widget Item', 'user_interface.wcol_tool.item'),
        ('User Interface Tool Widget Outline', 'user_interface.wcol_tool.outline'),
        ('User Interface Tool Widget Outline Selected', 'user_interface.wcol_tool.outline_sel'),
        ('User Interface Tool Widget Text', 'user_interface.wcol_tool.text'),
        ('User Interface Tool Widget Text Selected', 'user_interface.wcol_tool.text_sel'),
        ('User Interface Toolbar Item Inner', 'user_interface.wcol_toolbar_item.inner'),
        ('User Interface Toolbar Item Inner Selected', 'user_interface.wcol_toolbar_item.inner_sel'),
        ('User Interface Toolbar Item Item', 'user_interface.wcol_toolbar_item.item'),
        ('User Interface Toolbar Item Outline', 'user_interface.wcol_toolbar_item.outline'),
        ('User Interface Toolbar Item Outline Selected', 'user_interface.wcol_toolbar_item.outline_sel'),
        ('User Interface Toolbar Item Text', 'user_interface.wcol_toolbar_item.text'),
        ('User Interface Toolbar Item Text Selected', 'user_interface.wcol_toolbar_item.text_sel'),
        ('User Interface Icon Autokey', 'user_interface.icon_autokey'),
        ('User Interface Icon Collection', 'user_interface.icon_collection'),
        ('User Interface Icon Folder', 'user_interface.icon_folder'),
        ('User Interface Icon Modifier', 'user_interface.icon_modifier'),
        ('User Interface Icon Object', 'user_interface.icon_object'),
        ('User Interface Icon Object Data', 'user_interface.icon_object_data'),
        ('User Interface Icon Scene', 'user_interface.icon_scene'),
        ('User Interface Icon Shading', 'user_interface.icon_shading'),
    ],
    'MD_05': [
        ('User Interface Axis W', 'user_interface.axis_w'),
        ('User Interface Axis X', 'user_interface.axis_x'),
        ('User Interface Axis Y', 'user_interface.axis_y'),
        ('User Interface Axis Z', 'user_interface.axis_z'),
        ('User Interface Gizmo A', 'user_interface.gizmo_a'),
        ('User Interface Gizmo B', 'user_interface.gizmo_b'),
        ('User Interface Gizmo Hi', 'user_interface.gizmo_hi'),
        ('User Interface Gizmo Primary', 'user_interface.gizmo_primary'),
        ('User Interface Gizmo Secondary', 'user_interface.gizmo_secondary'),
        ('User Interface Gizmo View Align', 'user_interface.gizmo_view_align'),
    ],
    'VIEW_3D_GIZMO_AREA': [
        ('User Interface Axis W', 'user_interface.axis_w'),
        ('User Interface Axis X', 'user_interface.axis_x'),
        ('User Interface Axis Y', 'user_interface.axis_y'),
        ('User Interface Axis Z', 'user_interface.axis_z'),
        ('User Interface Gizmo View Align', 'user_interface.gizmo_view_align'),
        ('User Interface Gizmo Hi', 'user_interface.gizmo_hi'),
        ('User Interface Gizmo A', 'user_interface.gizmo_a'),
        ('User Interface Gizmo B', 'user_interface.gizmo_b'),
        ('User Interface Gizmo Primary', 'user_interface.gizmo_primary'),
        ('User Interface Gizmo Secondary', 'user_interface.gizmo_secondary'),
    ],
    'VIEW_3D_NAVIGATION_AREA': [
        ('User Interface Gizmo Primary', 'user_interface.gizmo_primary'),
        ('User Interface Gizmo Secondary', 'user_interface.gizmo_secondary'),
        ('User Interface Gizmo Hi', 'user_interface.gizmo_hi'),
        ('User Interface Gizmo A', 'user_interface.gizmo_a'),
        ('User Interface Gizmo B', 'user_interface.gizmo_b'),
        ('User Interface Gizmo View Align', 'user_interface.gizmo_view_align'),
    ],
    'UI_NAVIGATION_AREA': [
        ('User Interface Icon Autokey', 'user_interface.icon_autokey'),
        ('User Interface Icon Collection', 'user_interface.icon_collection'),
        ('User Interface Icon Folder', 'user_interface.icon_folder'),
        ('User Interface Icon Modifier', 'user_interface.icon_modifier'),
        ('User Interface Icon Object', 'user_interface.icon_object'),
        ('User Interface Icon Object Data', 'user_interface.icon_object_data'),
        ('User Interface Icon Scene', 'user_interface.icon_scene'),
        ('User Interface Icon Shading', 'user_interface.icon_shading'),
        ('User Interface Number Widget Inner', 'user_interface.wcol_num.inner'),
        ('User Interface Option Widget Inner', 'user_interface.wcol_option.inner'),
        ('User Interface Option Widget Inner Selected', 'user_interface.wcol_option.inner_sel'),
        ('User Interface Option Widget Outline', 'user_interface.wcol_option.outline'),
        ('Regions Sidebars Navigation/Tabs Background', 'regions.sidebars.tab_back'),
        ('User Interface Panel Back', 'user_interface.panel_back'),
        ('User Interface Panel Header', 'user_interface.panel_header'),
        ('User Interface Panel Outline', 'user_interface.panel_outline'),
        ('User Interface Panel Sub Back', 'user_interface.panel_sub_back'),
        ('User Interface Panel Text', 'user_interface.panel_text'),
        ('User Interface Panel Title', 'user_interface.panel_title'),
        ('User Interface Tab Inner', 'user_interface.wcol_tab.inner'),
        ('User Interface Tab Inner Selected', 'user_interface.wcol_tab.inner_sel'),
        ('User Interface Tab Item', 'user_interface.wcol_tab.item'),
        ('User Interface Tab Outline', 'user_interface.wcol_tab.outline'),
        ('User Interface Tab Outline Selected', 'user_interface.wcol_tab.outline_sel'),
        ('User Interface Tab Text', 'user_interface.wcol_tab.text'),
        ('User Interface Tab Text Selected', 'user_interface.wcol_tab.text_sel'),
        ('User Interface Tool Widget Inner', 'user_interface.wcol_tool.inner'),
        ('User Interface Tool Widget Inner Selected', 'user_interface.wcol_tool.inner_sel'),
        ('User Interface Tool Widget Item', 'user_interface.wcol_tool.item'),
        ('User Interface Tool Widget Outline', 'user_interface.wcol_tool.outline'),
        ('User Interface Tool Widget Outline Selected', 'user_interface.wcol_tool.outline_sel'),
        ('User Interface Tool Widget Text', 'user_interface.wcol_tool.text'),
        ('User Interface Tool Widget Text Selected', 'user_interface.wcol_tool.text_sel'),
        ('User Interface Toolbar Item Inner', 'user_interface.wcol_toolbar_item.inner'),
        ('User Interface Toolbar Item Inner Selected', 'user_interface.wcol_toolbar_item.inner_sel'),
        ('User Interface Toolbar Item Item', 'user_interface.wcol_toolbar_item.item'),
        ('User Interface Toolbar Item Outline', 'user_interface.wcol_toolbar_item.outline'),
        ('User Interface Toolbar Item Outline Selected', 'user_interface.wcol_toolbar_item.outline_sel'),
        ('User Interface Toolbar Item Text', 'user_interface.wcol_toolbar_item.text'),
        ('User Interface Toolbar Item Text Selected', 'user_interface.wcol_toolbar_item.text_sel'),
    ],
    'MD_06': [
        ('3D View After Current Frame', 'view_3d.after_current_frame'),
        ('3D View Before Current Frame', 'view_3d.before_current_frame'),
        ('3D View Bundle Solid', 'view_3d.bundle_solid'),
        ('3D View Camera', 'view_3d.camera'),
        ('3D View Camera Passepartout', 'view_3d.camera_passepartout'),
        ('3D View Camera Path', 'view_3d.camera_path'),
        ('3D View Clipping Border 3D', 'view_3d.clipping_border_3d'),
        ('3D View Empty', 'view_3d.empty'),
        ('3D View Freestyle', 'view_3d.freestyle'),
        ('3D View Grid', 'view_3d.grid'),
        ('3D View Grid Major', 'view_3d.grid_major'),
        ('3D View Light', 'view_3d.light'),
        ('3D View Object Active', 'view_3d.object_active'),
        ('3D View Object Selected', 'view_3d.object_selected'),
        ('3D View Space Gradients Gradient', 'view_3d.space.gradients.gradient'),
        ('3D View Space Gradients High Gradient', 'view_3d.space.gradients.high_gradient'),
        ('3D View Space Header', 'view_3d.space.header'),
        ('3D View Space Header Text', 'view_3d.space.header_text'),
        ('3D View Space Header Text Hi', 'view_3d.space.header_text_hi'),
        ('3D View Space Text', 'view_3d.space.text'),
        ('3D View Space Text Hi', 'view_3d.space.text_hi'),
        ('3D View Space Title', 'view_3d.space.title'),
        ('3D View Speaker', 'view_3d.speaker'),
        ('3D View Transform', 'view_3d.transform'),
        ('3D View View Overlay', 'view_3d.view_overlay'),
        ('3D View Wire', 'view_3d.wire'),
        ('User Interface Icon Autokey', 'user_interface.icon_autokey'),
        ('User Interface Icon Collection', 'user_interface.icon_collection'),
        ('User Interface Icon Folder', 'user_interface.icon_folder'),
        ('User Interface Icon Modifier', 'user_interface.icon_modifier'),
        ('User Interface Icon Object', 'user_interface.icon_object'),
        ('User Interface Icon Object Data', 'user_interface.icon_object_data'),
        ('User Interface Icon Scene', 'user_interface.icon_scene'),
        ('User Interface Icon Shading', 'user_interface.icon_shading'),
        ('User Interface Curve Widget Inner', 'user_interface.wcol_curve.inner'),
        ('User Interface Curve Widget Inner Selected', 'user_interface.wcol_curve.inner_sel'),
        ('User Interface Curve Widget Item', 'user_interface.wcol_curve.item'),
        ('User Interface Curve Widget Outline', 'user_interface.wcol_curve.outline'),
        ('User Interface Curve Widget Outline Selected', 'user_interface.wcol_curve.outline_sel'),
        ('User Interface Curve Widget Text', 'user_interface.wcol_curve.text'),
        ('User Interface Curve Widget Text Selected', 'user_interface.wcol_curve.text_sel'),
        ('User Interface Number Widget Inner', 'user_interface.wcol_num.inner'),
        ('User Interface Number Widget Inner Selected', 'user_interface.wcol_num.inner_sel'),
        ('User Interface Number Widget Item', 'user_interface.wcol_num.item'),
        ('User Interface Number Widget Outline', 'user_interface.wcol_num.outline'),
        ('User Interface Number Widget Outline Selected', 'user_interface.wcol_num.outline_sel'),
        ('User Interface Number Widget Text', 'user_interface.wcol_num.text'),
        ('User Interface Number Widget Text Selected', 'user_interface.wcol_num.text_sel'),
        ('User Interface Slider Widget Inner', 'user_interface.wcol_numslider.inner'),
        ('User Interface Slider Widget Inner Selected', 'user_interface.wcol_numslider.inner_sel'),
        ('User Interface Slider Widget Item', 'user_interface.wcol_numslider.item'),
        ('User Interface Slider Widget Outline', 'user_interface.wcol_numslider.outline'),
        ('User Interface Slider Widget Outline Selected', 'user_interface.wcol_numslider.outline_sel'),
        ('User Interface Slider Widget Text', 'user_interface.wcol_numslider.text'),
        ('User Interface Slider Widget Text Selected', 'user_interface.wcol_numslider.text_sel'),
        ('User Interface Option Widget Inner', 'user_interface.wcol_option.inner'),
        ('User Interface Option Widget Inner Selected', 'user_interface.wcol_option.inner_sel'),
        ('User Interface Option Widget Item', 'user_interface.wcol_option.item'),
        ('User Interface Option Widget Outline', 'user_interface.wcol_option.outline'),
        ('User Interface Option Widget Outline Selected', 'user_interface.wcol_option.outline_sel'),
        ('User Interface Option Widget Text', 'user_interface.wcol_option.text'),
        ('User Interface Option Widget Text Selected', 'user_interface.wcol_option.text_sel'),
        ('User Interface Radio Widget Inner', 'user_interface.wcol_radio.inner'),
        ('User Interface Radio Widget Inner Selected', 'user_interface.wcol_radio.inner_sel'),
        ('User Interface Radio Widget Item', 'user_interface.wcol_radio.item'),
        ('User Interface Radio Widget Outline', 'user_interface.wcol_radio.outline'),
        ('User Interface Radio Widget Outline Selected', 'user_interface.wcol_radio.outline_sel'),
        ('User Interface Radio Widget Text', 'user_interface.wcol_radio.text'),
        ('User Interface Radio Widget Text Selected', 'user_interface.wcol_radio.text_sel'),
        ('User Interface Regular Widget Inner', 'user_interface.wcol_regular.inner'),
        ('User Interface Regular Widget Inner Selected', 'user_interface.wcol_regular.inner_sel'),
        ('User Interface Regular Widget Item', 'user_interface.wcol_regular.item'),
        ('User Interface Regular Widget Outline', 'user_interface.wcol_regular.outline'),
        ('User Interface Regular Widget Outline Selected', 'user_interface.wcol_regular.outline_sel'),
        ('User Interface Regular Widget Text', 'user_interface.wcol_regular.text'),
        ('User Interface Regular Widget Text Selected', 'user_interface.wcol_regular.text_sel'),
        ('User Interface Text Widget Inner', 'user_interface.wcol_text.inner'),
        ('User Interface Text Widget Inner Selected', 'user_interface.wcol_text.inner_sel'),
        ('User Interface Text Widget Item', 'user_interface.wcol_text.item'),
        ('User Interface Text Widget Outline', 'user_interface.wcol_text.outline'),
        ('User Interface Text Widget Outline Selected', 'user_interface.wcol_text.outline_sel'),
        ('User Interface Text Widget Text', 'user_interface.wcol_text.text'),
        ('User Interface Text Widget Text Selected', 'user_interface.wcol_text.text_sel'),
        ('User Interface Toggle Widget Inner', 'user_interface.wcol_toggle.inner'),
        ('User Interface Toggle Widget Inner Selected', 'user_interface.wcol_toggle.inner_sel'),
        ('User Interface Toggle Widget Item', 'user_interface.wcol_toggle.item'),
        ('User Interface Toggle Widget Outline', 'user_interface.wcol_toggle.outline'),
        ('User Interface Toggle Widget Outline Selected', 'user_interface.wcol_toggle.outline_sel'),
        ('User Interface Toggle Widget Text', 'user_interface.wcol_toggle.text'),
        ('User Interface Toggle Widget Text Selected', 'user_interface.wcol_toggle.text_sel'),
        ('User Interface Widget Emboss', 'user_interface.widget_emboss'),
        ('User Interface Text Cursor', 'user_interface.widget_text_cursor'),
    ],
    'MD_07': [
        ('3D View Bevel', 'view_3d.bevel'),
        ('3D View Crease', 'view_3d.crease'),
        ('3D View Edge Mode Select', 'view_3d.edge_mode_select'),
        ('3D View Edge Select', 'view_3d.edge_select'),
        ('3D View Editmesh Active', 'view_3d.editmesh_active'),
        ('3D View Extra Edge Angle', 'view_3d.extra_edge_angle'),
        ('3D View Extra Edge Len', 'view_3d.extra_edge_len'),
        ('3D View Extra Face Angle', 'view_3d.extra_face_angle'),
        ('3D View Extra Face Area', 'view_3d.extra_face_area'),
        ('3D View Face', 'view_3d.face'),
        ('3D View Face Back', 'view_3d.face_back'),
        ('3D View Face Front', 'view_3d.face_front'),
        ('3D View Face Mode Select', 'view_3d.face_mode_select'),
        ('3D View Face Retopology', 'view_3d.face_retopology'),
        ('3D View Face Select', 'view_3d.face_select'),
        ('3D View Normal', 'view_3d.normal'),
        ('3D View Seam', 'view_3d.seam'),
        ('3D View Sharp', 'view_3d.sharp'),
        ('3D View Skin Root', 'view_3d.skin_root'),
        ('3D View Split Normal', 'view_3d.split_normal'),
        ('3D View Vertex', 'view_3d.vertex'),
        ('3D View Vertex Normal', 'view_3d.vertex_normal'),
        ('3D View Vertex Select', 'view_3d.vertex_select'),
        ('3D View Vertex Unreferenced', 'view_3d.vertex_unreferenced'),
        ('3D View Wire Edit', 'view_3d.wire_edit'),
    ],
    'MD_08': [
        ('Common Curves Handle Align', 'common.curves.handle_align'),
        ('Common Curves Handle Auto', 'common.curves.handle_auto'),
        ('Common Curves Handle Auto Clamped', 'common.curves.handle_auto_clamped'),
        ('Common Curves Handle Free', 'common.curves.handle_free'),
        ('Common Curves Handle Sel Align', 'common.curves.handle_sel_align'),
        ('Common Curves Handle Sel Auto', 'common.curves.handle_sel_auto'),
        ('Common Curves Handle Sel Auto Clamped', 'common.curves.handle_sel_auto_clamped'),
        ('Common Curves Handle Sel Free', 'common.curves.handle_sel_free'),
        ('Common Curves Handle Sel Vect', 'common.curves.handle_sel_vect'),
        ('Common Curves Handle Vect', 'common.curves.handle_vect'),
        ('Common Curves Handle Vertex', 'common.curves.handle_vertex'),
        ('Common Curves Handle Vertex Select', 'common.curves.handle_vertex_select'),
        ('3D View Nurb Sel Uline', 'view_3d.nurb_sel_uline'),
        ('3D View Nurb Sel Vline', 'view_3d.nurb_sel_vline'),
        ('3D View Nurb Uline', 'view_3d.nurb_uline'),
        ('3D View Nurb Vline', 'view_3d.nurb_vline'),
        ('User Interface Curve Widget Inner', 'user_interface.wcol_curve.inner'),
        ('User Interface Curve Widget Inner Selected', 'user_interface.wcol_curve.inner_sel'),
        ('User Interface Curve Widget Item', 'user_interface.wcol_curve.item'),
        ('User Interface Curve Widget Outline', 'user_interface.wcol_curve.outline'),
        ('User Interface Curve Widget Outline Selected', 'user_interface.wcol_curve.outline_sel'),
        ('User Interface Curve Widget Text', 'user_interface.wcol_curve.text'),
        ('User Interface Curve Widget Text Selected', 'user_interface.wcol_curve.text_sel'),
    ],
    'MD_09': [
        ('Bone Color Set 0 Active', 'bone_color_sets[0].active'),
        ('Bone Color Set 0 Normal', 'bone_color_sets[0].normal'),
        ('Bone Color Set 0 Select', 'bone_color_sets[0].select'),
        ('Bone Color Set 10 Active', 'bone_color_sets[10].active'),
        ('Bone Color Set 10 Normal', 'bone_color_sets[10].normal'),
        ('Bone Color Set 10 Select', 'bone_color_sets[10].select'),
        ('Bone Color Set 11 Active', 'bone_color_sets[11].active'),
        ('Bone Color Set 11 Normal', 'bone_color_sets[11].normal'),
        ('Bone Color Set 11 Select', 'bone_color_sets[11].select'),
        ('Bone Color Set 12 Active', 'bone_color_sets[12].active'),
        ('Bone Color Set 12 Normal', 'bone_color_sets[12].normal'),
        ('Bone Color Set 12 Select', 'bone_color_sets[12].select'),
        ('Bone Color Set 13 Active', 'bone_color_sets[13].active'),
        ('Bone Color Set 13 Normal', 'bone_color_sets[13].normal'),
        ('Bone Color Set 13 Select', 'bone_color_sets[13].select'),
        ('Bone Color Set 14 Active', 'bone_color_sets[14].active'),
        ('Bone Color Set 14 Normal', 'bone_color_sets[14].normal'),
        ('Bone Color Set 14 Select', 'bone_color_sets[14].select'),
        ('Bone Color Set 15 Active', 'bone_color_sets[15].active'),
        ('Bone Color Set 15 Normal', 'bone_color_sets[15].normal'),
        ('Bone Color Set 15 Select', 'bone_color_sets[15].select'),
        ('Bone Color Set 16 Active', 'bone_color_sets[16].active'),
        ('Bone Color Set 16 Normal', 'bone_color_sets[16].normal'),
        ('Bone Color Set 16 Select', 'bone_color_sets[16].select'),
        ('Bone Color Set 17 Active', 'bone_color_sets[17].active'),
        ('Bone Color Set 17 Normal', 'bone_color_sets[17].normal'),
        ('Bone Color Set 17 Select', 'bone_color_sets[17].select'),
        ('Bone Color Set 18 Active', 'bone_color_sets[18].active'),
        ('Bone Color Set 18 Normal', 'bone_color_sets[18].normal'),
        ('Bone Color Set 18 Select', 'bone_color_sets[18].select'),
        ('Bone Color Set 19 Active', 'bone_color_sets[19].active'),
        ('Bone Color Set 19 Normal', 'bone_color_sets[19].normal'),
        ('Bone Color Set 19 Select', 'bone_color_sets[19].select'),
        ('Bone Color Set 1 Active', 'bone_color_sets[1].active'),
        ('Bone Color Set 1 Normal', 'bone_color_sets[1].normal'),
        ('Bone Color Set 1 Select', 'bone_color_sets[1].select'),
        ('Bone Color Set 2 Active', 'bone_color_sets[2].active'),
        ('Bone Color Set 2 Normal', 'bone_color_sets[2].normal'),
        ('Bone Color Set 2 Select', 'bone_color_sets[2].select'),
        ('Bone Color Set 3 Active', 'bone_color_sets[3].active'),
        ('Bone Color Set 3 Normal', 'bone_color_sets[3].normal'),
        ('Bone Color Set 3 Select', 'bone_color_sets[3].select'),
        ('Bone Color Set 4 Active', 'bone_color_sets[4].active'),
        ('Bone Color Set 4 Normal', 'bone_color_sets[4].normal'),
        ('Bone Color Set 4 Select', 'bone_color_sets[4].select'),
        ('Bone Color Set 5 Active', 'bone_color_sets[5].active'),
        ('Bone Color Set 5 Normal', 'bone_color_sets[5].normal'),
        ('Bone Color Set 5 Select', 'bone_color_sets[5].select'),
        ('Bone Color Set 6 Active', 'bone_color_sets[6].active'),
        ('Bone Color Set 6 Normal', 'bone_color_sets[6].normal'),
        ('Bone Color Set 6 Select', 'bone_color_sets[6].select'),
        ('Bone Color Set 7 Active', 'bone_color_sets[7].active'),
        ('Bone Color Set 7 Normal', 'bone_color_sets[7].normal'),
        ('Bone Color Set 7 Select', 'bone_color_sets[7].select'),
        ('Bone Color Set 8 Active', 'bone_color_sets[8].active'),
        ('Bone Color Set 8 Normal', 'bone_color_sets[8].normal'),
        ('Bone Color Set 8 Select', 'bone_color_sets[8].select'),
        ('Bone Color Set 9 Active', 'bone_color_sets[9].active'),
        ('Bone Color Set 9 Normal', 'bone_color_sets[9].normal'),
        ('Bone Color Set 9 Select', 'bone_color_sets[9].select'),
        ('3D View Bone Locked Weight', 'view_3d.bone_locked_weight'),
        ('3D View Bone Pose', 'view_3d.bone_pose'),
        ('3D View Bone Pose Active', 'view_3d.bone_pose_active'),
        ('3D View Bone Solid', 'view_3d.bone_solid'),
    ],
    'MD_10': [
        ('3D View Gp Vertex', 'view_3d.gp_vertex'),
        ('3D View Gp Vertex Select', 'view_3d.gp_vertex_select'),
        ('3D View Gp Wire Edit', 'view_3d.gp_wire_edit'),
        ('3D View Text Grease Pencil', 'view_3d.text_grease_pencil'),
    ],
    'MD_11': [
        ('Common Animation Channel', 'common.anim.channel'),
        ('Common Animation Channel Group', 'common.anim.channel_group'),
        ('Common Animation Channel Group Active', 'common.anim.channel_group_active'),
        ('Common Animation Channel Selected', 'common.anim.channel_selected'),
        ('Common Animation Channels', 'common.anim.channels'),
        ('Common Animation Channels Sub', 'common.anim.channels_sub'),
        ('Common Animation Keyframe', 'common.anim.keyframe'),
        ('Common Animation Keyframe Breakdown', 'common.anim.keyframe_breakdown'),
        ('Common Animation Keyframe Breakdown Selected', 'common.anim.keyframe_breakdown_selected'),
        ('Common Animation Keyframe Extreme', 'common.anim.keyframe_extreme'),
        ('Common Animation Keyframe Extreme Selected', 'common.anim.keyframe_extreme_selected'),
        ('Common Animation Keyframe Generated', 'common.anim.keyframe_generated'),
        ('Common Animation Keyframe Generated Selected', 'common.anim.keyframe_generated_selected'),
        ('Common Animation Keyframe Jitter', 'common.anim.keyframe_jitter'),
        ('Common Animation Keyframe Jitter Selected', 'common.anim.keyframe_jitter_selected'),
        ('Common Animation Keyframe Moving Hold', 'common.anim.keyframe_moving_hold'),
        ('Common Animation Keyframe Moving Hold Selected', 'common.anim.keyframe_moving_hold_selected'),
        ('Common Animation Keyframe Selected', 'common.anim.keyframe_selected'),
        ('Common Animation Long Key', 'common.anim.long_key'),
        ('Common Animation Long Key Selected', 'common.anim.long_key_selected'),
        ('Common Animation Playhead', 'common.anim.playhead'),
        ('Common Animation Preview Range', 'common.anim.preview_range'),
        ('Common Animation Scene Strip Range', 'common.anim.scene_strip_range'),
        ('Dope Sheet Anim Interpolation Constant', 'dopesheet_editor.anim_interpolation_constant'),
        ('Dope Sheet Anim Interpolation Linear', 'dopesheet_editor.anim_interpolation_linear'),
        ('Dope Sheet Anim Interpolation Other', 'dopesheet_editor.anim_interpolation_other'),
        ('Dope Sheet Grid', 'dopesheet_editor.grid'),
        ('Dope Sheet Keyframe Border', 'dopesheet_editor.keyframe_border'),
        ('Dope Sheet Keyframe Border Selected', 'dopesheet_editor.keyframe_border_selected'),
        ('Dope Sheet Simulated Frames', 'dopesheet_editor.simulated_frames'),
        ('Dope Sheet Space Background', 'dopesheet_editor.space.back'),
        ('Dope Sheet Space Header', 'dopesheet_editor.space.header'),
        ('Dope Sheet Space Header Text', 'dopesheet_editor.space.header_text'),
        ('Dope Sheet Space Header Text Hi', 'dopesheet_editor.space.header_text_hi'),
        ('Dope Sheet Space Text', 'dopesheet_editor.space.text'),
        ('Dope Sheet Space Text Hi', 'dopesheet_editor.space.text_hi'),
        ('Dope Sheet Space Title', 'dopesheet_editor.space.title'),
        ('Dope Sheet Summary', 'dopesheet_editor.summary'),
        ('Graph Editor Grid', 'graph_editor.grid'),
        ('Graph Editor Space Background', 'graph_editor.space.back'),
        ('Graph Editor Space Header', 'graph_editor.space.header'),
        ('Graph Editor Space Header Text', 'graph_editor.space.header_text'),
        ('Graph Editor Space Header Text Hi', 'graph_editor.space.header_text_hi'),
        ('Graph Editor Space Text', 'graph_editor.space.text'),
        ('Graph Editor Space Text Hi', 'graph_editor.space.text_hi'),
        ('Graph Editor Space Title', 'graph_editor.space.title'),
        ('Graph Editor Vertex', 'graph_editor.vertex'),
        ('Graph Editor Vertex Active', 'graph_editor.vertex_active'),
        ('Graph Editor Vertex Select', 'graph_editor.vertex_select'),
        ('NLA Editor Active Action', 'nla_editor.active_action'),
        ('NLA Editor Active Action Unset', 'nla_editor.active_action_unset'),
        ('NLA Editor Grid', 'nla_editor.grid'),
        ('NLA Editor Keyframe Border', 'nla_editor.keyframe_border'),
        ('NLA Editor Keyframe Border Selected', 'nla_editor.keyframe_border_selected'),
        ('NLA Editor Meta Strips', 'nla_editor.meta_strips'),
        ('NLA Editor Meta Strips Selected', 'nla_editor.meta_strips_selected'),
        ('NLA Editor Sound Strips', 'nla_editor.sound_strips'),
        ('NLA Editor Sound Strips Selected', 'nla_editor.sound_strips_selected'),
        ('NLA Editor Space Background', 'nla_editor.space.back'),
        ('NLA Editor Space Header', 'nla_editor.space.header'),
        ('NLA Editor Space Header Text', 'nla_editor.space.header_text'),
        ('NLA Editor Space Header Text Hi', 'nla_editor.space.header_text_hi'),
        ('NLA Editor Space Text', 'nla_editor.space.text'),
        ('NLA Editor Space Text Hi', 'nla_editor.space.text_hi'),
        ('NLA Editor Space Title', 'nla_editor.space.title'),
        ('NLA Editor Strips', 'nla_editor.strips'),
        ('NLA Editor Strips Selected', 'nla_editor.strips_selected'),
        ('NLA Editor Transition Strips', 'nla_editor.transition_strips'),
        ('NLA Editor Transition Strips Selected', 'nla_editor.transition_strips_selected'),
        ('NLA Editor Tweak', 'nla_editor.tweak'),
        ('NLA Editor Tweak Duplicate', 'nla_editor.tweak_duplicate'),
        ('Regions Channels Background', 'regions.channels.back'),
        ('Regions Channels Text', 'regions.channels.text'),
        ('Regions Channels Text Selected', 'regions.channels.text_selected'),
        ('Regions Scrubbing Background', 'regions.scrubbing.back'),
        ('Regions Scrubbing Text', 'regions.scrubbing.text'),
        ('Regions Scrubbing Time Marker', 'regions.scrubbing.time_marker'),
        ('Regions Scrubbing Time Marker Selected', 'regions.scrubbing.time_marker_selected'),
        ('User Interface Curve Widget Inner', 'user_interface.wcol_curve.inner'),
        ('User Interface Curve Widget Inner Selected', 'user_interface.wcol_curve.inner_sel'),
        ('User Interface Curve Widget Item', 'user_interface.wcol_curve.item'),
        ('User Interface Curve Widget Outline', 'user_interface.wcol_curve.outline'),
        ('User Interface Curve Widget Outline Selected', 'user_interface.wcol_curve.outline_sel'),
        ('User Interface Curve Widget Text', 'user_interface.wcol_curve.text'),
        ('User Interface Curve Widget Text Selected', 'user_interface.wcol_curve.text_sel'),
        ('User Interface Number Widget Inner', 'user_interface.wcol_num.inner'),
        ('User Interface Number Widget Inner Selected', 'user_interface.wcol_num.inner_sel'),
        ('User Interface Number Widget Item', 'user_interface.wcol_num.item'),
        ('User Interface Number Widget Outline', 'user_interface.wcol_num.outline'),
        ('User Interface Number Widget Outline Selected', 'user_interface.wcol_num.outline_sel'),
        ('User Interface Number Widget Text', 'user_interface.wcol_num.text'),
        ('User Interface Number Widget Text Selected', 'user_interface.wcol_num.text_sel'),
        ('User Interface Slider Widget Inner', 'user_interface.wcol_numslider.inner'),
        ('User Interface Slider Widget Inner Selected', 'user_interface.wcol_numslider.inner_sel'),
        ('User Interface Slider Widget Item', 'user_interface.wcol_numslider.item'),
        ('User Interface Slider Widget Outline', 'user_interface.wcol_numslider.outline'),
        ('User Interface Slider Widget Outline Selected', 'user_interface.wcol_numslider.outline_sel'),
        ('User Interface Slider Widget Text', 'user_interface.wcol_numslider.text'),
        ('User Interface Slider Widget Text Selected', 'user_interface.wcol_numslider.text_sel'),
        ('User Interface Option Widget Inner', 'user_interface.wcol_option.inner'),
        ('User Interface Option Widget Inner Selected', 'user_interface.wcol_option.inner_sel'),
        ('User Interface Option Widget Item', 'user_interface.wcol_option.item'),
        ('User Interface Option Widget Outline', 'user_interface.wcol_option.outline'),
        ('User Interface Option Widget Outline Selected', 'user_interface.wcol_option.outline_sel'),
        ('User Interface Option Widget Text', 'user_interface.wcol_option.text'),
        ('User Interface Option Widget Text Selected', 'user_interface.wcol_option.text_sel'),
        ('User Interface Radio Widget Inner', 'user_interface.wcol_radio.inner'),
        ('User Interface Radio Widget Inner Selected', 'user_interface.wcol_radio.inner_sel'),
        ('User Interface Radio Widget Item', 'user_interface.wcol_radio.item'),
        ('User Interface Radio Widget Outline', 'user_interface.wcol_radio.outline'),
        ('User Interface Radio Widget Outline Selected', 'user_interface.wcol_radio.outline_sel'),
        ('User Interface Radio Widget Text', 'user_interface.wcol_radio.text'),
        ('User Interface Radio Widget Text Selected', 'user_interface.wcol_radio.text_sel'),
        ('User Interface Regular Widget Inner', 'user_interface.wcol_regular.inner'),
        ('User Interface Regular Widget Inner Selected', 'user_interface.wcol_regular.inner_sel'),
        ('User Interface Regular Widget Item', 'user_interface.wcol_regular.item'),
        ('User Interface Regular Widget Outline', 'user_interface.wcol_regular.outline'),
        ('User Interface Regular Widget Outline Selected', 'user_interface.wcol_regular.outline_sel'),
        ('User Interface Regular Widget Text', 'user_interface.wcol_regular.text'),
        ('User Interface Regular Widget Text Selected', 'user_interface.wcol_regular.text_sel'),
        ('User Interface Text Widget Inner', 'user_interface.wcol_text.inner'),
        ('User Interface Text Widget Inner Selected', 'user_interface.wcol_text.inner_sel'),
        ('User Interface Text Widget Item', 'user_interface.wcol_text.item'),
        ('User Interface Text Widget Outline', 'user_interface.wcol_text.outline'),
        ('User Interface Text Widget Outline Selected', 'user_interface.wcol_text.outline_sel'),
        ('User Interface Text Widget Text', 'user_interface.wcol_text.text'),
        ('User Interface Text Widget Text Selected', 'user_interface.wcol_text.text_sel'),
        ('User Interface Toggle Widget Inner', 'user_interface.wcol_toggle.inner'),
        ('User Interface Toggle Widget Inner Selected', 'user_interface.wcol_toggle.inner_sel'),
        ('User Interface Toggle Widget Item', 'user_interface.wcol_toggle.item'),
        ('User Interface Toggle Widget Outline', 'user_interface.wcol_toggle.outline'),
        ('User Interface Toggle Widget Outline Selected', 'user_interface.wcol_toggle.outline_sel'),
        ('User Interface Toggle Widget Text', 'user_interface.wcol_toggle.text'),
        ('User Interface Toggle Widget Text Selected', 'user_interface.wcol_toggle.text_sel'),
        ('User Interface Widget Emboss', 'user_interface.widget_emboss'),
        ('User Interface Text Cursor', 'user_interface.widget_text_cursor'),
    ],
    'MD_12': [
        ('Node Editor Attribute Node', 'node_editor.attribute_node'),
        ('Node Editor Closure Zone', 'node_editor.closure_zone'),
        ('Node Editor Color Node', 'node_editor.color_node'),
        ('Node Editor Converter Node', 'node_editor.converter_node'),
        ('Node Editor Distor Node', 'node_editor.distor_node'),
        ('Node Editor Filter Node', 'node_editor.filter_node'),
        ('Node Editor Foreach Geometry Element Zone', 'node_editor.foreach_geometry_element_zone'),
        ('Node Editor Frame Node', 'node_editor.frame_node'),
        ('Node Editor Geometry Node', 'node_editor.geometry_node'),
        ('Node Editor Grid', 'node_editor.grid'),
        ('Node Editor Group Node', 'node_editor.group_node'),
        ('Node Editor Group Socket Node', 'node_editor.group_socket_node'),
        ('Node Editor Input Node', 'node_editor.input_node'),
        ('Node Editor Matte Node', 'node_editor.matte_node'),
        ('Node Editor Node Active', 'node_editor.node_active'),
        ('Node Editor Node Backdrop', 'node_editor.node_backdrop'),
        ('Node Editor Node Outline', 'node_editor.node_outline'),
        ('Node Editor Node Selected', 'node_editor.node_selected'),
        ('Node Editor Output Node', 'node_editor.output_node'),
        ('Node Editor Repeat Zone', 'node_editor.repeat_zone'),
        ('Node Editor Script Node', 'node_editor.script_node'),
        ('Node Editor Shader Node', 'node_editor.shader_node'),
        ('Node Editor Simulation Zone', 'node_editor.simulation_zone'),
        ('Node Editor Space Background', 'node_editor.space.back'),
        ('Node Editor Space Header', 'node_editor.space.header'),
        ('Node Editor Space Header Text', 'node_editor.space.header_text'),
        ('Node Editor Space Header Text Hi', 'node_editor.space.header_text_hi'),
        ('Node Editor Space Text', 'node_editor.space.text'),
        ('Node Editor Space Text Hi', 'node_editor.space.text_hi'),
        ('Node Editor Space Title', 'node_editor.space.title'),
        ('Node Editor Texture Node', 'node_editor.texture_node'),
        ('Node Editor Vector Node', 'node_editor.vector_node'),
        ('Node Editor Wire', 'node_editor.wire'),
        ('Node Editor Wire Inner', 'node_editor.wire_inner'),
        ('Node Editor Wire Select', 'node_editor.wire_select'),
        ('User Interface Box Inner', 'user_interface.wcol_box.inner'),
        ('User Interface Box Inner Selected', 'user_interface.wcol_box.inner_sel'),
        ('User Interface Box Item', 'user_interface.wcol_box.item'),
        ('User Interface Box Outline', 'user_interface.wcol_box.outline'),
        ('User Interface Box Outline Selected', 'user_interface.wcol_box.outline_sel'),
        ('User Interface Box Text', 'user_interface.wcol_box.text'),
        ('User Interface Box Text Selected', 'user_interface.wcol_box.text_sel'),
        ('User Interface Curve Widget Inner', 'user_interface.wcol_curve.inner'),
        ('User Interface Curve Widget Inner Selected', 'user_interface.wcol_curve.inner_sel'),
        ('User Interface Curve Widget Item', 'user_interface.wcol_curve.item'),
        ('User Interface Curve Widget Outline', 'user_interface.wcol_curve.outline'),
        ('User Interface Curve Widget Outline Selected', 'user_interface.wcol_curve.outline_sel'),
        ('User Interface Curve Widget Text', 'user_interface.wcol_curve.text'),
        ('User Interface Curve Widget Text Selected', 'user_interface.wcol_curve.text_sel'),
        ('User Interface List Item Inner', 'user_interface.wcol_list_item.inner'),
        ('User Interface List Item Inner Selected', 'user_interface.wcol_list_item.inner_sel'),
        ('User Interface List Item Item', 'user_interface.wcol_list_item.item'),
        ('User Interface List Item Outline', 'user_interface.wcol_list_item.outline'),
        ('User Interface List Item Outline Selected', 'user_interface.wcol_list_item.outline_sel'),
        ('User Interface List Item Text', 'user_interface.wcol_list_item.text'),
        ('User Interface List Item Text Selected', 'user_interface.wcol_list_item.text_sel'),
        ('User Interface Number Widget Inner', 'user_interface.wcol_num.inner'),
        ('User Interface Number Widget Inner Selected', 'user_interface.wcol_num.inner_sel'),
        ('User Interface Number Widget Item', 'user_interface.wcol_num.item'),
        ('User Interface Number Widget Outline', 'user_interface.wcol_num.outline'),
        ('User Interface Number Widget Outline Selected', 'user_interface.wcol_num.outline_sel'),
        ('User Interface Number Widget Text', 'user_interface.wcol_num.text'),
        ('User Interface Number Widget Text Selected', 'user_interface.wcol_num.text_sel'),
        ('User Interface Slider Widget Inner', 'user_interface.wcol_numslider.inner'),
        ('User Interface Slider Widget Inner Selected', 'user_interface.wcol_numslider.inner_sel'),
        ('User Interface Slider Widget Item', 'user_interface.wcol_numslider.item'),
        ('User Interface Slider Widget Outline', 'user_interface.wcol_numslider.outline'),
        ('User Interface Slider Widget Outline Selected', 'user_interface.wcol_numslider.outline_sel'),
        ('User Interface Slider Widget Text', 'user_interface.wcol_numslider.text'),
        ('User Interface Slider Widget Text Selected', 'user_interface.wcol_numslider.text_sel'),
        ('User Interface Option Widget Inner', 'user_interface.wcol_option.inner'),
        ('User Interface Option Widget Inner Selected', 'user_interface.wcol_option.inner_sel'),
        ('User Interface Option Widget Item', 'user_interface.wcol_option.item'),
        ('User Interface Option Widget Outline', 'user_interface.wcol_option.outline'),
        ('User Interface Option Widget Outline Selected', 'user_interface.wcol_option.outline_sel'),
        ('User Interface Option Widget Text', 'user_interface.wcol_option.text'),
        ('User Interface Option Widget Text Selected', 'user_interface.wcol_option.text_sel'),
        ('User Interface Radio Widget Inner', 'user_interface.wcol_radio.inner'),
        ('User Interface Radio Widget Inner Selected', 'user_interface.wcol_radio.inner_sel'),
        ('User Interface Radio Widget Item', 'user_interface.wcol_radio.item'),
        ('User Interface Radio Widget Outline', 'user_interface.wcol_radio.outline'),
        ('User Interface Radio Widget Outline Selected', 'user_interface.wcol_radio.outline_sel'),
        ('User Interface Radio Widget Text', 'user_interface.wcol_radio.text'),
        ('User Interface Radio Widget Text Selected', 'user_interface.wcol_radio.text_sel'),
        ('User Interface Regular Widget Inner', 'user_interface.wcol_regular.inner'),
        ('User Interface Regular Widget Inner Selected', 'user_interface.wcol_regular.inner_sel'),
        ('User Interface Regular Widget Item', 'user_interface.wcol_regular.item'),
        ('User Interface Regular Widget Outline', 'user_interface.wcol_regular.outline'),
        ('User Interface Regular Widget Outline Selected', 'user_interface.wcol_regular.outline_sel'),
        ('User Interface Regular Widget Text', 'user_interface.wcol_regular.text'),
        ('User Interface Regular Widget Text Selected', 'user_interface.wcol_regular.text_sel'),
        ('User Interface Scroll Widget Inner', 'user_interface.wcol_scroll.inner'),
        ('User Interface Scroll Widget Inner Selected', 'user_interface.wcol_scroll.inner_sel'),
        ('User Interface Scroll Widget Item', 'user_interface.wcol_scroll.item'),
        ('User Interface Scroll Widget Outline', 'user_interface.wcol_scroll.outline'),
        ('User Interface Scroll Widget Outline Selected', 'user_interface.wcol_scroll.outline_sel'),
        ('User Interface Scroll Widget Text', 'user_interface.wcol_scroll.text'),
        ('User Interface Scroll Widget Text Selected', 'user_interface.wcol_scroll.text_sel'),
        ('User Interface Tab Inner', 'user_interface.wcol_tab.inner'),
        ('User Interface Tab Inner Selected', 'user_interface.wcol_tab.inner_sel'),
        ('User Interface Tab Item', 'user_interface.wcol_tab.item'),
        ('User Interface Tab Outline', 'user_interface.wcol_tab.outline'),
        ('User Interface Tab Outline Selected', 'user_interface.wcol_tab.outline_sel'),
        ('User Interface Tab Text', 'user_interface.wcol_tab.text'),
        ('User Interface Tab Text Selected', 'user_interface.wcol_tab.text_sel'),
        ('User Interface Text Widget Inner', 'user_interface.wcol_text.inner'),
        ('User Interface Text Widget Inner Selected', 'user_interface.wcol_text.inner_sel'),
        ('User Interface Text Widget Item', 'user_interface.wcol_text.item'),
        ('User Interface Text Widget Outline', 'user_interface.wcol_text.outline'),
        ('User Interface Text Widget Outline Selected', 'user_interface.wcol_text.outline_sel'),
        ('User Interface Text Widget Text', 'user_interface.wcol_text.text'),
        ('User Interface Text Widget Text Selected', 'user_interface.wcol_text.text_sel'),
        ('User Interface Toggle Widget Inner', 'user_interface.wcol_toggle.inner'),
        ('User Interface Toggle Widget Inner Selected', 'user_interface.wcol_toggle.inner_sel'),
        ('User Interface Toggle Widget Item', 'user_interface.wcol_toggle.item'),
        ('User Interface Toggle Widget Outline', 'user_interface.wcol_toggle.outline'),
        ('User Interface Toggle Widget Outline Selected', 'user_interface.wcol_toggle.outline_sel'),
        ('User Interface Toggle Widget Text', 'user_interface.wcol_toggle.text'),
        ('User Interface Toggle Widget Text Selected', 'user_interface.wcol_toggle.text_sel'),
        ('User Interface Tool Widget Inner', 'user_interface.wcol_tool.inner'),
        ('User Interface Tool Widget Inner Selected', 'user_interface.wcol_tool.inner_sel'),
        ('User Interface Tool Widget Item', 'user_interface.wcol_tool.item'),
        ('User Interface Tool Widget Outline', 'user_interface.wcol_tool.outline'),
        ('User Interface Tool Widget Outline Selected', 'user_interface.wcol_tool.outline_sel'),
        ('User Interface Tool Widget Text', 'user_interface.wcol_tool.text'),
        ('User Interface Tool Widget Text Selected', 'user_interface.wcol_tool.text_sel'),
        ('User Interface Toolbar Item Inner', 'user_interface.wcol_toolbar_item.inner'),
        ('User Interface Toolbar Item Inner Selected', 'user_interface.wcol_toolbar_item.inner_sel'),
        ('User Interface Toolbar Item Item', 'user_interface.wcol_toolbar_item.item'),
        ('User Interface Toolbar Item Outline', 'user_interface.wcol_toolbar_item.outline'),
        ('User Interface Toolbar Item Outline Selected', 'user_interface.wcol_toolbar_item.outline_sel'),
        ('User Interface Toolbar Item Text', 'user_interface.wcol_toolbar_item.text'),
        ('User Interface Toolbar Item Text Selected', 'user_interface.wcol_toolbar_item.text_sel'),
        ('User Interface Widget Emboss', 'user_interface.widget_emboss'),
        ('User Interface Text Cursor', 'user_interface.widget_text_cursor'),
    ],
    'MD_13': [
        ('Properties Match', 'properties.match'),
        ('Properties Space Background', 'properties.space.back'),
        ('Properties Space Header', 'properties.space.header'),
        ('Properties Space Header Text', 'properties.space.header_text'),
        ('Properties Space Header Text Hi', 'properties.space.header_text_hi'),
        ('Properties Space Text', 'properties.space.text'),
        ('Properties Space Text Hi', 'properties.space.text_hi'),
        ('Properties Space Title', 'properties.space.title'),
        ('User Interface Icon Autokey', 'user_interface.icon_autokey'),
        ('User Interface Icon Collection', 'user_interface.icon_collection'),
        ('User Interface Icon Folder', 'user_interface.icon_folder'),
        ('User Interface Icon Modifier', 'user_interface.icon_modifier'),
        ('User Interface Icon Object', 'user_interface.icon_object'),
        ('User Interface Icon Object Data', 'user_interface.icon_object_data'),
        ('User Interface Icon Scene', 'user_interface.icon_scene'),
        ('User Interface Icon Shading', 'user_interface.icon_shading'),
        ('User Interface Box Inner', 'user_interface.wcol_box.inner'),
        ('User Interface Box Inner Selected', 'user_interface.wcol_box.inner_sel'),
        ('User Interface Box Item', 'user_interface.wcol_box.item'),
        ('User Interface Box Outline', 'user_interface.wcol_box.outline'),
        ('User Interface Box Outline Selected', 'user_interface.wcol_box.outline_sel'),
        ('User Interface Box Text', 'user_interface.wcol_box.text'),
        ('User Interface Box Text Selected', 'user_interface.wcol_box.text_sel'),
        ('User Interface Curve Widget Inner', 'user_interface.wcol_curve.inner'),
        ('User Interface Curve Widget Inner Selected', 'user_interface.wcol_curve.inner_sel'),
        ('User Interface Curve Widget Item', 'user_interface.wcol_curve.item'),
        ('User Interface Curve Widget Outline', 'user_interface.wcol_curve.outline'),
        ('User Interface Curve Widget Outline Selected', 'user_interface.wcol_curve.outline_sel'),
        ('User Interface Curve Widget Text', 'user_interface.wcol_curve.text'),
        ('User Interface Curve Widget Text Selected', 'user_interface.wcol_curve.text_sel'),
        ('User Interface List Item Inner', 'user_interface.wcol_list_item.inner'),
        ('User Interface List Item Inner Selected', 'user_interface.wcol_list_item.inner_sel'),
        ('User Interface List Item Item', 'user_interface.wcol_list_item.item'),
        ('User Interface List Item Outline', 'user_interface.wcol_list_item.outline'),
        ('User Interface List Item Outline Selected', 'user_interface.wcol_list_item.outline_sel'),
        ('User Interface List Item Text', 'user_interface.wcol_list_item.text'),
        ('User Interface List Item Text Selected', 'user_interface.wcol_list_item.text_sel'),
        ('User Interface Number Widget Inner', 'user_interface.wcol_num.inner'),
        ('User Interface Number Widget Inner Selected', 'user_interface.wcol_num.inner_sel'),
        ('User Interface Number Widget Item', 'user_interface.wcol_num.item'),
        ('User Interface Number Widget Outline', 'user_interface.wcol_num.outline'),
        ('User Interface Number Widget Outline Selected', 'user_interface.wcol_num.outline_sel'),
        ('User Interface Number Widget Text', 'user_interface.wcol_num.text'),
        ('User Interface Number Widget Text Selected', 'user_interface.wcol_num.text_sel'),
        ('User Interface Slider Widget Inner', 'user_interface.wcol_numslider.inner'),
        ('User Interface Slider Widget Inner Selected', 'user_interface.wcol_numslider.inner_sel'),
        ('User Interface Slider Widget Item', 'user_interface.wcol_numslider.item'),
        ('User Interface Slider Widget Outline', 'user_interface.wcol_numslider.outline'),
        ('User Interface Slider Widget Outline Selected', 'user_interface.wcol_numslider.outline_sel'),
        ('User Interface Slider Widget Text', 'user_interface.wcol_numslider.text'),
        ('User Interface Slider Widget Text Selected', 'user_interface.wcol_numslider.text_sel'),
        ('User Interface Option Widget Inner', 'user_interface.wcol_option.inner'),
        ('User Interface Option Widget Inner Selected', 'user_interface.wcol_option.inner_sel'),
        ('User Interface Option Widget Item', 'user_interface.wcol_option.item'),
        ('User Interface Option Widget Outline', 'user_interface.wcol_option.outline'),
        ('User Interface Option Widget Outline Selected', 'user_interface.wcol_option.outline_sel'),
        ('User Interface Option Widget Text', 'user_interface.wcol_option.text'),
        ('User Interface Option Widget Text Selected', 'user_interface.wcol_option.text_sel'),
        ('User Interface Progress Bar Inner', 'user_interface.wcol_progress.inner'),
        ('User Interface Progress Bar Inner Selected', 'user_interface.wcol_progress.inner_sel'),
        ('User Interface Progress Bar Item', 'user_interface.wcol_progress.item'),
        ('User Interface Progress Bar Outline', 'user_interface.wcol_progress.outline'),
        ('User Interface Progress Bar Outline Selected', 'user_interface.wcol_progress.outline_sel'),
        ('User Interface Progress Bar Text', 'user_interface.wcol_progress.text'),
        ('User Interface Progress Bar Text Selected', 'user_interface.wcol_progress.text_sel'),
        ('User Interface Radio Widget Inner', 'user_interface.wcol_radio.inner'),
        ('User Interface Radio Widget Inner Selected', 'user_interface.wcol_radio.inner_sel'),
        ('User Interface Radio Widget Item', 'user_interface.wcol_radio.item'),
        ('User Interface Radio Widget Outline', 'user_interface.wcol_radio.outline'),
        ('User Interface Radio Widget Outline Selected', 'user_interface.wcol_radio.outline_sel'),
        ('User Interface Radio Widget Text', 'user_interface.wcol_radio.text'),
        ('User Interface Radio Widget Text Selected', 'user_interface.wcol_radio.text_sel'),
        ('User Interface Regular Widget Inner', 'user_interface.wcol_regular.inner'),
        ('User Interface Regular Widget Inner Selected', 'user_interface.wcol_regular.inner_sel'),
        ('User Interface Regular Widget Item', 'user_interface.wcol_regular.item'),
        ('User Interface Regular Widget Outline', 'user_interface.wcol_regular.outline'),
        ('User Interface Regular Widget Outline Selected', 'user_interface.wcol_regular.outline_sel'),
        ('User Interface Regular Widget Text', 'user_interface.wcol_regular.text'),
        ('User Interface Regular Widget Text Selected', 'user_interface.wcol_regular.text_sel'),
        ('User Interface Scroll Widget Inner', 'user_interface.wcol_scroll.inner'),
        ('User Interface Scroll Widget Inner Selected', 'user_interface.wcol_scroll.inner_sel'),
        ('User Interface Scroll Widget Item', 'user_interface.wcol_scroll.item'),
        ('User Interface Scroll Widget Outline', 'user_interface.wcol_scroll.outline'),
        ('User Interface Scroll Widget Outline Selected', 'user_interface.wcol_scroll.outline_sel'),
        ('User Interface Scroll Widget Text', 'user_interface.wcol_scroll.text'),
        ('User Interface Scroll Widget Text Selected', 'user_interface.wcol_scroll.text_sel'),
        ('User Interface State Error', 'user_interface.wcol_state.error'),
        ('User Interface State Info', 'user_interface.wcol_state.info'),
        ('User Interface State Inner Anim', 'user_interface.wcol_state.inner_anim'),
        ('User Interface State Inner Anim Sel', 'user_interface.wcol_state.inner_anim_sel'),
        ('User Interface State Inner Changed', 'user_interface.wcol_state.inner_changed'),
        ('User Interface State Inner Changed Sel', 'user_interface.wcol_state.inner_changed_sel'),
        ('User Interface State Inner Driven', 'user_interface.wcol_state.inner_driven'),
        ('User Interface State Inner Driven Sel', 'user_interface.wcol_state.inner_driven_sel'),
        ('User Interface State Inner Key', 'user_interface.wcol_state.inner_key'),
        ('User Interface State Inner Key Sel', 'user_interface.wcol_state.inner_key_sel'),
        ('User Interface State Inner Overridden', 'user_interface.wcol_state.inner_overridden'),
        ('User Interface State Inner Overridden Sel', 'user_interface.wcol_state.inner_overridden_sel'),
        ('User Interface State Success', 'user_interface.wcol_state.success'),
        ('User Interface State Warning', 'user_interface.wcol_state.warning'),
        ('User Interface Tab Inner', 'user_interface.wcol_tab.inner'),
        ('User Interface Tab Inner Selected', 'user_interface.wcol_tab.inner_sel'),
        ('User Interface Tab Item', 'user_interface.wcol_tab.item'),
        ('User Interface Tab Outline', 'user_interface.wcol_tab.outline'),
        ('User Interface Tab Outline Selected', 'user_interface.wcol_tab.outline_sel'),
        ('User Interface Tab Text', 'user_interface.wcol_tab.text'),
        ('User Interface Tab Text Selected', 'user_interface.wcol_tab.text_sel'),
        ('User Interface Text Widget Inner', 'user_interface.wcol_text.inner'),
        ('User Interface Text Widget Inner Selected', 'user_interface.wcol_text.inner_sel'),
        ('User Interface Text Widget Item', 'user_interface.wcol_text.item'),
        ('User Interface Text Widget Outline', 'user_interface.wcol_text.outline'),
        ('User Interface Text Widget Outline Selected', 'user_interface.wcol_text.outline_sel'),
        ('User Interface Text Widget Text', 'user_interface.wcol_text.text'),
        ('User Interface Text Widget Text Selected', 'user_interface.wcol_text.text_sel'),
        ('User Interface Toggle Widget Inner', 'user_interface.wcol_toggle.inner'),
        ('User Interface Toggle Widget Inner Selected', 'user_interface.wcol_toggle.inner_sel'),
        ('User Interface Toggle Widget Item', 'user_interface.wcol_toggle.item'),
        ('User Interface Toggle Widget Outline', 'user_interface.wcol_toggle.outline'),
        ('User Interface Toggle Widget Outline Selected', 'user_interface.wcol_toggle.outline_sel'),
        ('User Interface Toggle Widget Text', 'user_interface.wcol_toggle.text'),
        ('User Interface Toggle Widget Text Selected', 'user_interface.wcol_toggle.text_sel'),
        ('User Interface Widget Emboss', 'user_interface.widget_emboss'),
        ('User Interface Text Cursor', 'user_interface.widget_text_cursor'),
    ],
    'MD_14': [
        ('Outliner Active', 'outliner.active'),
        ('Outliner Active Object', 'outliner.active_object'),
        ('Outliner Edited Object', 'outliner.edited_object'),
        ('Outliner Match', 'outliner.match'),
        ('Outliner Row Alternate', 'outliner.row_alternate'),
        ('Outliner Selected Highlight', 'outliner.selected_highlight'),
        ('Outliner Selected Object', 'outliner.selected_object'),
        ('Outliner Space Background', 'outliner.space.back'),
        ('Outliner Space Header', 'outliner.space.header'),
        ('Outliner Space Header Text', 'outliner.space.header_text'),
        ('Outliner Space Header Text Hi', 'outliner.space.header_text_hi'),
        ('Outliner Space Text', 'outliner.space.text'),
        ('Outliner Space Text Hi', 'outliner.space.text_hi'),
        ('Outliner Space Title', 'outliner.space.title'),
        ('Collection Color 0 Color', 'collection_color[0].color'),
        ('Collection Color 1 Color', 'collection_color[1].color'),
        ('Collection Color 2 Color', 'collection_color[2].color'),
        ('Collection Color 3 Color', 'collection_color[3].color'),
        ('Collection Color 4 Color', 'collection_color[4].color'),
        ('Collection Color 5 Color', 'collection_color[5].color'),
        ('Collection Color 6 Color', 'collection_color[6].color'),
        ('Collection Color 7 Color', 'collection_color[7].color'),
        ('User Interface Icon Autokey', 'user_interface.icon_autokey'),
        ('User Interface Icon Collection', 'user_interface.icon_collection'),
        ('User Interface Icon Folder', 'user_interface.icon_folder'),
        ('User Interface Icon Modifier', 'user_interface.icon_modifier'),
        ('User Interface Icon Object', 'user_interface.icon_object'),
        ('User Interface Icon Object Data', 'user_interface.icon_object_data'),
        ('User Interface Icon Scene', 'user_interface.icon_scene'),
        ('User Interface Icon Shading', 'user_interface.icon_shading'),
        ('User Interface Curve Widget Inner', 'user_interface.wcol_curve.inner'),
        ('User Interface Curve Widget Inner Selected', 'user_interface.wcol_curve.inner_sel'),
        ('User Interface Curve Widget Item', 'user_interface.wcol_curve.item'),
        ('User Interface Curve Widget Outline', 'user_interface.wcol_curve.outline'),
        ('User Interface Curve Widget Outline Selected', 'user_interface.wcol_curve.outline_sel'),
        ('User Interface Curve Widget Text', 'user_interface.wcol_curve.text'),
        ('User Interface Curve Widget Text Selected', 'user_interface.wcol_curve.text_sel'),
        ('User Interface Number Widget Inner', 'user_interface.wcol_num.inner'),
        ('User Interface Number Widget Inner Selected', 'user_interface.wcol_num.inner_sel'),
        ('User Interface Number Widget Item', 'user_interface.wcol_num.item'),
        ('User Interface Number Widget Outline', 'user_interface.wcol_num.outline'),
        ('User Interface Number Widget Outline Selected', 'user_interface.wcol_num.outline_sel'),
        ('User Interface Number Widget Text', 'user_interface.wcol_num.text'),
        ('User Interface Number Widget Text Selected', 'user_interface.wcol_num.text_sel'),
        ('User Interface Slider Widget Inner', 'user_interface.wcol_numslider.inner'),
        ('User Interface Slider Widget Inner Selected', 'user_interface.wcol_numslider.inner_sel'),
        ('User Interface Slider Widget Item', 'user_interface.wcol_numslider.item'),
        ('User Interface Slider Widget Outline', 'user_interface.wcol_numslider.outline'),
        ('User Interface Slider Widget Outline Selected', 'user_interface.wcol_numslider.outline_sel'),
        ('User Interface Slider Widget Text', 'user_interface.wcol_numslider.text'),
        ('User Interface Slider Widget Text Selected', 'user_interface.wcol_numslider.text_sel'),
        ('User Interface Option Widget Inner', 'user_interface.wcol_option.inner'),
        ('User Interface Option Widget Inner Selected', 'user_interface.wcol_option.inner_sel'),
        ('User Interface Option Widget Item', 'user_interface.wcol_option.item'),
        ('User Interface Option Widget Outline', 'user_interface.wcol_option.outline'),
        ('User Interface Option Widget Outline Selected', 'user_interface.wcol_option.outline_sel'),
        ('User Interface Option Widget Text', 'user_interface.wcol_option.text'),
        ('User Interface Option Widget Text Selected', 'user_interface.wcol_option.text_sel'),
        ('User Interface Radio Widget Inner', 'user_interface.wcol_radio.inner'),
        ('User Interface Radio Widget Inner Selected', 'user_interface.wcol_radio.inner_sel'),
        ('User Interface Radio Widget Item', 'user_interface.wcol_radio.item'),
        ('User Interface Radio Widget Outline', 'user_interface.wcol_radio.outline'),
        ('User Interface Radio Widget Outline Selected', 'user_interface.wcol_radio.outline_sel'),
        ('User Interface Radio Widget Text', 'user_interface.wcol_radio.text'),
        ('User Interface Radio Widget Text Selected', 'user_interface.wcol_radio.text_sel'),
        ('User Interface Regular Widget Inner', 'user_interface.wcol_regular.inner'),
        ('User Interface Regular Widget Inner Selected', 'user_interface.wcol_regular.inner_sel'),
        ('User Interface Regular Widget Item', 'user_interface.wcol_regular.item'),
        ('User Interface Regular Widget Outline', 'user_interface.wcol_regular.outline'),
        ('User Interface Regular Widget Outline Selected', 'user_interface.wcol_regular.outline_sel'),
        ('User Interface Regular Widget Text', 'user_interface.wcol_regular.text'),
        ('User Interface Regular Widget Text Selected', 'user_interface.wcol_regular.text_sel'),
        ('User Interface Text Widget Inner', 'user_interface.wcol_text.inner'),
        ('User Interface Text Widget Inner Selected', 'user_interface.wcol_text.inner_sel'),
        ('User Interface Text Widget Item', 'user_interface.wcol_text.item'),
        ('User Interface Text Widget Outline', 'user_interface.wcol_text.outline'),
        ('User Interface Text Widget Outline Selected', 'user_interface.wcol_text.outline_sel'),
        ('User Interface Text Widget Text', 'user_interface.wcol_text.text'),
        ('User Interface Text Widget Text Selected', 'user_interface.wcol_text.text_sel'),
        ('User Interface Toggle Widget Inner', 'user_interface.wcol_toggle.inner'),
        ('User Interface Toggle Widget Inner Selected', 'user_interface.wcol_toggle.inner_sel'),
        ('User Interface Toggle Widget Item', 'user_interface.wcol_toggle.item'),
        ('User Interface Toggle Widget Outline', 'user_interface.wcol_toggle.outline'),
        ('User Interface Toggle Widget Outline Selected', 'user_interface.wcol_toggle.outline_sel'),
        ('User Interface Toggle Widget Text', 'user_interface.wcol_toggle.text'),
        ('User Interface Toggle Widget Text Selected', 'user_interface.wcol_toggle.text_sel'),
        ('User Interface Widget Emboss', 'user_interface.widget_emboss'),
        ('User Interface Text Cursor', 'user_interface.widget_text_cursor'),
    ],
    'MD_15': [
        ('Image Editor Edge Select', 'image_editor.edge_select'),
        ('Image Editor Editmesh Active', 'image_editor.editmesh_active'),
        ('Image Editor Face', 'image_editor.face'),
        ('Image Editor Face Mode Select', 'image_editor.face_mode_select'),
        ('Image Editor Face Select', 'image_editor.face_select'),
        ('Image Editor Grid', 'image_editor.grid'),
        ('Image Editor Metadatabg', 'image_editor.metadatabg'),
        ('Image Editor Metadatatext', 'image_editor.metadatatext'),
        ('Image Editor Preview Stitch Active', 'image_editor.preview_stitch_active'),
        ('Image Editor Preview Stitch Edge', 'image_editor.preview_stitch_edge'),
        ('Image Editor Preview Stitch Face', 'image_editor.preview_stitch_face'),
        ('Image Editor Preview Stitch Stitchable', 'image_editor.preview_stitch_stitchable'),
        ('Image Editor Preview Stitch Unstitchable', 'image_editor.preview_stitch_unstitchable'),
        ('Image Editor Preview Stitch Vert', 'image_editor.preview_stitch_vert'),
        ('Image Editor Scope Back', 'image_editor.scope_back'),
        ('Image Editor Space Background', 'image_editor.space.back'),
        ('Image Editor Space Header', 'image_editor.space.header'),
        ('Image Editor Space Header Text', 'image_editor.space.header_text'),
        ('Image Editor Space Header Text Hi', 'image_editor.space.header_text_hi'),
        ('Image Editor Space Text', 'image_editor.space.text'),
        ('Image Editor Space Text Hi', 'image_editor.space.text_hi'),
        ('Image Editor Space Title', 'image_editor.space.title'),
        ('Image Editor Uv Shadow', 'image_editor.uv_shadow'),
        ('Image Editor Vertex', 'image_editor.vertex'),
        ('Image Editor Vertex Select', 'image_editor.vertex_select'),
        ('Image Editor Wire Edit', 'image_editor.wire_edit'),
        ('User Interface Transparent Checker Primary', 'user_interface.transparent_checker_primary'),
        ('User Interface Transparent Checker Secondary', 'user_interface.transparent_checker_secondary'),
        ('User Interface Box Inner', 'user_interface.wcol_box.inner'),
        ('User Interface Box Inner Selected', 'user_interface.wcol_box.inner_sel'),
        ('User Interface Box Item', 'user_interface.wcol_box.item'),
        ('User Interface Box Outline', 'user_interface.wcol_box.outline'),
        ('User Interface Box Outline Selected', 'user_interface.wcol_box.outline_sel'),
        ('User Interface Box Text', 'user_interface.wcol_box.text'),
        ('User Interface Box Text Selected', 'user_interface.wcol_box.text_sel'),
        ('User Interface Curve Widget Inner', 'user_interface.wcol_curve.inner'),
        ('User Interface Curve Widget Inner Selected', 'user_interface.wcol_curve.inner_sel'),
        ('User Interface Curve Widget Item', 'user_interface.wcol_curve.item'),
        ('User Interface Curve Widget Outline', 'user_interface.wcol_curve.outline'),
        ('User Interface Curve Widget Outline Selected', 'user_interface.wcol_curve.outline_sel'),
        ('User Interface Curve Widget Text', 'user_interface.wcol_curve.text'),
        ('User Interface Curve Widget Text Selected', 'user_interface.wcol_curve.text_sel'),
        ('User Interface List Item Inner', 'user_interface.wcol_list_item.inner'),
        ('User Interface List Item Inner Selected', 'user_interface.wcol_list_item.inner_sel'),
        ('User Interface List Item Item', 'user_interface.wcol_list_item.item'),
        ('User Interface List Item Outline', 'user_interface.wcol_list_item.outline'),
        ('User Interface List Item Outline Selected', 'user_interface.wcol_list_item.outline_sel'),
        ('User Interface List Item Text', 'user_interface.wcol_list_item.text'),
        ('User Interface List Item Text Selected', 'user_interface.wcol_list_item.text_sel'),
        ('User Interface Number Widget Inner', 'user_interface.wcol_num.inner'),
        ('User Interface Number Widget Inner Selected', 'user_interface.wcol_num.inner_sel'),
        ('User Interface Number Widget Item', 'user_interface.wcol_num.item'),
        ('User Interface Number Widget Outline', 'user_interface.wcol_num.outline'),
        ('User Interface Number Widget Outline Selected', 'user_interface.wcol_num.outline_sel'),
        ('User Interface Number Widget Text', 'user_interface.wcol_num.text'),
        ('User Interface Number Widget Text Selected', 'user_interface.wcol_num.text_sel'),
        ('User Interface Slider Widget Inner', 'user_interface.wcol_numslider.inner'),
        ('User Interface Slider Widget Inner Selected', 'user_interface.wcol_numslider.inner_sel'),
        ('User Interface Slider Widget Item', 'user_interface.wcol_numslider.item'),
        ('User Interface Slider Widget Outline', 'user_interface.wcol_numslider.outline'),
        ('User Interface Slider Widget Outline Selected', 'user_interface.wcol_numslider.outline_sel'),
        ('User Interface Slider Widget Text', 'user_interface.wcol_numslider.text'),
        ('User Interface Slider Widget Text Selected', 'user_interface.wcol_numslider.text_sel'),
        ('User Interface Option Widget Inner', 'user_interface.wcol_option.inner'),
        ('User Interface Option Widget Inner Selected', 'user_interface.wcol_option.inner_sel'),
        ('User Interface Option Widget Item', 'user_interface.wcol_option.item'),
        ('User Interface Option Widget Outline', 'user_interface.wcol_option.outline'),
        ('User Interface Option Widget Outline Selected', 'user_interface.wcol_option.outline_sel'),
        ('User Interface Option Widget Text', 'user_interface.wcol_option.text'),
        ('User Interface Option Widget Text Selected', 'user_interface.wcol_option.text_sel'),
        ('User Interface Radio Widget Inner', 'user_interface.wcol_radio.inner'),
        ('User Interface Radio Widget Inner Selected', 'user_interface.wcol_radio.inner_sel'),
        ('User Interface Radio Widget Item', 'user_interface.wcol_radio.item'),
        ('User Interface Radio Widget Outline', 'user_interface.wcol_radio.outline'),
        ('User Interface Radio Widget Outline Selected', 'user_interface.wcol_radio.outline_sel'),
        ('User Interface Radio Widget Text', 'user_interface.wcol_radio.text'),
        ('User Interface Radio Widget Text Selected', 'user_interface.wcol_radio.text_sel'),
        ('User Interface Regular Widget Inner', 'user_interface.wcol_regular.inner'),
        ('User Interface Regular Widget Inner Selected', 'user_interface.wcol_regular.inner_sel'),
        ('User Interface Regular Widget Item', 'user_interface.wcol_regular.item'),
        ('User Interface Regular Widget Outline', 'user_interface.wcol_regular.outline'),
        ('User Interface Regular Widget Outline Selected', 'user_interface.wcol_regular.outline_sel'),
        ('User Interface Regular Widget Text', 'user_interface.wcol_regular.text'),
        ('User Interface Regular Widget Text Selected', 'user_interface.wcol_regular.text_sel'),
        ('User Interface Scroll Widget Inner', 'user_interface.wcol_scroll.inner'),
        ('User Interface Scroll Widget Inner Selected', 'user_interface.wcol_scroll.inner_sel'),
        ('User Interface Scroll Widget Item', 'user_interface.wcol_scroll.item'),
        ('User Interface Scroll Widget Outline', 'user_interface.wcol_scroll.outline'),
        ('User Interface Scroll Widget Outline Selected', 'user_interface.wcol_scroll.outline_sel'),
        ('User Interface Scroll Widget Text', 'user_interface.wcol_scroll.text'),
        ('User Interface Scroll Widget Text Selected', 'user_interface.wcol_scroll.text_sel'),
        ('User Interface Tab Inner', 'user_interface.wcol_tab.inner'),
        ('User Interface Tab Inner Selected', 'user_interface.wcol_tab.inner_sel'),
        ('User Interface Tab Item', 'user_interface.wcol_tab.item'),
        ('User Interface Tab Outline', 'user_interface.wcol_tab.outline'),
        ('User Interface Tab Outline Selected', 'user_interface.wcol_tab.outline_sel'),
        ('User Interface Tab Text', 'user_interface.wcol_tab.text'),
        ('User Interface Tab Text Selected', 'user_interface.wcol_tab.text_sel'),
        ('User Interface Text Widget Inner', 'user_interface.wcol_text.inner'),
        ('User Interface Text Widget Inner Selected', 'user_interface.wcol_text.inner_sel'),
        ('User Interface Text Widget Item', 'user_interface.wcol_text.item'),
        ('User Interface Text Widget Outline', 'user_interface.wcol_text.outline'),
        ('User Interface Text Widget Outline Selected', 'user_interface.wcol_text.outline_sel'),
        ('User Interface Text Widget Text', 'user_interface.wcol_text.text'),
        ('User Interface Text Widget Text Selected', 'user_interface.wcol_text.text_sel'),
        ('User Interface Toggle Widget Inner', 'user_interface.wcol_toggle.inner'),
        ('User Interface Toggle Widget Inner Selected', 'user_interface.wcol_toggle.inner_sel'),
        ('User Interface Toggle Widget Item', 'user_interface.wcol_toggle.item'),
        ('User Interface Toggle Widget Outline', 'user_interface.wcol_toggle.outline'),
        ('User Interface Toggle Widget Outline Selected', 'user_interface.wcol_toggle.outline_sel'),
        ('User Interface Toggle Widget Text', 'user_interface.wcol_toggle.text'),
        ('User Interface Toggle Widget Text Selected', 'user_interface.wcol_toggle.text_sel'),
        ('User Interface Widget Emboss', 'user_interface.widget_emboss'),
        ('User Interface Text Cursor', 'user_interface.widget_text_cursor'),
    ],
    'MD_16': [
        ('Video Sequencer Active Strip', 'sequence_editor.active_strip'),
        ('Video Sequencer Audio Strip', 'sequence_editor.audio_strip'),
        ('Video Sequencer Color Strip', 'sequence_editor.color_strip'),
        ('Video Sequencer Effect Strip', 'sequence_editor.effect_strip'),
        ('Video Sequencer Grid', 'sequence_editor.grid'),
        ('Video Sequencer Image Strip', 'sequence_editor.image_strip'),
        ('Video Sequencer Keyframe Border', 'sequence_editor.keyframe_border'),
        ('Video Sequencer Keyframe Border Selected', 'sequence_editor.keyframe_border_selected'),
        ('Video Sequencer Mask Strip', 'sequence_editor.mask_strip'),
        ('Video Sequencer Meta Strip', 'sequence_editor.meta_strip'),
        ('Video Sequencer Metadatabg', 'sequence_editor.metadatabg'),
        ('Video Sequencer Metadatatext', 'sequence_editor.metadatatext'),
        ('Video Sequencer Movie Strip', 'sequence_editor.movie_strip'),
        ('Video Sequencer Movieclip Strip', 'sequence_editor.movieclip_strip'),
        ('Video Sequencer Preview Back', 'sequence_editor.preview_back'),
        ('Video Sequencer Row Alternate', 'sequence_editor.row_alternate'),
        ('Video Sequencer Scene Strip', 'sequence_editor.scene_strip'),
        ('Video Sequencer Selected Strip', 'sequence_editor.selected_strip'),
        ('Video Sequencer Selected Text', 'sequence_editor.selected_text'),
        ('Video Sequencer Space Background', 'sequence_editor.space.back'),
        ('Video Sequencer Space Header', 'sequence_editor.space.header'),
        ('Video Sequencer Space Header Text', 'sequence_editor.space.header_text'),
        ('Video Sequencer Space Header Text Hi', 'sequence_editor.space.header_text_hi'),
        ('Video Sequencer Space Text', 'sequence_editor.space.text'),
        ('Video Sequencer Space Text Hi', 'sequence_editor.space.text_hi'),
        ('Video Sequencer Space Title', 'sequence_editor.space.title'),
        ('Video Sequencer Text Strip', 'sequence_editor.text_strip'),
        ('Video Sequencer Text Strip Cursor', 'sequence_editor.text_strip_cursor'),
        ('Video Sequencer Transition Strip', 'sequence_editor.transition_strip'),
        ('Strip Color 0 Color', 'strip_color[0].color'),
        ('Strip Color 1 Color', 'strip_color[1].color'),
        ('Strip Color 2 Color', 'strip_color[2].color'),
        ('Strip Color 3 Color', 'strip_color[3].color'),
        ('Strip Color 4 Color', 'strip_color[4].color'),
        ('Strip Color 5 Color', 'strip_color[5].color'),
        ('Strip Color 6 Color', 'strip_color[6].color'),
        ('Strip Color 7 Color', 'strip_color[7].color'),
        ('Strip Color 8 Color', 'strip_color[8].color'),
        ('User Interface Curve Widget Inner', 'user_interface.wcol_curve.inner'),
        ('User Interface Curve Widget Inner Selected', 'user_interface.wcol_curve.inner_sel'),
        ('User Interface Curve Widget Item', 'user_interface.wcol_curve.item'),
        ('User Interface Curve Widget Outline', 'user_interface.wcol_curve.outline'),
        ('User Interface Curve Widget Outline Selected', 'user_interface.wcol_curve.outline_sel'),
        ('User Interface Curve Widget Text', 'user_interface.wcol_curve.text'),
        ('User Interface Curve Widget Text Selected', 'user_interface.wcol_curve.text_sel'),
        ('User Interface Number Widget Inner', 'user_interface.wcol_num.inner'),
        ('User Interface Number Widget Inner Selected', 'user_interface.wcol_num.inner_sel'),
        ('User Interface Number Widget Item', 'user_interface.wcol_num.item'),
        ('User Interface Number Widget Outline', 'user_interface.wcol_num.outline'),
        ('User Interface Number Widget Outline Selected', 'user_interface.wcol_num.outline_sel'),
        ('User Interface Number Widget Text', 'user_interface.wcol_num.text'),
        ('User Interface Number Widget Text Selected', 'user_interface.wcol_num.text_sel'),
        ('User Interface Slider Widget Inner', 'user_interface.wcol_numslider.inner'),
        ('User Interface Slider Widget Inner Selected', 'user_interface.wcol_numslider.inner_sel'),
        ('User Interface Slider Widget Item', 'user_interface.wcol_numslider.item'),
        ('User Interface Slider Widget Outline', 'user_interface.wcol_numslider.outline'),
        ('User Interface Slider Widget Outline Selected', 'user_interface.wcol_numslider.outline_sel'),
        ('User Interface Slider Widget Text', 'user_interface.wcol_numslider.text'),
        ('User Interface Slider Widget Text Selected', 'user_interface.wcol_numslider.text_sel'),
        ('User Interface Option Widget Inner', 'user_interface.wcol_option.inner'),
        ('User Interface Option Widget Inner Selected', 'user_interface.wcol_option.inner_sel'),
        ('User Interface Option Widget Item', 'user_interface.wcol_option.item'),
        ('User Interface Option Widget Outline', 'user_interface.wcol_option.outline'),
        ('User Interface Option Widget Outline Selected', 'user_interface.wcol_option.outline_sel'),
        ('User Interface Option Widget Text', 'user_interface.wcol_option.text'),
        ('User Interface Option Widget Text Selected', 'user_interface.wcol_option.text_sel'),
        ('User Interface Radio Widget Inner', 'user_interface.wcol_radio.inner'),
        ('User Interface Radio Widget Inner Selected', 'user_interface.wcol_radio.inner_sel'),
        ('User Interface Radio Widget Item', 'user_interface.wcol_radio.item'),
        ('User Interface Radio Widget Outline', 'user_interface.wcol_radio.outline'),
        ('User Interface Radio Widget Outline Selected', 'user_interface.wcol_radio.outline_sel'),
        ('User Interface Radio Widget Text', 'user_interface.wcol_radio.text'),
        ('User Interface Radio Widget Text Selected', 'user_interface.wcol_radio.text_sel'),
        ('User Interface Regular Widget Inner', 'user_interface.wcol_regular.inner'),
        ('User Interface Regular Widget Inner Selected', 'user_interface.wcol_regular.inner_sel'),
        ('User Interface Regular Widget Item', 'user_interface.wcol_regular.item'),
        ('User Interface Regular Widget Outline', 'user_interface.wcol_regular.outline'),
        ('User Interface Regular Widget Outline Selected', 'user_interface.wcol_regular.outline_sel'),
        ('User Interface Regular Widget Text', 'user_interface.wcol_regular.text'),
        ('User Interface Regular Widget Text Selected', 'user_interface.wcol_regular.text_sel'),
        ('User Interface Text Widget Inner', 'user_interface.wcol_text.inner'),
        ('User Interface Text Widget Inner Selected', 'user_interface.wcol_text.inner_sel'),
        ('User Interface Text Widget Item', 'user_interface.wcol_text.item'),
        ('User Interface Text Widget Outline', 'user_interface.wcol_text.outline'),
        ('User Interface Text Widget Outline Selected', 'user_interface.wcol_text.outline_sel'),
        ('User Interface Text Widget Text', 'user_interface.wcol_text.text'),
        ('User Interface Text Widget Text Selected', 'user_interface.wcol_text.text_sel'),
        ('User Interface Toggle Widget Inner', 'user_interface.wcol_toggle.inner'),
        ('User Interface Toggle Widget Inner Selected', 'user_interface.wcol_toggle.inner_sel'),
        ('User Interface Toggle Widget Item', 'user_interface.wcol_toggle.item'),
        ('User Interface Toggle Widget Outline', 'user_interface.wcol_toggle.outline'),
        ('User Interface Toggle Widget Outline Selected', 'user_interface.wcol_toggle.outline_sel'),
        ('User Interface Toggle Widget Text', 'user_interface.wcol_toggle.text'),
        ('User Interface Toggle Widget Text Selected', 'user_interface.wcol_toggle.text_sel'),
        ('User Interface Widget Emboss', 'user_interface.widget_emboss'),
        ('User Interface Text Cursor', 'user_interface.widget_text_cursor'),
    ],
    'MD_17': [
        ('Clip Editor Active Marker', 'clip_editor.active_marker'),
        ('Clip Editor Disabled Marker', 'clip_editor.disabled_marker'),
        ('Clip Editor Grid', 'clip_editor.grid'),
        ('Clip Editor Locked Marker', 'clip_editor.locked_marker'),
        ('Clip Editor Marker', 'clip_editor.marker'),
        ('Clip Editor Marker Outline', 'clip_editor.marker_outline'),
        ('Clip Editor Metadatabg', 'clip_editor.metadatabg'),
        ('Clip Editor Metadatatext', 'clip_editor.metadatatext'),
        ('Clip Editor Path After', 'clip_editor.path_after'),
        ('Clip Editor Path Before', 'clip_editor.path_before'),
        ('Clip Editor Path Keyframe After', 'clip_editor.path_keyframe_after'),
        ('Clip Editor Path Keyframe Before', 'clip_editor.path_keyframe_before'),
        ('Clip Editor Selected Marker', 'clip_editor.selected_marker'),
        ('Clip Editor Space Background', 'clip_editor.space.back'),
        ('Clip Editor Space Header', 'clip_editor.space.header'),
        ('Clip Editor Space Header Text', 'clip_editor.space.header_text'),
        ('Clip Editor Space Header Text Hi', 'clip_editor.space.header_text_hi'),
        ('Clip Editor Space Text', 'clip_editor.space.text'),
        ('Clip Editor Space Text Hi', 'clip_editor.space.text_hi'),
        ('Clip Editor Space Title', 'clip_editor.space.title'),
        ('Python Console Cursor', 'console.cursor'),
        ('Python Console Line Error', 'console.line_error'),
        ('Python Console Line Info', 'console.line_info'),
        ('Python Console Line Input', 'console.line_input'),
        ('Python Console Line Output', 'console.line_output'),
        ('Python Console Select', 'console.select'),
        ('Python Console Space Background', 'console.space.back'),
        ('Python Console Space Header', 'console.space.header'),
        ('Python Console Space Header Text', 'console.space.header_text'),
        ('Python Console Space Header Text Hi', 'console.space.header_text_hi'),
        ('Python Console Space Text', 'console.space.text'),
        ('Python Console Space Text Hi', 'console.space.text_hi'),
        ('Python Console Space Title', 'console.space.title'),
        ('File Browser Row Alternate', 'file_browser.row_alternate'),
        ('File Browser Selected File', 'file_browser.selected_file'),
        ('File Browser Space Background', 'file_browser.space.back'),
        ('File Browser Space Header', 'file_browser.space.header'),
        ('File Browser Space Header Text', 'file_browser.space.header_text'),
        ('File Browser Space Header Text Hi', 'file_browser.space.header_text_hi'),
        ('File Browser Space Text', 'file_browser.space.text'),
        ('File Browser Space Text Hi', 'file_browser.space.text_hi'),
        ('File Browser Space Title', 'file_browser.space.title'),
        ('Info Info Debug', 'info.info_debug'),
        ('Info Info Debug Text', 'info.info_debug_text'),
        ('Info Info Error Text', 'info.info_error_text'),
        ('Info Info Info Text', 'info.info_info_text'),
        ('Info Info Operator', 'info.info_operator'),
        ('Info Info Operator Text', 'info.info_operator_text'),
        ('Info Info Property', 'info.info_property'),
        ('Info Info Property Text', 'info.info_property_text'),
        ('Info Info Selected', 'info.info_selected'),
        ('Info Info Selected Text', 'info.info_selected_text'),
        ('Info Info Warning Text', 'info.info_warning_text'),
        ('Info Space Background', 'info.space.back'),
        ('Info Space Header', 'info.space.header'),
        ('Info Space Header Text', 'info.space.header_text'),
        ('Info Space Header Text Hi', 'info.space.header_text_hi'),
        ('Info Space Text', 'info.space.text'),
        ('Info Space Text Hi', 'info.space.text_hi'),
        ('Info Space Title', 'info.space.title'),
        ('Preferences Match', 'preferences.match'),
        ('Preferences Space Background', 'preferences.space.back'),
        ('Preferences Space Header', 'preferences.space.header'),
        ('Preferences Space Header Text', 'preferences.space.header_text'),
        ('Preferences Space Header Text Hi', 'preferences.space.header_text_hi'),
        ('Preferences Space Text', 'preferences.space.text'),
        ('Preferences Space Text Hi', 'preferences.space.text_hi'),
        ('Preferences Space Title', 'preferences.space.title'),
        ('Spreadsheet Row Alternate', 'spreadsheet.row_alternate'),
        ('Spreadsheet Space Background', 'spreadsheet.space.back'),
        ('Spreadsheet Space Header', 'spreadsheet.space.header'),
        ('Spreadsheet Space Header Text', 'spreadsheet.space.header_text'),
        ('Spreadsheet Space Header Text Hi', 'spreadsheet.space.header_text_hi'),
        ('Spreadsheet Space Text', 'spreadsheet.space.text'),
        ('Spreadsheet Space Text Hi', 'spreadsheet.space.text_hi'),
        ('Spreadsheet Space Title', 'spreadsheet.space.title'),
        ('Text Editor Cursor', 'text_editor.cursor'),
        ('Text Editor Line Numbers', 'text_editor.line_numbers'),
        ('Text Editor Line Numbers Background', 'text_editor.line_numbers_background'),
        ('Text Editor Selected Text', 'text_editor.selected_text'),
        ('Text Editor Space Background', 'text_editor.space.back'),
        ('Text Editor Space Header', 'text_editor.space.header'),
        ('Text Editor Space Header Text', 'text_editor.space.header_text'),
        ('Text Editor Space Header Text Hi', 'text_editor.space.header_text_hi'),
        ('Text Editor Space Text', 'text_editor.space.text'),
        ('Text Editor Space Text Hi', 'text_editor.space.text_hi'),
        ('Text Editor Space Title', 'text_editor.space.title'),
        ('Text Editor Syntax Builtin', 'text_editor.syntax_builtin'),
        ('Text Editor Syntax Comment', 'text_editor.syntax_comment'),
        ('Text Editor Syntax Numbers', 'text_editor.syntax_numbers'),
        ('Text Editor Syntax Preprocessor', 'text_editor.syntax_preprocessor'),
        ('Text Editor Syntax Reserved', 'text_editor.syntax_reserved'),
        ('Text Editor Syntax Special', 'text_editor.syntax_special'),
        ('Text Editor Syntax String', 'text_editor.syntax_string'),
        ('Text Editor Syntax Symbols', 'text_editor.syntax_symbols'),
        ('User Interface Icon Autokey', 'user_interface.icon_autokey'),
        ('User Interface Icon Collection', 'user_interface.icon_collection'),
        ('User Interface Icon Folder', 'user_interface.icon_folder'),
        ('User Interface Icon Modifier', 'user_interface.icon_modifier'),
        ('User Interface Icon Object', 'user_interface.icon_object'),
        ('User Interface Icon Object Data', 'user_interface.icon_object_data'),
        ('User Interface Icon Scene', 'user_interface.icon_scene'),
        ('User Interface Icon Shading', 'user_interface.icon_shading'),
        ('User Interface Box Inner', 'user_interface.wcol_box.inner'),
        ('User Interface Box Inner Selected', 'user_interface.wcol_box.inner_sel'),
        ('User Interface Box Item', 'user_interface.wcol_box.item'),
        ('User Interface Box Outline', 'user_interface.wcol_box.outline'),
        ('User Interface Box Outline Selected', 'user_interface.wcol_box.outline_sel'),
        ('User Interface Box Text', 'user_interface.wcol_box.text'),
        ('User Interface Box Text Selected', 'user_interface.wcol_box.text_sel'),
        ('User Interface Curve Widget Inner', 'user_interface.wcol_curve.inner'),
        ('User Interface Curve Widget Inner Selected', 'user_interface.wcol_curve.inner_sel'),
        ('User Interface Curve Widget Item', 'user_interface.wcol_curve.item'),
        ('User Interface Curve Widget Outline', 'user_interface.wcol_curve.outline'),
        ('User Interface Curve Widget Outline Selected', 'user_interface.wcol_curve.outline_sel'),
        ('User Interface Curve Widget Text', 'user_interface.wcol_curve.text'),
        ('User Interface Curve Widget Text Selected', 'user_interface.wcol_curve.text_sel'),
        ('User Interface List Item Inner', 'user_interface.wcol_list_item.inner'),
        ('User Interface List Item Inner Selected', 'user_interface.wcol_list_item.inner_sel'),
        ('User Interface List Item Item', 'user_interface.wcol_list_item.item'),
        ('User Interface List Item Outline', 'user_interface.wcol_list_item.outline'),
        ('User Interface List Item Outline Selected', 'user_interface.wcol_list_item.outline_sel'),
        ('User Interface List Item Text', 'user_interface.wcol_list_item.text'),
        ('User Interface List Item Text Selected', 'user_interface.wcol_list_item.text_sel'),
        ('User Interface Number Widget Inner', 'user_interface.wcol_num.inner'),
        ('User Interface Number Widget Inner Selected', 'user_interface.wcol_num.inner_sel'),
        ('User Interface Number Widget Item', 'user_interface.wcol_num.item'),
        ('User Interface Number Widget Outline', 'user_interface.wcol_num.outline'),
        ('User Interface Number Widget Outline Selected', 'user_interface.wcol_num.outline_sel'),
        ('User Interface Number Widget Text', 'user_interface.wcol_num.text'),
        ('User Interface Number Widget Text Selected', 'user_interface.wcol_num.text_sel'),
        ('User Interface Slider Widget Inner', 'user_interface.wcol_numslider.inner'),
        ('User Interface Slider Widget Inner Selected', 'user_interface.wcol_numslider.inner_sel'),
        ('User Interface Slider Widget Item', 'user_interface.wcol_numslider.item'),
        ('User Interface Slider Widget Outline', 'user_interface.wcol_numslider.outline'),
        ('User Interface Slider Widget Outline Selected', 'user_interface.wcol_numslider.outline_sel'),
        ('User Interface Slider Widget Text', 'user_interface.wcol_numslider.text'),
        ('User Interface Slider Widget Text Selected', 'user_interface.wcol_numslider.text_sel'),
        ('User Interface Option Widget Inner', 'user_interface.wcol_option.inner'),
        ('User Interface Option Widget Inner Selected', 'user_interface.wcol_option.inner_sel'),
        ('User Interface Option Widget Item', 'user_interface.wcol_option.item'),
        ('User Interface Option Widget Outline', 'user_interface.wcol_option.outline'),
        ('User Interface Option Widget Outline Selected', 'user_interface.wcol_option.outline_sel'),
        ('User Interface Option Widget Text', 'user_interface.wcol_option.text'),
        ('User Interface Option Widget Text Selected', 'user_interface.wcol_option.text_sel'),
        ('User Interface Radio Widget Inner', 'user_interface.wcol_radio.inner'),
        ('User Interface Radio Widget Inner Selected', 'user_interface.wcol_radio.inner_sel'),
        ('User Interface Radio Widget Item', 'user_interface.wcol_radio.item'),
        ('User Interface Radio Widget Outline', 'user_interface.wcol_radio.outline'),
        ('User Interface Radio Widget Outline Selected', 'user_interface.wcol_radio.outline_sel'),
        ('User Interface Radio Widget Text', 'user_interface.wcol_radio.text'),
        ('User Interface Radio Widget Text Selected', 'user_interface.wcol_radio.text_sel'),
        ('User Interface Regular Widget Inner', 'user_interface.wcol_regular.inner'),
        ('User Interface Regular Widget Inner Selected', 'user_interface.wcol_regular.inner_sel'),
        ('User Interface Regular Widget Item', 'user_interface.wcol_regular.item'),
        ('User Interface Regular Widget Outline', 'user_interface.wcol_regular.outline'),
        ('User Interface Regular Widget Outline Selected', 'user_interface.wcol_regular.outline_sel'),
        ('User Interface Regular Widget Text', 'user_interface.wcol_regular.text'),
        ('User Interface Regular Widget Text Selected', 'user_interface.wcol_regular.text_sel'),
        ('User Interface Scroll Widget Inner', 'user_interface.wcol_scroll.inner'),
        ('User Interface Scroll Widget Inner Selected', 'user_interface.wcol_scroll.inner_sel'),
        ('User Interface Scroll Widget Item', 'user_interface.wcol_scroll.item'),
        ('User Interface Scroll Widget Outline', 'user_interface.wcol_scroll.outline'),
        ('User Interface Scroll Widget Outline Selected', 'user_interface.wcol_scroll.outline_sel'),
        ('User Interface Scroll Widget Text', 'user_interface.wcol_scroll.text'),
        ('User Interface Scroll Widget Text Selected', 'user_interface.wcol_scroll.text_sel'),
        ('User Interface Tab Inner', 'user_interface.wcol_tab.inner'),
        ('User Interface Tab Inner Selected', 'user_interface.wcol_tab.inner_sel'),
        ('User Interface Tab Item', 'user_interface.wcol_tab.item'),
        ('User Interface Tab Outline', 'user_interface.wcol_tab.outline'),
        ('User Interface Tab Outline Selected', 'user_interface.wcol_tab.outline_sel'),
        ('User Interface Tab Text', 'user_interface.wcol_tab.text'),
        ('User Interface Tab Text Selected', 'user_interface.wcol_tab.text_sel'),
        ('User Interface Text Widget Inner', 'user_interface.wcol_text.inner'),
        ('User Interface Text Widget Inner Selected', 'user_interface.wcol_text.inner_sel'),
        ('User Interface Text Widget Item', 'user_interface.wcol_text.item'),
        ('User Interface Text Widget Outline', 'user_interface.wcol_text.outline'),
        ('User Interface Text Widget Outline Selected', 'user_interface.wcol_text.outline_sel'),
        ('User Interface Text Widget Text', 'user_interface.wcol_text.text'),
        ('User Interface Text Widget Text Selected', 'user_interface.wcol_text.text_sel'),
        ('User Interface Toggle Widget Inner', 'user_interface.wcol_toggle.inner'),
        ('User Interface Toggle Widget Inner Selected', 'user_interface.wcol_toggle.inner_sel'),
        ('User Interface Toggle Widget Item', 'user_interface.wcol_toggle.item'),
        ('User Interface Toggle Widget Outline', 'user_interface.wcol_toggle.outline'),
        ('User Interface Toggle Widget Outline Selected', 'user_interface.wcol_toggle.outline_sel'),
        ('User Interface Toggle Widget Text', 'user_interface.wcol_toggle.text'),
        ('User Interface Toggle Widget Text Selected', 'user_interface.wcol_toggle.text_sel'),
        ('User Interface Widget Emboss', 'user_interface.widget_emboss'),
        ('User Interface Text Cursor', 'user_interface.widget_text_cursor'),
    ],
    'MD_18': [
        ('Regions Asset Shelf Background', 'regions.asset_shelf.back'),
        ('Regions Asset Shelf Header Background', 'regions.asset_shelf.header_back'),
        ('Regions Channels Background', 'regions.channels.back'),
        ('Regions Channels Text', 'regions.channels.text'),
        ('Regions Channels Text Selected', 'regions.channels.text_selected'),
        ('Regions Scrubbing Background', 'regions.scrubbing.back'),
        ('Regions Scrubbing Text', 'regions.scrubbing.text'),
        ('Regions Scrubbing Time Marker', 'regions.scrubbing.time_marker'),
        ('Regions Scrubbing Time Marker Selected', 'regions.scrubbing.time_marker_selected'),
    ],
}

SEMANTIC_LINKED_COUNTS = {
    "MD_01": 42,
    "MD_02": 17,
    "MD_03": 9,
    "TOP_BAR_AREA": 7,
    "STATUS_BAR_AREA": 7,
    "SCREEN_BOUNDARY_AREA": 3,
    "MD_04": 14,
    "MD_05": 10,
    "VIEW_3D_GIZMO_AREA": 10,
    "VIEW_3D_NAVIGATION_AREA": 6,
    "UI_NAVIGATION_AREA": 29,
    "MD_06": 26,
    "MD_07": 25,
    "MD_08": 16,
    "MD_09": 64,
    "MD_10": 4,
    "MD_11": 78,
    "MD_12": 35,
    "MD_13": 8,
    "MD_14": 14,
    "MD_15": 26,
    "MD_16": 29,
    "MD_17": 95,
    "MD_18": 9,
}


SHORTCUT_MAP_TYPES = (
    ("KEYBOARD", "Keyboard", "Use a keyboard shortcut"),
    ("MOUSE", "Mouse", "Use a mouse shortcut"),
)



THEME_PATH_LABELS_EN = {
    'bone_color_sets[0].active': 'Bone Color Set 0 Active',
    'bone_color_sets[0].normal': 'Bone Color Set 0 Normal',
    'bone_color_sets[0].select': 'Bone Color Set 0 Select',
    'bone_color_sets[10].active': 'Bone Color Set 10 Active',
    'bone_color_sets[10].normal': 'Bone Color Set 10 Normal',
    'bone_color_sets[10].select': 'Bone Color Set 10 Select',
    'bone_color_sets[11].active': 'Bone Color Set 11 Active',
    'bone_color_sets[11].normal': 'Bone Color Set 11 Normal',
    'bone_color_sets[11].select': 'Bone Color Set 11 Select',
    'bone_color_sets[12].active': 'Bone Color Set 12 Active',
    'bone_color_sets[12].normal': 'Bone Color Set 12 Normal',
    'bone_color_sets[12].select': 'Bone Color Set 12 Select',
    'bone_color_sets[13].active': 'Bone Color Set 13 Active',
    'bone_color_sets[13].normal': 'Bone Color Set 13 Normal',
    'bone_color_sets[13].select': 'Bone Color Set 13 Select',
    'bone_color_sets[14].active': 'Bone Color Set 14 Active',
    'bone_color_sets[14].normal': 'Bone Color Set 14 Normal',
    'bone_color_sets[14].select': 'Bone Color Set 14 Select',
    'bone_color_sets[15].active': 'Bone Color Set 15 Active',
    'bone_color_sets[15].normal': 'Bone Color Set 15 Normal',
    'bone_color_sets[15].select': 'Bone Color Set 15 Select',
    'bone_color_sets[16].active': 'Bone Color Set 16 Active',
    'bone_color_sets[16].normal': 'Bone Color Set 16 Normal',
    'bone_color_sets[16].select': 'Bone Color Set 16 Select',
    'bone_color_sets[17].active': 'Bone Color Set 17 Active',
    'bone_color_sets[17].normal': 'Bone Color Set 17 Normal',
    'bone_color_sets[17].select': 'Bone Color Set 17 Select',
    'bone_color_sets[18].active': 'Bone Color Set 18 Active',
    'bone_color_sets[18].normal': 'Bone Color Set 18 Normal',
    'bone_color_sets[18].select': 'Bone Color Set 18 Select',
    'bone_color_sets[19].active': 'Bone Color Set 19 Active',
    'bone_color_sets[19].normal': 'Bone Color Set 19 Normal',
    'bone_color_sets[19].select': 'Bone Color Set 19 Select',
    'bone_color_sets[1].active': 'Bone Color Set 1 Active',
    'bone_color_sets[1].normal': 'Bone Color Set 1 Normal',
    'bone_color_sets[1].select': 'Bone Color Set 1 Select',
    'bone_color_sets[2].active': 'Bone Color Set 2 Active',
    'bone_color_sets[2].normal': 'Bone Color Set 2 Normal',
    'bone_color_sets[2].select': 'Bone Color Set 2 Select',
    'bone_color_sets[3].active': 'Bone Color Set 3 Active',
    'bone_color_sets[3].normal': 'Bone Color Set 3 Normal',
    'bone_color_sets[3].select': 'Bone Color Set 3 Select',
    'bone_color_sets[4].active': 'Bone Color Set 4 Active',
    'bone_color_sets[4].normal': 'Bone Color Set 4 Normal',
    'bone_color_sets[4].select': 'Bone Color Set 4 Select',
    'bone_color_sets[5].active': 'Bone Color Set 5 Active',
    'bone_color_sets[5].normal': 'Bone Color Set 5 Normal',
    'bone_color_sets[5].select': 'Bone Color Set 5 Select',
    'bone_color_sets[6].active': 'Bone Color Set 6 Active',
    'bone_color_sets[6].normal': 'Bone Color Set 6 Normal',
    'bone_color_sets[6].select': 'Bone Color Set 6 Select',
    'bone_color_sets[7].active': 'Bone Color Set 7 Active',
    'bone_color_sets[7].normal': 'Bone Color Set 7 Normal',
    'bone_color_sets[7].select': 'Bone Color Set 7 Select',
    'bone_color_sets[8].active': 'Bone Color Set 8 Active',
    'bone_color_sets[8].normal': 'Bone Color Set 8 Normal',
    'bone_color_sets[8].select': 'Bone Color Set 8 Select',
    'bone_color_sets[9].active': 'Bone Color Set 9 Active',
    'bone_color_sets[9].normal': 'Bone Color Set 9 Normal',
    'bone_color_sets[9].select': 'Bone Color Set 9 Select',
    'clip_editor.active_marker': 'Clip Editor Active Marker',
    'clip_editor.disabled_marker': 'Clip Editor Disabled Marker',
    'clip_editor.grid': 'Clip Editor Grid',
    'clip_editor.locked_marker': 'Clip Editor Locked Marker',
    'clip_editor.marker': 'Clip Editor Marker',
    'clip_editor.marker_outline': 'Clip Editor Marker Outline',
    'clip_editor.metadatabg': 'Clip Editor Metadatabg',
    'clip_editor.metadatatext': 'Clip Editor Metadatatext',
    'clip_editor.path_after': 'Clip Editor Path After',
    'clip_editor.path_before': 'Clip Editor Path Before',
    'clip_editor.path_keyframe_after': 'Clip Editor Path Keyframe After',
    'clip_editor.path_keyframe_before': 'Clip Editor Path Keyframe Before',
    'clip_editor.selected_marker': 'Clip Editor Selected Marker',
    'clip_editor.space.back': 'Clip Editor Space Background',
    'clip_editor.space.header': 'Clip Editor Space Header',
    'clip_editor.space.header_text': 'Clip Editor Space Header Text',
    'clip_editor.space.header_text_hi': 'Clip Editor Space Header Text Hi',
    'clip_editor.space.text': 'Clip Editor Space Text',
    'clip_editor.space.text_hi': 'Clip Editor Space Text Hi',
    'clip_editor.space.title': 'Clip Editor Space Title',
    'collection_color[0].color': 'Collection Color 0 Color',
    'collection_color[1].color': 'Collection Color 1 Color',
    'collection_color[2].color': 'Collection Color 2 Color',
    'collection_color[3].color': 'Collection Color 3 Color',
    'collection_color[4].color': 'Collection Color 4 Color',
    'collection_color[5].color': 'Collection Color 5 Color',
    'collection_color[6].color': 'Collection Color 6 Color',
    'collection_color[7].color': 'Collection Color 7 Color',
    'common.anim.channel': 'Common Animation Channel',
    'common.anim.channel_group': 'Common Animation Channel Group',
    'common.anim.channel_group_active': 'Common Animation Channel Group Active',
    'common.anim.channel_selected': 'Common Animation Channel Selected',
    'common.anim.channels': 'Common Animation Channels',
    'common.anim.channels_sub': 'Common Animation Channels Sub',
    'common.anim.keyframe': 'Common Animation Keyframe',
    'common.anim.keyframe_breakdown': 'Common Animation Keyframe Breakdown',
    'common.anim.keyframe_breakdown_selected': 'Common Animation Keyframe Breakdown Selected',
    'common.anim.keyframe_extreme': 'Common Animation Keyframe Extreme',
    'common.anim.keyframe_extreme_selected': 'Common Animation Keyframe Extreme Selected',
    'common.anim.keyframe_generated': 'Common Animation Keyframe Generated',
    'common.anim.keyframe_generated_selected': 'Common Animation Keyframe Generated Selected',
    'common.anim.keyframe_jitter': 'Common Animation Keyframe Jitter',
    'common.anim.keyframe_jitter_selected': 'Common Animation Keyframe Jitter Selected',
    'common.anim.keyframe_moving_hold': 'Common Animation Keyframe Moving Hold',
    'common.anim.keyframe_moving_hold_selected': 'Common Animation Keyframe Moving Hold Selected',
    'common.anim.keyframe_selected': 'Common Animation Keyframe Selected',
    'common.anim.long_key': 'Common Animation Long Key',
    'common.anim.long_key_selected': 'Common Animation Long Key Selected',
    'common.anim.playhead': 'Common Animation Playhead',
    'common.anim.preview_range': 'Common Animation Preview Range',
    'common.anim.scene_strip_range': 'Common Animation Scene Strip Range',
    'common.curves.handle_align': 'Common Curves Handle Align',
    'common.curves.handle_auto': 'Common Curves Handle Auto',
    'common.curves.handle_auto_clamped': 'Common Curves Handle Auto Clamped',
    'common.curves.handle_free': 'Common Curves Handle Free',
    'common.curves.handle_sel_align': 'Common Curves Handle Sel Align',
    'common.curves.handle_sel_auto': 'Common Curves Handle Sel Auto',
    'common.curves.handle_sel_auto_clamped': 'Common Curves Handle Sel Auto Clamped',
    'common.curves.handle_sel_free': 'Common Curves Handle Sel Free',
    'common.curves.handle_sel_vect': 'Common Curves Handle Sel Vect',
    'common.curves.handle_vect': 'Common Curves Handle Vect',
    'common.curves.handle_vertex': 'Common Curves Handle Vertex',
    'common.curves.handle_vertex_select': 'Common Curves Handle Vertex Select',
    'console.cursor': 'Python Console Cursor',
    'console.line_error': 'Python Console Line Error',
    'console.line_info': 'Python Console Line Info',
    'console.line_input': 'Python Console Line Input',
    'console.line_output': 'Python Console Line Output',
    'console.select': 'Python Console Select',
    'console.space.back': 'Python Console Space Background',
    'console.space.header': 'Python Console Space Header',
    'console.space.header_text': 'Python Console Space Header Text',
    'console.space.header_text_hi': 'Python Console Space Header Text Hi',
    'console.space.text': 'Python Console Space Text',
    'console.space.text_hi': 'Python Console Space Text Hi',
    'console.space.title': 'Python Console Space Title',
    'dopesheet_editor.anim_interpolation_constant': 'Dope Sheet Anim Interpolation Constant',
    'dopesheet_editor.anim_interpolation_linear': 'Dope Sheet Anim Interpolation Linear',
    'dopesheet_editor.anim_interpolation_other': 'Dope Sheet Anim Interpolation Other',
    'dopesheet_editor.grid': 'Dope Sheet Grid',
    'dopesheet_editor.keyframe_border': 'Dope Sheet Keyframe Border',
    'dopesheet_editor.keyframe_border_selected': 'Dope Sheet Keyframe Border Selected',
    'dopesheet_editor.simulated_frames': 'Dope Sheet Simulated Frames',
    'dopesheet_editor.space.back': 'Dope Sheet Space Background',
    'dopesheet_editor.space.header': 'Dope Sheet Space Header',
    'dopesheet_editor.space.header_text': 'Dope Sheet Space Header Text',
    'dopesheet_editor.space.header_text_hi': 'Dope Sheet Space Header Text Hi',
    'dopesheet_editor.space.text': 'Dope Sheet Space Text',
    'dopesheet_editor.space.text_hi': 'Dope Sheet Space Text Hi',
    'dopesheet_editor.space.title': 'Dope Sheet Space Title',
    'dopesheet_editor.summary': 'Dope Sheet Summary',
    'file_browser.row_alternate': 'File Browser Row Alternate',
    'file_browser.selected_file': 'File Browser Selected File',
    'file_browser.space.back': 'File Browser Space Background',
    'file_browser.space.header': 'File Browser Space Header',
    'file_browser.space.header_text': 'File Browser Space Header Text',
    'file_browser.space.header_text_hi': 'File Browser Space Header Text Hi',
    'file_browser.space.text': 'File Browser Space Text',
    'file_browser.space.text_hi': 'File Browser Space Text Hi',
    'file_browser.space.title': 'File Browser Space Title',
    'graph_editor.grid': 'Graph Editor Grid',
    'graph_editor.space.back': 'Graph Editor Space Background',
    'graph_editor.space.header': 'Graph Editor Space Header',
    'graph_editor.space.header_text': 'Graph Editor Space Header Text',
    'graph_editor.space.header_text_hi': 'Graph Editor Space Header Text Hi',
    'graph_editor.space.text': 'Graph Editor Space Text',
    'graph_editor.space.text_hi': 'Graph Editor Space Text Hi',
    'graph_editor.space.title': 'Graph Editor Space Title',
    'graph_editor.vertex': 'Graph Editor Vertex',
    'graph_editor.vertex_active': 'Graph Editor Vertex Active',
    'graph_editor.vertex_select': 'Graph Editor Vertex Select',
    'image_editor.edge_select': 'Image Editor Edge Select',
    'image_editor.editmesh_active': 'Image Editor Editmesh Active',
    'image_editor.face': 'Image Editor Face',
    'image_editor.face_mode_select': 'Image Editor Face Mode Select',
    'image_editor.face_select': 'Image Editor Face Select',
    'image_editor.grid': 'Image Editor Grid',
    'image_editor.metadatabg': 'Image Editor Metadatabg',
    'image_editor.metadatatext': 'Image Editor Metadatatext',
    'image_editor.preview_stitch_active': 'Image Editor Preview Stitch Active',
    'image_editor.preview_stitch_edge': 'Image Editor Preview Stitch Edge',
    'image_editor.preview_stitch_face': 'Image Editor Preview Stitch Face',
    'image_editor.preview_stitch_stitchable': 'Image Editor Preview Stitch Stitchable',
    'image_editor.preview_stitch_unstitchable': 'Image Editor Preview Stitch Unstitchable',
    'image_editor.preview_stitch_vert': 'Image Editor Preview Stitch Vert',
    'image_editor.scope_back': 'Image Editor Scope Back',
    'image_editor.space.back': 'Image Editor Space Background',
    'image_editor.space.header': 'Image Editor Space Header',
    'image_editor.space.header_text': 'Image Editor Space Header Text',
    'image_editor.space.header_text_hi': 'Image Editor Space Header Text Hi',
    'image_editor.space.text': 'Image Editor Space Text',
    'image_editor.space.text_hi': 'Image Editor Space Text Hi',
    'image_editor.space.title': 'Image Editor Space Title',
    'image_editor.uv_shadow': 'Image Editor Uv Shadow',
    'image_editor.vertex': 'Image Editor Vertex',
    'image_editor.vertex_select': 'Image Editor Vertex Select',
    'image_editor.wire_edit': 'Image Editor Wire Edit',
    'info.info_debug': 'Info Info Debug',
    'info.info_debug_text': 'Info Info Debug Text',
    'info.info_error_text': 'Info Info Error Text',
    'info.info_info_text': 'Info Info Info Text',
    'info.info_operator': 'Info Info Operator',
    'info.info_operator_text': 'Info Info Operator Text',
    'info.info_property': 'Info Info Property',
    'info.info_property_text': 'Info Info Property Text',
    'info.info_selected': 'Info Info Selected',
    'info.info_selected_text': 'Info Info Selected Text',
    'info.info_warning_text': 'Info Info Warning Text',
    'info.space.back': 'Info Space Background',
    'info.space.header': 'Info Space Header',
    'info.space.header_text': 'Info Space Header Text',
    'info.space.header_text_hi': 'Info Space Header Text Hi',
    'info.space.text': 'Info Space Text',
    'info.space.text_hi': 'Info Space Text Hi',
    'info.space.title': 'Info Space Title',
    'nla_editor.active_action': 'NLA Editor Active Action',
    'nla_editor.active_action_unset': 'NLA Editor Active Action Unset',
    'nla_editor.grid': 'NLA Editor Grid',
    'nla_editor.keyframe_border': 'NLA Editor Keyframe Border',
    'nla_editor.keyframe_border_selected': 'NLA Editor Keyframe Border Selected',
    'nla_editor.meta_strips': 'NLA Editor Meta Strips',
    'nla_editor.meta_strips_selected': 'NLA Editor Meta Strips Selected',
    'nla_editor.sound_strips': 'NLA Editor Sound Strips',
    'nla_editor.sound_strips_selected': 'NLA Editor Sound Strips Selected',
    'nla_editor.space.back': 'NLA Editor Space Background',
    'nla_editor.space.header': 'NLA Editor Space Header',
    'nla_editor.space.header_text': 'NLA Editor Space Header Text',
    'nla_editor.space.header_text_hi': 'NLA Editor Space Header Text Hi',
    'nla_editor.space.text': 'NLA Editor Space Text',
    'nla_editor.space.text_hi': 'NLA Editor Space Text Hi',
    'nla_editor.space.title': 'NLA Editor Space Title',
    'nla_editor.strips': 'NLA Editor Strips',
    'nla_editor.strips_selected': 'NLA Editor Strips Selected',
    'nla_editor.transition_strips': 'NLA Editor Transition Strips',
    'nla_editor.transition_strips_selected': 'NLA Editor Transition Strips Selected',
    'nla_editor.tweak': 'NLA Editor Tweak',
    'nla_editor.tweak_duplicate': 'NLA Editor Tweak Duplicate',
    'node_editor.attribute_node': 'Node Editor Attribute Node',
    'node_editor.closure_zone': 'Node Editor Closure Zone',
    'node_editor.color_node': 'Node Editor Color Node',
    'node_editor.converter_node': 'Node Editor Converter Node',
    'node_editor.distor_node': 'Node Editor Distor Node',
    'node_editor.filter_node': 'Node Editor Filter Node',
    'node_editor.foreach_geometry_element_zone': 'Node Editor Foreach Geometry Element Zone',
    'node_editor.frame_node': 'Node Editor Frame Node',
    'node_editor.geometry_node': 'Node Editor Geometry Node',
    'node_editor.grid': 'Node Editor Grid',
    'node_editor.group_node': 'Node Editor Group Node',
    'node_editor.group_socket_node': 'Node Editor Group Socket Node',
    'node_editor.input_node': 'Node Editor Input Node',
    'node_editor.matte_node': 'Node Editor Matte Node',
    'node_editor.node_active': 'Node Editor Node Active',
    'node_editor.node_backdrop': 'Node Editor Node Backdrop',
    'node_editor.node_outline': 'Node Editor Node Outline',
    'node_editor.node_selected': 'Node Editor Node Selected',
    'node_editor.output_node': 'Node Editor Output Node',
    'node_editor.repeat_zone': 'Node Editor Repeat Zone',
    'node_editor.script_node': 'Node Editor Script Node',
    'node_editor.shader_node': 'Node Editor Shader Node',
    'node_editor.simulation_zone': 'Node Editor Simulation Zone',
    'node_editor.space.back': 'Node Editor Space Background',
    'node_editor.space.header': 'Node Editor Space Header',
    'node_editor.space.header_text': 'Node Editor Space Header Text',
    'node_editor.space.header_text_hi': 'Node Editor Space Header Text Hi',
    'node_editor.space.text': 'Node Editor Space Text',
    'node_editor.space.text_hi': 'Node Editor Space Text Hi',
    'node_editor.space.title': 'Node Editor Space Title',
    'node_editor.texture_node': 'Node Editor Texture Node',
    'node_editor.vector_node': 'Node Editor Vector Node',
    'node_editor.wire': 'Node Editor Wire',
    'node_editor.wire_inner': 'Node Editor Wire Inner',
    'node_editor.wire_select': 'Node Editor Wire Select',
    'outliner.active': 'Outliner Active',
    'outliner.active_object': 'Outliner Active Object',
    'outliner.edited_object': 'Outliner Edited Object',
    'outliner.match': 'Outliner Match',
    'outliner.row_alternate': 'Outliner Row Alternate',
    'outliner.selected_highlight': 'Outliner Selected Highlight',
    'outliner.selected_object': 'Outliner Selected Object',
    'outliner.space.back': 'Outliner Space Background',
    'outliner.space.header': 'Outliner Space Header',
    'outliner.space.header_text': 'Outliner Space Header Text',
    'outliner.space.header_text_hi': 'Outliner Space Header Text Hi',
    'outliner.space.text': 'Outliner Space Text',
    'outliner.space.text_hi': 'Outliner Space Text Hi',
    'outliner.space.title': 'Outliner Space Title',
    'preferences.match': 'Preferences Match',
    'preferences.space.back': 'Preferences Space Background',
    'preferences.space.header': 'Preferences Space Header',
    'preferences.space.header_text': 'Preferences Space Header Text',
    'preferences.space.header_text_hi': 'Preferences Space Header Text Hi',
    'preferences.space.text': 'Preferences Space Text',
    'preferences.space.text_hi': 'Preferences Space Text Hi',
    'preferences.space.title': 'Preferences Space Title',
    'properties.match': 'Properties Match',
    'properties.space.back': 'Properties Space Background',
    'properties.space.header': 'Properties Space Header',
    'properties.space.header_text': 'Properties Space Header Text',
    'properties.space.header_text_hi': 'Properties Space Header Text Hi',
    'properties.space.text': 'Properties Space Text',
    'properties.space.text_hi': 'Properties Space Text Hi',
    'properties.space.title': 'Properties Space Title',
    'regions.asset_shelf.back': 'Regions Asset Shelf Background',
    'regions.asset_shelf.header_back': 'Regions Asset Shelf Header Background',
    'regions.channels.back': 'Regions Channels Background',
    'regions.channels.text': 'Regions Channels Text',
    'regions.channels.text_selected': 'Regions Channels Text Selected',
    'regions.scrubbing.back': 'Regions Scrubbing Background',
    'regions.scrubbing.text': 'Regions Scrubbing Text',
    'regions.scrubbing.time_marker': 'Regions Scrubbing Time Marker',
    'regions.scrubbing.time_marker_selected': 'Regions Scrubbing Time Marker Selected',
    'regions.sidebars.back': 'Regions Sidebars Background',
    'regions.sidebars.tab_back': 'Regions Sidebars Navigation/Tabs Background',
    'sequence_editor.active_strip': 'Video Sequencer Active Strip',
    'sequence_editor.audio_strip': 'Video Sequencer Audio Strip',
    'sequence_editor.color_strip': 'Video Sequencer Color Strip',
    'sequence_editor.effect_strip': 'Video Sequencer Effect Strip',
    'sequence_editor.grid': 'Video Sequencer Grid',
    'sequence_editor.image_strip': 'Video Sequencer Image Strip',
    'sequence_editor.keyframe_border': 'Video Sequencer Keyframe Border',
    'sequence_editor.keyframe_border_selected': 'Video Sequencer Keyframe Border Selected',
    'sequence_editor.mask_strip': 'Video Sequencer Mask Strip',
    'sequence_editor.meta_strip': 'Video Sequencer Meta Strip',
    'sequence_editor.metadatabg': 'Video Sequencer Metadatabg',
    'sequence_editor.metadatatext': 'Video Sequencer Metadatatext',
    'sequence_editor.movie_strip': 'Video Sequencer Movie Strip',
    'sequence_editor.movieclip_strip': 'Video Sequencer Movieclip Strip',
    'sequence_editor.preview_back': 'Video Sequencer Preview Back',
    'sequence_editor.row_alternate': 'Video Sequencer Row Alternate',
    'sequence_editor.scene_strip': 'Video Sequencer Scene Strip',
    'sequence_editor.selected_strip': 'Video Sequencer Selected Strip',
    'sequence_editor.selected_text': 'Video Sequencer Selected Text',
    'sequence_editor.space.back': 'Video Sequencer Space Background',
    'sequence_editor.space.header': 'Video Sequencer Space Header',
    'sequence_editor.space.header_text': 'Video Sequencer Space Header Text',
    'sequence_editor.space.header_text_hi': 'Video Sequencer Space Header Text Hi',
    'sequence_editor.space.text': 'Video Sequencer Space Text',
    'sequence_editor.space.text_hi': 'Video Sequencer Space Text Hi',
    'sequence_editor.space.title': 'Video Sequencer Space Title',
    'sequence_editor.text_strip': 'Video Sequencer Text Strip',
    'sequence_editor.text_strip_cursor': 'Video Sequencer Text Strip Cursor',
    'sequence_editor.transition_strip': 'Video Sequencer Transition Strip',
    'spreadsheet.row_alternate': 'Spreadsheet Row Alternate',
    'spreadsheet.space.back': 'Spreadsheet Space Background',
    'spreadsheet.space.header': 'Spreadsheet Space Header',
    'spreadsheet.space.header_text': 'Spreadsheet Space Header Text',
    'spreadsheet.space.header_text_hi': 'Spreadsheet Space Header Text Hi',
    'spreadsheet.space.text': 'Spreadsheet Space Text',
    'spreadsheet.space.text_hi': 'Spreadsheet Space Text Hi',
    'spreadsheet.space.title': 'Spreadsheet Space Title',
    'statusbar.space.back': 'Status Bar Space Background',
    'statusbar.space.header': 'Status Bar Space Header',
    'statusbar.space.header_text': 'Status Bar Space Header Text',
    'statusbar.space.header_text_hi': 'Status Bar Space Header Text Hi',
    'statusbar.space.text': 'Status Bar Space Text',
    'statusbar.space.text_hi': 'Status Bar Space Text Hi',
    'statusbar.space.title': 'Status Bar Space Title',
    'strip_color[0].color': 'Strip Color 0 Color',
    'strip_color[1].color': 'Strip Color 1 Color',
    'strip_color[2].color': 'Strip Color 2 Color',
    'strip_color[3].color': 'Strip Color 3 Color',
    'strip_color[4].color': 'Strip Color 4 Color',
    'strip_color[5].color': 'Strip Color 5 Color',
    'strip_color[6].color': 'Strip Color 6 Color',
    'strip_color[7].color': 'Strip Color 7 Color',
    'strip_color[8].color': 'Strip Color 8 Color',
    'text_editor.cursor': 'Text Editor Cursor',
    'text_editor.line_numbers': 'Text Editor Line Numbers',
    'text_editor.line_numbers_background': 'Text Editor Line Numbers Background',
    'text_editor.selected_text': 'Text Editor Selected Text',
    'text_editor.space.back': 'Text Editor Space Background',
    'text_editor.space.header': 'Text Editor Space Header',
    'text_editor.space.header_text': 'Text Editor Space Header Text',
    'text_editor.space.header_text_hi': 'Text Editor Space Header Text Hi',
    'text_editor.space.text': 'Text Editor Space Text',
    'text_editor.space.text_hi': 'Text Editor Space Text Hi',
    'text_editor.space.title': 'Text Editor Space Title',
    'text_editor.syntax_builtin': 'Text Editor Syntax Builtin',
    'text_editor.syntax_comment': 'Text Editor Syntax Comment',
    'text_editor.syntax_numbers': 'Text Editor Syntax Numbers',
    'text_editor.syntax_preprocessor': 'Text Editor Syntax Preprocessor',
    'text_editor.syntax_reserved': 'Text Editor Syntax Reserved',
    'text_editor.syntax_special': 'Text Editor Syntax Special',
    'text_editor.syntax_string': 'Text Editor Syntax String',
    'text_editor.syntax_symbols': 'Text Editor Syntax Symbols',
    'topbar.space.back': 'Top Bar Space Background',
    'topbar.space.header': 'Top Bar Space Header',
    'topbar.space.header_text': 'Top Bar Space Header Text',
    'topbar.space.header_text_hi': 'Top Bar Space Header Text Hi',
    'topbar.space.text': 'Top Bar Space Text',
    'topbar.space.text_hi': 'Top Bar Space Text Hi',
    'topbar.space.title': 'Top Bar Space Title',
    'user_interface.axis_w': 'User Interface Axis W',
    'user_interface.axis_x': 'User Interface Axis X',
    'user_interface.axis_y': 'User Interface Axis Y',
    'user_interface.axis_z': 'User Interface Axis Z',
    'user_interface.editor_border': 'User Interface Editor Border',
    'user_interface.editor_outline': 'User Interface Editor Outline',
    'user_interface.editor_outline_active': 'User Interface Editor Outline Active',
    'user_interface.gizmo_a': 'User Interface Gizmo A',
    'user_interface.gizmo_b': 'User Interface Gizmo B',
    'user_interface.gizmo_hi': 'User Interface Gizmo Hi',
    'user_interface.gizmo_primary': 'User Interface Gizmo Primary',
    'user_interface.gizmo_secondary': 'User Interface Gizmo Secondary',
    'user_interface.gizmo_view_align': 'User Interface Gizmo View Align',
    'user_interface.icon_autokey': 'User Interface Icon Autokey',
    'user_interface.icon_collection': 'User Interface Icon Collection',
    'user_interface.icon_folder': 'User Interface Icon Folder',
    'user_interface.icon_modifier': 'User Interface Icon Modifier',
    'user_interface.icon_object': 'User Interface Icon Object',
    'user_interface.icon_object_data': 'User Interface Icon Object Data',
    'user_interface.icon_scene': 'User Interface Icon Scene',
    'user_interface.icon_shading': 'User Interface Icon Shading',
    'user_interface.panel_active': 'User Interface Panel Active',
    'user_interface.panel_back': 'User Interface Panel Back',
    'user_interface.panel_header': 'User Interface Panel Header',
    'user_interface.panel_outline': 'User Interface Panel Outline',
    'user_interface.panel_sub_back': 'User Interface Panel Sub Back',
    'user_interface.panel_text': 'User Interface Panel Text',
    'user_interface.panel_title': 'User Interface Panel Title',
    'user_interface.transparent_checker_primary': 'User Interface Transparent Checker Primary',
    'user_interface.transparent_checker_secondary': 'User Interface Transparent Checker Secondary',
    'user_interface.wcol_box.inner': 'User Interface Box Inner',
    'user_interface.wcol_box.inner_sel': 'User Interface Box Inner Selected',
    'user_interface.wcol_box.item': 'User Interface Box Item',
    'user_interface.wcol_box.outline': 'User Interface Box Outline',
    'user_interface.wcol_box.outline_sel': 'User Interface Box Outline Selected',
    'user_interface.wcol_box.text': 'User Interface Box Text',
    'user_interface.wcol_box.text_sel': 'User Interface Box Text Selected',
    'user_interface.wcol_curve.inner': 'User Interface Curve Widget Inner',
    'user_interface.wcol_curve.inner_sel': 'User Interface Curve Widget Inner Selected',
    'user_interface.wcol_curve.item': 'User Interface Curve Widget Item',
    'user_interface.wcol_curve.outline': 'User Interface Curve Widget Outline',
    'user_interface.wcol_curve.outline_sel': 'User Interface Curve Widget Outline Selected',
    'user_interface.wcol_curve.text': 'User Interface Curve Widget Text',
    'user_interface.wcol_curve.text_sel': 'User Interface Curve Widget Text Selected',
    'user_interface.wcol_list_item.inner': 'User Interface List Item Inner',
    'user_interface.wcol_list_item.inner_sel': 'User Interface List Item Inner Selected',
    'user_interface.wcol_list_item.item': 'User Interface List Item Item',
    'user_interface.wcol_list_item.outline': 'User Interface List Item Outline',
    'user_interface.wcol_list_item.outline_sel': 'User Interface List Item Outline Selected',
    'user_interface.wcol_list_item.text': 'User Interface List Item Text',
    'user_interface.wcol_list_item.text_sel': 'User Interface List Item Text Selected',
    'user_interface.wcol_menu.inner': 'User Interface Menu Widget Inner',
    'user_interface.wcol_menu.inner_sel': 'User Interface Menu Widget Inner Selected',
    'user_interface.wcol_menu.item': 'User Interface Menu Widget Item',
    'user_interface.wcol_menu.outline': 'User Interface Menu Widget Outline',
    'user_interface.wcol_menu.outline_sel': 'User Interface Menu Widget Outline Selected',
    'user_interface.wcol_menu.text': 'User Interface Menu Widget Text',
    'user_interface.wcol_menu.text_sel': 'User Interface Menu Widget Text Selected',
    'user_interface.wcol_menu_back.inner': 'User Interface Menu Backdrop Inner',
    'user_interface.wcol_menu_back.inner_sel': 'User Interface Menu Backdrop Inner Selected',
    'user_interface.wcol_menu_back.item': 'User Interface Menu Backdrop Item',
    'user_interface.wcol_menu_back.outline': 'User Interface Menu Backdrop Outline',
    'user_interface.wcol_menu_back.outline_sel': 'User Interface Menu Backdrop Outline Selected',
    'user_interface.wcol_menu_back.text': 'User Interface Menu Backdrop Text',
    'user_interface.wcol_menu_back.text_sel': 'User Interface Menu Backdrop Text Selected',
    'user_interface.wcol_menu_item.inner': 'User Interface Menu Item Inner',
    'user_interface.wcol_menu_item.inner_sel': 'User Interface Menu Item Inner Selected',
    'user_interface.wcol_menu_item.item': 'User Interface Menu Item Item',
    'user_interface.wcol_menu_item.outline': 'User Interface Menu Item Outline',
    'user_interface.wcol_menu_item.outline_sel': 'User Interface Menu Item Outline Selected',
    'user_interface.wcol_menu_item.text': 'User Interface Menu Item Text',
    'user_interface.wcol_menu_item.text_sel': 'User Interface Menu Item Text Selected',
    'user_interface.wcol_num.inner': 'User Interface Number Widget Inner',
    'user_interface.wcol_num.inner_sel': 'User Interface Number Widget Inner Selected',
    'user_interface.wcol_num.item': 'User Interface Number Widget Item',
    'user_interface.wcol_num.outline': 'User Interface Number Widget Outline',
    'user_interface.wcol_num.outline_sel': 'User Interface Number Widget Outline Selected',
    'user_interface.wcol_num.text': 'User Interface Number Widget Text',
    'user_interface.wcol_num.text_sel': 'User Interface Number Widget Text Selected',
    'user_interface.wcol_numslider.inner': 'User Interface Slider Widget Inner',
    'user_interface.wcol_numslider.inner_sel': 'User Interface Slider Widget Inner Selected',
    'user_interface.wcol_numslider.item': 'User Interface Slider Widget Item',
    'user_interface.wcol_numslider.outline': 'User Interface Slider Widget Outline',
    'user_interface.wcol_numslider.outline_sel': 'User Interface Slider Widget Outline Selected',
    'user_interface.wcol_numslider.text': 'User Interface Slider Widget Text',
    'user_interface.wcol_numslider.text_sel': 'User Interface Slider Widget Text Selected',
    'user_interface.wcol_option.inner': 'User Interface Option Widget Inner',
    'user_interface.wcol_option.inner_sel': 'User Interface Option Widget Inner Selected',
    'user_interface.wcol_option.item': 'User Interface Option Widget Item',
    'user_interface.wcol_option.outline': 'User Interface Option Widget Outline',
    'user_interface.wcol_option.outline_sel': 'User Interface Option Widget Outline Selected',
    'user_interface.wcol_option.text': 'User Interface Option Widget Text',
    'user_interface.wcol_option.text_sel': 'User Interface Option Widget Text Selected',
    'user_interface.wcol_pie_menu.inner': 'User Interface Pie Menu Inner',
    'user_interface.wcol_pie_menu.inner_sel': 'User Interface Pie Menu Inner Selected',
    'user_interface.wcol_pie_menu.item': 'User Interface Pie Menu Item',
    'user_interface.wcol_pie_menu.outline': 'User Interface Pie Menu Outline',
    'user_interface.wcol_pie_menu.outline_sel': 'User Interface Pie Menu Outline Selected',
    'user_interface.wcol_pie_menu.text': 'User Interface Pie Menu Text',
    'user_interface.wcol_pie_menu.text_sel': 'User Interface Pie Menu Text Selected',
    'user_interface.wcol_progress.inner': 'User Interface Progress Bar Inner',
    'user_interface.wcol_progress.inner_sel': 'User Interface Progress Bar Inner Selected',
    'user_interface.wcol_progress.item': 'User Interface Progress Bar Item',
    'user_interface.wcol_progress.outline': 'User Interface Progress Bar Outline',
    'user_interface.wcol_progress.outline_sel': 'User Interface Progress Bar Outline Selected',
    'user_interface.wcol_progress.text': 'User Interface Progress Bar Text',
    'user_interface.wcol_progress.text_sel': 'User Interface Progress Bar Text Selected',
    'user_interface.wcol_pulldown.inner': 'User Interface Pulldown Widget Inner',
    'user_interface.wcol_pulldown.inner_sel': 'User Interface Pulldown Widget Inner Selected',
    'user_interface.wcol_pulldown.item': 'User Interface Pulldown Widget Item',
    'user_interface.wcol_pulldown.outline': 'User Interface Pulldown Widget Outline',
    'user_interface.wcol_pulldown.outline_sel': 'User Interface Pulldown Widget Outline Selected',
    'user_interface.wcol_pulldown.text': 'User Interface Pulldown Widget Text',
    'user_interface.wcol_pulldown.text_sel': 'User Interface Pulldown Widget Text Selected',
    'user_interface.wcol_radio.inner': 'User Interface Radio Widget Inner',
    'user_interface.wcol_radio.inner_sel': 'User Interface Radio Widget Inner Selected',
    'user_interface.wcol_radio.item': 'User Interface Radio Widget Item',
    'user_interface.wcol_radio.outline': 'User Interface Radio Widget Outline',
    'user_interface.wcol_radio.outline_sel': 'User Interface Radio Widget Outline Selected',
    'user_interface.wcol_radio.text': 'User Interface Radio Widget Text',
    'user_interface.wcol_radio.text_sel': 'User Interface Radio Widget Text Selected',
    'user_interface.wcol_regular.inner': 'User Interface Regular Widget Inner',
    'user_interface.wcol_regular.inner_sel': 'User Interface Regular Widget Inner Selected',
    'user_interface.wcol_regular.item': 'User Interface Regular Widget Item',
    'user_interface.wcol_regular.outline': 'User Interface Regular Widget Outline',
    'user_interface.wcol_regular.outline_sel': 'User Interface Regular Widget Outline Selected',
    'user_interface.wcol_regular.text': 'User Interface Regular Widget Text',
    'user_interface.wcol_regular.text_sel': 'User Interface Regular Widget Text Selected',
    'user_interface.wcol_scroll.inner': 'User Interface Scroll Widget Inner',
    'user_interface.wcol_scroll.inner_sel': 'User Interface Scroll Widget Inner Selected',
    'user_interface.wcol_scroll.item': 'User Interface Scroll Widget Item',
    'user_interface.wcol_scroll.outline': 'User Interface Scroll Widget Outline',
    'user_interface.wcol_scroll.outline_sel': 'User Interface Scroll Widget Outline Selected',
    'user_interface.wcol_scroll.text': 'User Interface Scroll Widget Text',
    'user_interface.wcol_scroll.text_sel': 'User Interface Scroll Widget Text Selected',
    'user_interface.wcol_state.error': 'User Interface State Error',
    'user_interface.wcol_state.info': 'User Interface State Info',
    'user_interface.wcol_state.inner_anim': 'User Interface State Inner Anim',
    'user_interface.wcol_state.inner_anim_sel': 'User Interface State Inner Anim Sel',
    'user_interface.wcol_state.inner_changed': 'User Interface State Inner Changed',
    'user_interface.wcol_state.inner_changed_sel': 'User Interface State Inner Changed Sel',
    'user_interface.wcol_state.inner_driven': 'User Interface State Inner Driven',
    'user_interface.wcol_state.inner_driven_sel': 'User Interface State Inner Driven Sel',
    'user_interface.wcol_state.inner_key': 'User Interface State Inner Key',
    'user_interface.wcol_state.inner_key_sel': 'User Interface State Inner Key Sel',
    'user_interface.wcol_state.inner_overridden': 'User Interface State Inner Overridden',
    'user_interface.wcol_state.inner_overridden_sel': 'User Interface State Inner Overridden Sel',
    'user_interface.wcol_state.success': 'User Interface State Success',
    'user_interface.wcol_state.warning': 'User Interface State Warning',
    'user_interface.wcol_tab.inner': 'User Interface Tab Inner',
    'user_interface.wcol_tab.inner_sel': 'User Interface Tab Inner Selected',
    'user_interface.wcol_tab.item': 'User Interface Tab Item',
    'user_interface.wcol_tab.outline': 'User Interface Tab Outline',
    'user_interface.wcol_tab.outline_sel': 'User Interface Tab Outline Selected',
    'user_interface.wcol_tab.text': 'User Interface Tab Text',
    'user_interface.wcol_tab.text_sel': 'User Interface Tab Text Selected',
    'user_interface.wcol_text.inner': 'User Interface Text Widget Inner',
    'user_interface.wcol_text.inner_sel': 'User Interface Text Widget Inner Selected',
    'user_interface.wcol_text.item': 'User Interface Text Widget Item',
    'user_interface.wcol_text.outline': 'User Interface Text Widget Outline',
    'user_interface.wcol_text.outline_sel': 'User Interface Text Widget Outline Selected',
    'user_interface.wcol_text.text': 'User Interface Text Widget Text',
    'user_interface.wcol_text.text_sel': 'User Interface Text Widget Text Selected',
    'user_interface.wcol_toggle.inner': 'User Interface Toggle Widget Inner',
    'user_interface.wcol_toggle.inner_sel': 'User Interface Toggle Widget Inner Selected',
    'user_interface.wcol_toggle.item': 'User Interface Toggle Widget Item',
    'user_interface.wcol_toggle.outline': 'User Interface Toggle Widget Outline',
    'user_interface.wcol_toggle.outline_sel': 'User Interface Toggle Widget Outline Selected',
    'user_interface.wcol_toggle.text': 'User Interface Toggle Widget Text',
    'user_interface.wcol_toggle.text_sel': 'User Interface Toggle Widget Text Selected',
    'user_interface.wcol_tool.inner': 'User Interface Tool Widget Inner',
    'user_interface.wcol_tool.inner_sel': 'User Interface Tool Widget Inner Selected',
    'user_interface.wcol_tool.item': 'User Interface Tool Widget Item',
    'user_interface.wcol_tool.outline': 'User Interface Tool Widget Outline',
    'user_interface.wcol_tool.outline_sel': 'User Interface Tool Widget Outline Selected',
    'user_interface.wcol_tool.text': 'User Interface Tool Widget Text',
    'user_interface.wcol_tool.text_sel': 'User Interface Tool Widget Text Selected',
    'user_interface.wcol_toolbar_item.inner': 'User Interface Toolbar Item Inner',
    'user_interface.wcol_toolbar_item.inner_sel': 'User Interface Toolbar Item Inner Selected',
    'user_interface.wcol_toolbar_item.item': 'User Interface Toolbar Item Item',
    'user_interface.wcol_toolbar_item.outline': 'User Interface Toolbar Item Outline',
    'user_interface.wcol_toolbar_item.outline_sel': 'User Interface Toolbar Item Outline Selected',
    'user_interface.wcol_toolbar_item.text': 'User Interface Toolbar Item Text',
    'user_interface.wcol_toolbar_item.text_sel': 'User Interface Toolbar Item Text Selected',
    'user_interface.wcol_tooltip.inner': 'User Interface Tooltip Inner',
    'user_interface.wcol_tooltip.inner_sel': 'User Interface Tooltip Inner Selected',
    'user_interface.wcol_tooltip.item': 'User Interface Tooltip Item',
    'user_interface.wcol_tooltip.outline': 'User Interface Tooltip Outline',
    'user_interface.wcol_tooltip.outline_sel': 'User Interface Tooltip Outline Selected',
    'user_interface.wcol_tooltip.text': 'User Interface Tooltip Text',
    'user_interface.wcol_tooltip.text_sel': 'User Interface Tooltip Text Selected',
    'user_interface.widget_emboss': 'User Interface Widget Emboss',
    'user_interface.widget_text_cursor': 'User Interface Text Cursor',
    'view_3d.after_current_frame': '3D View After Current Frame',
    'view_3d.before_current_frame': '3D View Before Current Frame',
    'view_3d.bevel': '3D View Bevel',
    'view_3d.bone_locked_weight': '3D View Bone Locked Weight',
    'view_3d.bone_pose': '3D View Bone Pose',
    'view_3d.bone_pose_active': '3D View Bone Pose Active',
    'view_3d.bone_solid': '3D View Bone Solid',
    'view_3d.bundle_solid': '3D View Bundle Solid',
    'view_3d.camera': '3D View Camera',
    'view_3d.camera_passepartout': '3D View Camera Passepartout',
    'view_3d.camera_path': '3D View Camera Path',
    'view_3d.clipping_border_3d': '3D View Clipping Border 3D',
    'view_3d.crease': '3D View Crease',
    'view_3d.edge_mode_select': '3D View Edge Mode Select',
    'view_3d.edge_select': '3D View Edge Select',
    'view_3d.editmesh_active': '3D View Editmesh Active',
    'view_3d.empty': '3D View Empty',
    'view_3d.extra_edge_angle': '3D View Extra Edge Angle',
    'view_3d.extra_edge_len': '3D View Extra Edge Len',
    'view_3d.extra_face_angle': '3D View Extra Face Angle',
    'view_3d.extra_face_area': '3D View Extra Face Area',
    'view_3d.face': '3D View Face',
    'view_3d.face_back': '3D View Face Back',
    'view_3d.face_front': '3D View Face Front',
    'view_3d.face_mode_select': '3D View Face Mode Select',
    'view_3d.face_retopology': '3D View Face Retopology',
    'view_3d.face_select': '3D View Face Select',
    'view_3d.freestyle': '3D View Freestyle',
    'view_3d.gp_vertex': '3D View Gp Vertex',
    'view_3d.gp_vertex_select': '3D View Gp Vertex Select',
    'view_3d.gp_wire_edit': '3D View Gp Wire Edit',
    'view_3d.grid': '3D View Grid',
    'view_3d.grid_major': '3D View Grid Major',
    'view_3d.light': '3D View Light',
    'view_3d.normal': '3D View Normal',
    'view_3d.nurb_sel_uline': '3D View Nurb Sel Uline',
    'view_3d.nurb_sel_vline': '3D View Nurb Sel Vline',
    'view_3d.nurb_uline': '3D View Nurb Uline',
    'view_3d.nurb_vline': '3D View Nurb Vline',
    'view_3d.object_active': '3D View Object Active',
    'view_3d.object_selected': '3D View Object Selected',
    'view_3d.seam': '3D View Seam',
    'view_3d.sharp': '3D View Sharp',
    'view_3d.skin_root': '3D View Skin Root',
    'view_3d.space.gradients.gradient': '3D View Space Gradients Gradient',
    'view_3d.space.gradients.high_gradient': '3D View Space Gradients High Gradient',
    'view_3d.space.header': '3D View Space Header',
    'view_3d.space.header_text': '3D View Space Header Text',
    'view_3d.space.header_text_hi': '3D View Space Header Text Hi',
    'view_3d.space.text': '3D View Space Text',
    'view_3d.space.text_hi': '3D View Space Text Hi',
    'view_3d.space.title': '3D View Space Title',
    'view_3d.speaker': '3D View Speaker',
    'view_3d.split_normal': '3D View Split Normal',
    'view_3d.text_grease_pencil': '3D View Text Grease Pencil',
    'view_3d.transform': '3D View Transform',
    'view_3d.vertex': '3D View Vertex',
    'view_3d.vertex_normal': '3D View Vertex Normal',
    'view_3d.vertex_select': '3D View Vertex Select',
    'view_3d.vertex_unreferenced': '3D View Vertex Unreferenced',
    'view_3d.view_overlay': '3D View View Overlay',
    'view_3d.wire': '3D View Wire',
    'view_3d.wire_edit': '3D View Wire Edit',
}


def english_theme_label(label, path):
    if path.endswith(".background_type"):
        return "Background Type"
    if path in THEME_PATH_LABELS_EN:
        return hierarchy_theme_label(path, THEME_PATH_LABELS_EN[path])
    tail = path.rsplit(".", 1)[-1]
    return hierarchy_theme_label(path, tail.replace("_", " ").title() if tail else label)


THEME_ROOT_LABELS = {
    "bone_color_sets": "Bone Color Sets",
    "clip_editor": "Clip Editor",
    "collection_color": "Collection Color",
    "common": "Common",
    "console": "Python Console",
    "dopesheet_editor": "Dope Sheet",
    "file_browser": "File Browser",
    "graph_editor": "Graph Editor",
    "image_editor": "Image Editor",
    "info": "Info",
    "nla_editor": "NLA Editor",
    "node_editor": "Node Editor",
    "outliner": "Outliner",
    "preferences": "Preferences",
    "properties": "Properties",
    "regions": "Regions",
    "sequence_editor": "Video Sequencer",
    "spreadsheet": "Spreadsheet",
    "statusbar": "Status Bar",
    "strip_color": "Strip Color",
    "text_editor": "Text Editor",
    "topbar": "Top Bar",
    "user_interface": "User Interface",
    "view_3d": "3D View",
}


THEME_FIELD_LABELS = {
    "back": "Background",
    "high_gradient": "High Gradient",
    "inner_sel": "Inner Selected",
    "outline_sel": "Outline Selected",
    "sub_back": "Sub Background",
    "text_hi": "Text Hi",
    "text_sel": "Text Selected",
}


def title_from_identifier(identifier):
    return THEME_FIELD_LABELS.get(identifier, identifier.replace("_", " ").title())


def translate_ui(text):
    if not text:
        return text
    try:
        return bpy.app.translations.pgettext_iface(text)
    except Exception:
        return text


def translate_zh_cn(text):
    if not text or translation is None:
        return text
    try:
        return translation.translations_dict.get("zh_CN", {}).get(("*", text), text)
    except Exception:
        return text


def hierarchy_theme_label(path, fallback_label):
    parts = path.split(".")
    if len(parts) < 2:
        return fallback_label

    labels = [THEME_ROOT_LABELS.get(parts[0], title_from_identifier(parts[0]))]
    for part in parts[1:]:
        if part.startswith("wcol_"):
            widget = title_from_identifier(part[5:])
            if widget not in {"State"}:
                widget = f"{widget} Widget"
            labels.append(widget)
        else:
            labels.append(title_from_identifier(part))
    return "> ".join(labels)


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


def changed_theme_paths(previous, current):
    if previous is None or current is None:
        return []
    paths = []
    for path in set(previous.keys()) | set(current.keys()):
        if previous.get(path) != current.get(path):
            paths.append(path)
    return paths


def consume_history_ignored_preview_paths(paths):
    ignored = [path for path in paths if path in _history_ignored_preview_paths]
    for path in ignored:
        _history_ignored_preview_paths.discard(path)
    return ignored


def state_without_paths(state, fallback_state, paths):
    if not paths or state is None:
        return state
    normalized = dict(state)
    for path in paths:
        if fallback_state is not None and path in fallback_state:
            normalized[path] = fallback_state[path]
        else:
            normalized.pop(path, None)
    return normalized


def record_edit_history_paths(paths, previous_state=None, current_state=None):
    for path in paths:
        if not path or path.endswith(".background_type") or not is_color_theme_path(path):
            continue
        previous = previous_state.get(path) if previous_state else None
        current = current_state.get(path) if current_state else None
        if candidate_preview_change_is_suppressed(path, previous, current):
            continue
        if path in _edit_history_paths:
            _edit_history_paths.remove(path)
        _edit_history_paths.insert(0, path)
        _candidate_preview_suppressed_values.pop(path, None)
    del _edit_history_paths[EDIT_HISTORY_LIMIT:]


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
    if not changed_count:
        _history_ignored_preview_paths.clear()
    if changed_count:
        manually_changed_paths = changed_theme_paths(_last_theme_state, current_state)
        ignored_preview_paths = consume_history_ignored_preview_paths(manually_changed_paths)
        if ignored_preview_paths:
            current_state = state_without_paths(current_state, _last_theme_state, ignored_preview_paths)
            manually_changed_paths = [path for path in manually_changed_paths if path not in ignored_preview_paths]
            changed_count = changed_value_count(_last_theme_state, current_state)
            if not changed_count:
                return HISTORY_TIMER_INTERVAL
        similar_sync_applied = False
        if not preview_state_active:
            current_state, similar_sync_applied = apply_similar_hsv_offset_from_change(bpy.context, _last_theme_state, current_state)
        changed_count = changed_value_count(_last_theme_state, current_state)
        if changed_count > max(24, len(current_state) // 4) and not similar_sync_applied:
            _clear_history_stacks()
            _clear_pending_history()
        else:
            if not preview_state_active:
                record_edit_history_paths(manually_changed_paths, _last_theme_state, current_state)
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


def remember_candidate_preview_value(path, color):
    if not path or color is None:
        return
    values = _candidate_preview_suppressed_values.setdefault(path, [])
    normalized = tuple(round(channel, 6) for channel in color)
    if not any(colors_close(normalized, value) for value in values):
        values.append(normalized)
        del values[:-8]


def reset_candidate_preview_values(path, original_color):
    if not path:
        return
    _candidate_preview_suppressed_values[path] = []
    remember_candidate_preview_value(path, original_color)


def candidate_preview_suppressed_color(path, color):
    if not path or color is None:
        return False
    return any(colors_close(color, value) for value in _candidate_preview_suppressed_values.get(path, []))


def candidate_preview_change_is_suppressed(path, previous, current):
    if path not in _candidate_preview_suppressed_values:
        return False
    return candidate_preview_suppressed_color(path, previous) or candidate_preview_suppressed_color(path, current)


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
        remember_candidate_preview_value(_candidate_preview_path, _candidate_preview_original)
        current = color_value_for_path(_candidate_preview_path)
        if _candidate_preview_last_written is None or colors_close(current, _candidate_preview_last_written):
            remember_candidate_preview_value(_candidate_preview_path, _candidate_preview_last_written)
            set_color_value_for_path_without_history(_candidate_preview_path, _candidate_preview_original, preview_operation=True)
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


def set_color_value_for_path_without_history(path, color, preview_operation=False):
    global _suspend_history
    if preview_operation and path:
        _history_ignored_preview_paths.add(path)
    was_suspended = _suspend_history
    _suspend_history = True
    try:
        return set_color_value_for_path(path, color)
    finally:
        _suspend_history = was_suspended


def normalized_candidate_preview_state(state):
    if state is None:
        return state
    normalized = None
    if _candidate_preview_path and _candidate_preview_original is not None and _candidate_preview_last_written is not None:
        current_value = state.get(_candidate_preview_path)
        if colors_close(current_value, _candidate_preview_last_written):
            normalized = dict(state)
            normalized[_candidate_preview_path] = tuple(round(channel, 6) for channel in _candidate_preview_original)
    for path, values in _candidate_preview_suppressed_values.items():
        current_value = (normalized or state).get(path)
        if not any(colors_close(current_value, value) for value in values[1:]):
            continue
        target = values[0]
        if normalized is None:
            normalized = dict(state)
        normalized[path] = target
    return normalized or state


def state_has_candidate_preview_value(state):
    if (
        state is None
        or not _candidate_preview_path
    ):
        return False
    current_value = state.get(_candidate_preview_path)
    if _candidate_preview_last_written is not None and colors_close(current_value, _candidate_preview_last_written):
        return True
    if candidate_preview_suppressed_color(_candidate_preview_path, current_value):
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
        reset_candidate_preview_values(path, _candidate_preview_original)
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
        remember_candidate_preview_value(_candidate_preview_path, _candidate_preview_original)
        remember_candidate_preview_value(_candidate_preview_path, preview_color)
        set_color_value_for_path_without_history(_candidate_preview_path, preview_color, preview_operation=True)
        _candidate_preview_last_written = color_value_for_path(_candidate_preview_path)
        remember_candidate_preview_value(_candidate_preview_path, _candidate_preview_last_written)
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


AREA_LABELS = {
    "TOPBAR": "Top Bar",
    "STATUSBAR": "Status Bar",
    "VIEW_3D": "3D View",
    "PROPERTIES": "Properties",
    "OUTLINER": "Outliner",
    "NODE_EDITOR": "Node Editor",
    "IMAGE_EDITOR": "Image Editor",
    "SEQUENCE_EDITOR": "Video Sequencer",
    "DOPESHEET_EDITOR": "Dope Sheet",
    "GRAPH_EDITOR": "Graph Editor",
    "NLA_EDITOR": "NLA Editor",
    "TEXT_EDITOR": "Text Editor",
    "CONSOLE": "Python Console",
    "INFO": "Info",
    "FILE_BROWSER": "File Browser",
    "PREFERENCES": "Preferences",
    "CLIP_EDITOR": "Clip Editor",
    "SPREADSHEET": "Spreadsheet",
}

REGION_LABELS = {
    "WINDOW": "Main Content",
    "HEADER": "Header",
    "TOOL_HEADER": "Tool Header",
    "UI": "N Panel",
    "TOOLS": "T Toolbar",
    "NAVIGATION_BAR": "Navigation Area",
    "HUD": "HUD",
    "CHANNELS": "Channels",
    "TEMPORARY": "Temporary Popup",
    "EXECUTE": "Operator Popup",
    "PREVIEW": "Preview",
    "MENU": "Menu",
    "FOOTER": "Footer",
    "TOOL_PROPS": "Tool Properties",
    "ASSET_SHELF": "Asset Shelf",
}

MODE_LABELS = {
    "OBJECT": "Object Mode",
    "EDIT_MESH": "Edit Mode - Mesh",
    "EDIT_CURVE": "Edit Mode - Curve",
    "EDIT_SURFACE": "Edit Mode - Surface",
    "EDIT_TEXT": "Edit Mode - Text",
    "EDIT_ARMATURE": "Edit Mode - Armature",
    "EDIT_METABALL": "Edit Mode - Metaball",
    "EDIT_LATTICE": "Edit Mode - Lattice",
    "POSE": "Pose Mode - Armature",
    "SCULPT": "Sculpt Mode",
    "PAINT_WEIGHT": "Weight Paint Mode",
    "PAINT_VERTEX": "Vertex Paint Mode",
    "PAINT_TEXTURE": "Texture Paint Mode",
    "PARTICLE": "Particle Edit Mode",
    "EDIT_GPENCIL": "Edit Mode - Grease Pencil",
    "PAINT_GPENCIL": "Draw Mode - Grease Pencil",
    "SCULPT_GPENCIL": "Sculpt Mode - Grease Pencil",
    "WEIGHT_GPENCIL": "Weight Paint Mode - Grease Pencil",
    "VERTEX_GPENCIL": "Vertex Paint Mode - Grease Pencil",
    "EDIT_GREASE_PENCIL": "Edit Mode - Grease Pencil",
    "PAINT_GREASE_PENCIL": "Draw Mode - Grease Pencil",
    "SCULPT_GREASE_PENCIL": "Sculpt Mode - Grease Pencil",
    "WEIGHT_GREASE_PENCIL": "Weight Paint Mode - Grease Pencil",
    "VERTEX_GREASE_PENCIL": "Vertex Paint Mode - Grease Pencil",
}

TRANSIENT_REGION_TYPES = {"MENU", "TEMPORARY", "EXECUTE", "HUD"}
GIZMO_CORNER_SIZE = 96

PROBE_GROUPS_BY_RESULT = {
    "Temporary Popup": ["MD_01"],
    "Menu": ["MD_01"],
    "Operator Popup": ["MD_01"],
    "HUD": ["MD_01"],
    "Top UI Area": ["TOP_BAR_AREA"],
    "Bottom Status/Screen Edge": ["STATUS_BAR_AREA"],
    "Area Separator / Screen Gap": ["SCREEN_BOUNDARY_AREA"],
    "Top Bar": ["TOP_BAR_AREA"],
    "Status Bar": ["STATUS_BAR_AREA"],
    "N Panel": ["MD_03"],
    "Sidebar": ["MD_03"],
    "T Toolbar": ["MD_04"],
    "Navigation Area": ["UI_NAVIGATION_AREA"],
    "Navigation/Gizmo Area": ["UI_NAVIGATION_AREA"],
    "3D View - Navigation/Gizmo Area": ["UI_NAVIGATION_AREA"],
    "3D View - Navigation Area": ["UI_NAVIGATION_AREA"],
    "3D View - Gizmo Area": ["VIEW_3D_GIZMO_AREA"],
    "3D View": ["MD_06"],
    "3D View - Main Content": ["MD_06"],
    "Sculpt Mode": ["MD_06"],
    "Weight Paint Mode": ["MD_06"],
    "Vertex Paint Mode": ["MD_06"],
    "Texture Paint Mode": ["MD_06"],
    "Particle Edit Mode": ["MD_06"],
    "Edit Mode - Mesh": ["MD_07"],
    "Edit Mode - Curve": ["MD_08"],
    "Edit Mode - Surface": ["MD_08"],
    "Edit Mode - Armature": ["MD_09"],
    "Pose Mode - Armature": ["MD_09"],
    "Edit Mode - Grease Pencil": ["MD_10"],
    "Draw Mode - Grease Pencil": ["MD_10"],
    "Sculpt Mode - Grease Pencil": ["MD_10"],
    "Weight Paint Mode - Grease Pencil": ["MD_10"],
    "Vertex Paint Mode - Grease Pencil": ["MD_10"],
    "Dope Sheet": ["MD_11"],
    "Graph Editor": ["MD_11"],
    "NLA Editor": ["MD_11"],
    "Node Editor": ["MD_12"],
    "Properties": ["MD_13"],
    "Outliner": ["MD_14"],
    "Image Editor": ["MD_15"],
    "Video Sequencer": ["MD_16"],
    "Text Editor": ["MD_17"],
    "Python Console": ["MD_17"],
    "Info": ["MD_17"],
    "File Browser": ["MD_17"],
    "Preferences": ["MD_17"],
    "Spreadsheet": ["MD_17"],
    "Clip Editor": ["MD_17"],
    "Asset Shelf": ["MD_18"],
    "Channels": ["MD_18"],
}


def label_for_area(area_type):
    return AREA_LABELS.get(area_type, area_type.replace("_", " ").title() if area_type else "Unknown Area")


def label_for_region(region_type, area_type=""):
    if area_type == "VIEW_3D" and region_type == "UI":
        return "N Panel"
    if area_type == "VIEW_3D" and region_type == "TOOLS":
        return "T Toolbar"
    return REGION_LABELS.get(region_type, region_type.replace("_", " ").title() if region_type else "No Region")


def point_inside_rect(x, y, left, bottom, width, height):
    return left <= x <= left + width and bottom <= y <= bottom + height


def region_rects(area, region):
    return (
        (region.x, region.y, region.width, region.height),
        (area.x + region.x, area.y + region.y, region.width, region.height),
    )


def preferred_region_rect(area, region, mouse_x=None, mouse_y=None):
    rects = region_rects(area, region)
    if mouse_x is not None and mouse_y is not None:
        for rect in rects:
            if point_inside_rect(mouse_x, mouse_y, *rect):
                return rect
    return rects[0]


def point_inside_region(area, region, x, y):
    return any(point_inside_rect(x, y, *rect) for rect in region_rects(area, region))


def region_priority(region):
    priorities = {
        "MENU": 0,
        "TEMPORARY": 1,
        "EXECUTE": 2,
        "HUD": 3,
        "HEADER": 4,
        "TOOL_HEADER": 5,
        "TOOLS": 6,
        "UI": 7,
        "NAVIGATION_BAR": 8,
        "ASSET_SHELF": 9,
        "WINDOW": 30,
    }
    return priorities.get(region.type, 15)


def find_area_region(screen, mouse_x, mouse_y):
    if screen is None:
        return None, None

    for area in screen.areas:
        if not point_inside_rect(mouse_x, mouse_y, area.x, area.y, area.width, area.height):
            continue

        matching_regions = []
        for region in area.regions:
            if region.width <= 1 or region.height <= 1:
                continue
            if point_inside_region(area, region, mouse_x, mouse_y):
                matching_regions.append(region)

        if matching_regions:
            matching_regions.sort(key=region_priority)
            return area, matching_regions[0]
        return area, None

    return None, None


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
    dx = max(area.x - mouse_x, 0, mouse_x - (area.x + area.width))
    dy = max(area.y - mouse_y, 0, mouse_y - (area.y + area.height))
    return dx + dy


def nearest_screen_area(screen, mouse_x, mouse_y):
    areas = list(getattr(screen, "areas", [])) if screen else []
    if not areas:
        return None
    return min(areas, key=lambda area: distance_to_area(area, mouse_x, mouse_y))


def boundary_edge_names(area, mouse_x, mouse_y):
    if area is None:
        return "", False
    distances = {
        "Left": abs(mouse_x - area.x),
        "Right": abs(mouse_x - (area.x + area.width)),
        "Bottom": abs(mouse_y - area.y),
        "Top": abs(mouse_y - (area.y + area.height)),
    }
    near = [name for name, distance in distances.items() if distance <= BOUNDARY_THRESHOLD]
    return ", ".join(near), bool(near)


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


def boundary_flags(area, mouse_x, mouse_y):
    if area is None:
        return {}
    edge_names, near_any = boundary_edge_names(area, mouse_x, mouse_y)
    return {
        "left": "Left" in edge_names,
        "right": "Right" in edge_names,
        "bottom": "Bottom" in edge_names,
        "top": "Top" in edge_names,
        "near_any": near_any,
    }


def outside_main_area_probe(screen, area, mouse_x, mouse_y):
    bounds = screen_area_bounds(screen)
    if bounds is None:
        return None

    if area is None:
        near = nearest_screen_area(screen, mouse_x, mouse_y)
        nearest_label = label_for_area(near.type) if near else "None"
        if mouse_y >= bounds["top"]:
            return {"title": "Top UI Area", "area": area, "region": None, "boundary": True, "nearest_area": nearest_label}
        if mouse_y <= bounds["bottom"]:
            return {"title": "Bottom Status/Screen Edge", "area": area, "region": None, "boundary": True, "nearest_area": nearest_label}
        return {"title": "Area Separator / Screen Gap", "area": area, "region": None, "boundary": True, "nearest_area": nearest_label}

    if area.type == "TOPBAR":
        return {"title": "Top Bar", "area": area, "region": None, "boundary": False, "nearest_area": label_for_area(area.type)}
    if area.type == "STATUSBAR":
        return {"title": "Status Bar", "area": area, "region": None, "boundary": False, "nearest_area": label_for_area(area.type)}

    edge_names, near_edge = boundary_edge_names(area, mouse_x, mouse_y)
    if near_edge:
        return {
            "title": f"{label_for_area(area.type)} Boundary",
            "area": area,
            "region": None,
            "boundary": True,
            "nearest_area": label_for_area(area.type),
        }
    return None


def transient_context_probe(context, mouse_x, mouse_y):
    area = getattr(context, "area", None)
    region = getattr(context, "region", None)
    if area is None or region is None or region.type not in TRANSIENT_REGION_TYPES:
        return None
    return {
        "title": label_for_region(region.type, area.type),
        "area": area,
        "region": region,
        "area_type": area.type,
        "region_type": region.type,
        "boundary": False,
        "inferred": False,
    }


def is_view3d_gizmo_corner(area, region, mouse_x, mouse_y):
    if area is None or region is None or area.type != "VIEW_3D" or region.type != "WINDOW":
        return False

    content_right = area.x + area.width
    content_top = area.y + area.height
    for item in area.regions:
        item_left, item_bottom, _item_width, _item_height = preferred_region_rect(area, item)
        if item.type in {"UI", "TOOLS"} and item.width > 1 and item_left > area.x + area.width * 0.5:
            content_right = min(content_right, item_left)
        if item.type in {"HEADER", "TOOL_HEADER"} and item.height > 1 and item_bottom > area.y + area.height * 0.5:
            content_top = min(content_top, item_bottom)
    return mouse_x >= content_right - GIZMO_CORNER_SIZE and mouse_y >= content_top - GIZMO_CORNER_SIZE


def view3d_navigation_zone(area, region, mouse_x, mouse_y):
    if area is None or region is None or area.type != "VIEW_3D":
        return ""

    if region.type == "NAVIGATION_BAR":
        nav_left, nav_bottom, nav_width, nav_height = preferred_region_rect(area, region, mouse_x, mouse_y)
        nav_top = nav_bottom + nav_height
        if mouse_y >= nav_top - min(GIZMO_CORNER_SIZE, nav_height * 0.45):
            return "3D View - Gizmo Area"
        return "3D View - Navigation Area"

    if is_view3d_gizmo_corner(area, region, mouse_x, mouse_y):
        return "3D View - Gizmo Area"

    return ""


def active_state_label(context):
    mode = getattr(context, "mode", "") or "OBJECT"
    return MODE_LABELS.get(mode, mode.replace("_", " ").title())


def is_special_state(context):
    return (getattr(context, "mode", "") or "OBJECT") != "OBJECT"


def location_probe(context, mouse_x, mouse_y):
    transient = transient_context_probe(context, mouse_x, mouse_y)
    if transient:
        return transient

    screen = getattr(context, "screen", None)
    area, region = find_area_region(screen, mouse_x, mouse_y)
    outside = outside_main_area_probe(screen, area, mouse_x, mouse_y)
    if outside:
        outside["area_type"] = area.type if area else "SCREEN"
        outside["region_type"] = region.type if region else ""
        return outside

    if area is None:
        return {"title": "Unknown Screen Position", "area": None, "region": None, "area_type": "SCREEN", "region_type": "", "boundary": False}

    area_type = area.type
    region_type = region.type if region else ""
    region_label = label_for_region(region_type, area_type) if region else "No Region"
    title = f"{label_for_area(area_type)} - {region_label}" if region_type else label_for_area(area_type)
    inferred = False

    navigation_zone = view3d_navigation_zone(area, region, mouse_x, mouse_y)
    if navigation_zone:
        title = navigation_zone
        inferred = region_type != "NAVIGATION_BAR"
    elif is_view3d_gizmo_corner(area, region, mouse_x, mouse_y):
        title = "3D View - Navigation/Gizmo Area"
        inferred = True

    return {
        "title": title,
        "area": area,
        "region": region,
        "area_type": area_type,
        "region_type": region_type,
        "boundary": False,
        "inferred": inferred,
    }


def highest_priority_probe(context, mouse_x, mouse_y):
    transient = transient_context_probe(context, mouse_x, mouse_y)
    if transient:
        return transient

    screen = getattr(context, "screen", None)
    area, region = find_area_region(screen, mouse_x, mouse_y)
    outside = outside_main_area_probe(screen, area, mouse_x, mouse_y)
    if outside:
        outside["area_type"] = area.type if area else "SCREEN"
        outside["region_type"] = region.type if region else ""
        return outside

    if is_special_state(context):
        return {
            "title": active_state_label(context),
            "area": area,
            "region": region,
            "area_type": area.type if area else "SCREEN",
            "region_type": region.type if region else "",
            "boundary": False,
            "inferred": False,
        }

    return location_probe(context, mouse_x, mouse_y)


def classify_probe_zone(screen, area, region, mouse_x, mouse_y):
    probe = location_probe(bpy.context, mouse_x, mouse_y)
    return probe.get("title", "Unknown")


def display_zone_label(zone):
    return zone or "Unknown"


def classify_fallback_zone(screen, mouse_x, mouse_y, nearest_area):
    outside = outside_main_area_probe(screen, None, mouse_x, mouse_y)
    return outside.get("title", "Screenshot Lookup Area") if outside else "Screenshot Lookup Area"


def fallback_preferred_groups(zone, nearest_area):
    groups = list(PROBE_GROUPS_BY_RESULT.get(zone, []))
    if nearest_area is not None:
        groups.extend(PROBE_GROUPS_BY_RESULT.get(label_for_area(nearest_area.type), []))
    seen = set()
    groups = [group for group in groups if not (group in seen or seen.add(group))]
    return groups or ["MD_02"]


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
    theme_index = build_theme_index()
    search_paths = preferred_paths or sorted(theme_index.keys())
    matches = []
    for path in search_paths:
        value = theme_index.get(path)
        if value is None:
            continue
        signature = color_signature(value)
        distance = visual_color_distance(signature, seed_signature)
        if distance is None or distance > FALLBACK_MATCH_TOLERANCE:
            continue
        matches.append({
            "label": semantic_label_for_path(path),
            "path": path,
            "distance": distance,
            "rank": preferred_index.get(path, len(preferred_index)),
        })
    matches.sort(key=lambda item: (item["distance"], item["rank"], item["path"]))
    return matches[:FALLBACK_MATCH_LIMIT]


def groups_for_probe(probe):
    title = probe.get("title", "")
    groups = list(PROBE_GROUPS_BY_RESULT.get(title, []))
    if title.endswith(" Boundary"):
        groups.extend(PROBE_GROUPS_BY_RESULT.get("Area Separator / Screen Gap", []))
    if not groups:
        region_type = probe.get("region_type", "")
        area_type = probe.get("area_type", "")
        if region_type:
            groups.extend(PROBE_GROUPS_BY_RESULT.get(label_for_region(region_type, area_type), []))
        if area_type:
            groups.extend(PROBE_GROUPS_BY_RESULT.get(label_for_area(area_type), []))
    seen = set()
    return [group for group in groups if not (group in seen or seen.add(group))]


def area_candidate_allowed(group, index, path, probe):
    linked_count = SEMANTIC_LINKED_COUNTS.get(group, 0)
    title = probe.get("title", "")
    region_type = probe.get("region_type", "")

    def has_any(terms):
        return any(term in path for term in terms)

    def prefix_any(prefixes):
        return any(path.startswith(prefix) for prefix in prefixes)

    if region_type == "NAVIGATION_BAR" or title in {"Navigation Area", "3D View - Navigation Area", "Properties - Navigation Area"}:
        navigation_extra_paths = {
            "regions.sidebars.tab_back",
            "user_interface.panel_back",
            "user_interface.panel_header",
            "user_interface.panel_outline",
            "user_interface.panel_sub_back",
            "user_interface.panel_text",
            "user_interface.panel_title",
            "user_interface.wcol_num.inner",
            "user_interface.wcol_option.inner",
            "user_interface.wcol_option.inner_sel",
            "user_interface.wcol_option.outline",
        }
        return group == "UI_NAVIGATION_AREA" and (
            path in navigation_extra_paths
            or has_any(("icon_", "wcol_tab", "wcol_tool", "wcol_toolbar_item"))
        )

    if region_type in {"HEADER", "TOOL_HEADER"} and group not in {"UI_NAVIGATION_AREA", "TOP_BAR_AREA", "STATUS_BAR_AREA"}:
        return (
            ".space.header" in path
            or path.endswith(".space.text")
            or path.endswith(".space.text_hi")
            or path.endswith(".space.title")
        )

    if title in {"Temporary Popup", "Menu", "Operator Popup", "HUD"}:
        return path.startswith("user_interface.") and has_any((
            "wcol_menu",
            "wcol_menu_back",
            "wcol_menu_item",
            "wcol_pie_menu",
            "wcol_pulldown",
            "wcol_tooltip",
            "wcol_curve.inner_sel",
            "wcol_curve.item",
            "wcol_curve.outline",
            "wcol_curve.outline_sel",
            "wcol_curve.text",
            "wcol_curve.text_sel",
            "wcol_num",
            "wcol_numslider",
            "wcol_option",
            "wcol_text",
            "wcol_toggle",
            "wcol_regular",
            "wcol_state",
            "widget_",
        ))

    if title in {"Top UI Area", "Top Bar"}:
        return path.startswith("topbar.space.")

    if title in {"Bottom Status/Screen Edge", "Status Bar"}:
        return path.startswith("statusbar.space.")

    if title == "Area Separator / Screen Gap" or title.endswith(" Boundary"):
        return path in {
            "user_interface.editor_border",
            "user_interface.editor_outline",
            "user_interface.editor_outline_active",
        }

    if title in {"N Panel", "Sidebar"}:
        return (
            path.startswith("regions.sidebars.")
            or (
                path.startswith("user_interface.")
                and has_any((
                    "panel_",
                    "wcol_box",
                    "wcol_list_item",
                    "wcol_scroll",
                    "wcol_tab",
                    "wcol_num",
                    "wcol_numslider",
                    "wcol_option",
                    "wcol_progress",
                    "wcol_radio",
                    "wcol_text",
                    "wcol_toggle",
                ))
            )
        )

    if title == "T Toolbar":
        return path.startswith("user_interface.") and has_any(("wcol_tool", "wcol_toolbar_item", "icon_"))

    if title == "3D View - Gizmo Area":
        return path.startswith("user_interface.") and has_any(("axis_", "gizmo"))

    if group == "MD_06" and title in {
        "3D View - Main Content",
        "Sculpt Mode",
        "Weight Paint Mode",
        "Vertex Paint Mode",
        "Texture Paint Mode",
        "Particle Edit Mode",
    }:
        return path.startswith("view_3d.") and not has_any((
            "space.header",
            "space.text",
            "space.title",
            "gizmo",
            "axis_",
        ))

    if title in {
        "Edit Mode - Mesh",
        "Edit Mode - Curve",
        "Edit Mode - Surface",
        "Edit Mode - Armature",
        "Pose Mode - Armature",
        "Edit Mode - Grease Pencil",
        "Draw Mode - Grease Pencil",
        "Sculpt Mode - Grease Pencil",
        "Weight Paint Mode - Grease Pencil",
        "Vertex Paint Mode - Grease Pencil",
    }:
        return index < linked_count and not prefix_any(("topbar.", "statusbar.", "properties.", "node_editor."))

    if title in {"Dope Sheet", "Graph Editor", "NLA Editor"}:
        return (
            prefix_any(("dopesheet_editor.", "graph_editor.", "nla_editor."))
            or path.startswith("common.anim")
            or path.startswith("regions.channels.")
            or path.startswith("regions.scrubbing.")
            or (
                path.startswith("user_interface.")
                and has_any(("wcol_num", "wcol_text", "wcol_scroll"))
            )
        )

    if title == "Node Editor":
        return (
            path.startswith("node_editor.")
            or (
                path.startswith("user_interface.")
                and has_any(("wcol_box", "wcol_curve", "wcol_num", "wcol_progress", "wcol_radio", "wcol_text", "wcol_toggle", "wcol_state"))
            )
        )

    if title in {"Properties", "Properties - Main Content"}:
        return (
            path.startswith("properties.")
            or (
                path.startswith("user_interface.")
                and has_any(("icon_", "wcol_box", "wcol_num", "wcol_numslider", "wcol_option", "wcol_progress", "wcol_radio", "wcol_text", "wcol_toggle", "panel_"))
            )
        )

    if title == "Outliner":
        return (
            path.startswith("outliner.")
            or path.startswith("collection_color[")
            or (
                path.startswith("user_interface.")
                and has_any(("icon_", "wcol_list_item", "wcol_scroll"))
            )
        )

    if title == "Image Editor":
        return (
            path.startswith("image_editor.")
            or "transparent_checker" in path
            or (
                path.startswith("user_interface.")
                and has_any(("wcol_box", "wcol_curve", "wcol_num", "wcol_text", "wcol_toggle"))
            )
        )

    if title == "Video Sequencer":
        return (
            path.startswith("sequence_editor.")
            or path.startswith("strip_color[")
            or path in {
                "user_interface.wcol_option.inner",
                "user_interface.wcol_option.inner_sel",
                "user_interface.wcol_option.text",
            }
            or (
                path.startswith("user_interface.")
                and has_any(("wcol_curve", "wcol_num", "wcol_text", "wcol_scroll"))
            )
        )

    editor_prefixes = {
        "Text Editor": ("text_editor.",),
        "Python Console": ("console.",),
        "Info": ("info.",),
        "File Browser": ("file_browser.",),
        "Preferences": ("preferences.",),
        "Spreadsheet": ("spreadsheet.",),
        "Clip Editor": ("clip_editor.",),
    }
    if title in editor_prefixes:
        return (
            prefix_any(editor_prefixes[title])
            or (
                path.startswith("user_interface.")
                and has_any(("icon_", "wcol_box", "wcol_num", "wcol_text", "wcol_scroll"))
            )
        )

    if title in {"Asset Shelf", "Channels"}:
        return path.startswith(("regions.asset_shelf.", "regions.channels.", "regions.scrubbing."))

    if index < linked_count:
        return True
    if group == "UI_NAVIGATION_AREA":
        return True

    if (
        region_type in {"NAVIGATION_BAR", "HEADER", "TOOL_HEADER"}
        or title in {"Top UI Area", "Bottom Status/Screen Edge", "Area Separator / Screen Gap"}
        or title.endswith(" Boundary")
    ):
        return False
    if group == "MD_06":
        return False
    return True


def collect_candidates(area, region):
    theme_index = build_theme_index()
    probe = _probe_runtime.get("probe", {})
    groups = groups_for_probe(probe)

    candidates = []
    seen = set()
    for group in groups:
        linked_count = SEMANTIC_LINKED_COUNTS.get(group, 0)
        for index, (label_text, path) in enumerate(SEMANTIC_MAP.get(group, [])):
            if not area_candidate_allowed(group, index, path, probe):
                continue
            if path not in theme_index or path in seen:
                continue
            seen.add(path)
            section = "LINKED" if index < linked_count else "COMMON"
            candidates.append({"label": label_text, "path": path, "section": section})

    if not candidates:
        for path in sorted(theme_index.keys())[:20]:
            candidates.append({"label": semantic_label_for_path(path), "path": path, "section": "LINKED"})
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


def collect_edit_history_candidates():
    candidates = []
    for path in _edit_history_paths[:EDIT_HISTORY_LIMIT]:
        if is_color_theme_path(path):
            candidates.append({"label": semantic_label_for_path(path), "path": path})
    return candidates


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
    mode = getattr(wm, "theme_probe_mode", "AREA")
    if mode == "SIMILAR":
        tolerance = getattr(wm, "theme_probe_tolerance", SIMILAR_TOLERANCE_DEFAULT)
        return collect_similar_candidates(_similar_seed_signature, tolerance)
    if mode == "EDIT_HISTORY":
        return collect_edit_history_candidates()
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
    probe = highest_priority_probe(context, mouse_x, mouse_y)
    area = probe.get("area")
    region = probe.get("region")
    if area is None:
        sample_color = sample_screen_color(context, mouse_x, mouse_y)
        nearest_area = nearest_screen_area(context.screen, mouse_x, mouse_y)
        zone = probe.get("title") or classify_fallback_zone(context.screen, mouse_x, mouse_y, nearest_area)
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
        _probe_runtime["probe"] = probe
        return True

    _probe_runtime.clear()
    _probe_runtime["area_type"] = probe.get("area_type", area.type)
    _probe_runtime["region_type"] = probe.get("region_type", region.type if region else "")
    _probe_runtime["zone"] = probe.get("title", "")
    _probe_runtime["boundary"] = boundary_flags(area, mouse_x, mouse_y)
    _probe_runtime["probe"] = probe
    _probe_runtime["candidates"] = collect_candidates(area, region)
    return True


def candidate_section_label(section):
    if section == "LINKED":
        return "Linked Item"
    if section == "COMMON":
        return "Common Properties"
    return ""


def add_candidate_section_heading(collection, section):
    label_text = candidate_section_label(section)
    if not label_text:
        return
    entry = collection.add()
    entry.name = label_text
    entry.label = label_text
    entry.path = ""
    entry.section = section
    entry.number = 0


def candidate_section_for_group(group, candidate_section_by_path):
    for item in group["colors"]:
        section = candidate_section_by_path.get(item["path"])
        if section:
            return section
    return "LINKED"


def populate_candidate_collection(context, candidates=None):
    wm = context.window_manager
    collection = getattr(wm, "theme_probe_candidates", None)
    if collection is None:
        return
    if candidates is None:
        candidates = active_probe_candidates(context)
    collection.clear()
    candidate_paths = {item["path"] for item in candidates}
    mode = getattr(wm, "theme_probe_mode", "AREA")
    show_sections = mode == "AREA"
    group_candidate_paths = candidate_paths if show_sections else set()
    label_by_path = {item["path"]: item["label"] for item in candidates}
    section_by_path = {item["path"]: item.get("section", "LINKED") for item in candidates}
    grouped_paths = set()
    current_section = ""
    number = 1
    for group in build_mode_color_groups():
        group_color_paths = {item["path"] for item in group["colors"]}
        if not group_candidate_paths.intersection(group_color_paths):
            continue
        section = candidate_section_for_group(group, section_by_path)
        if show_sections and section != current_section:
            add_candidate_section_heading(collection, section)
            current_section = section
        for item in group["enums"] + group["colors"]:
            if resolve_theme_path(item["path"])[0] is None:
                continue
            entry = collection.add()
            label_text = label_by_path.get(item["path"]) or ("Background Type" if item["path"].endswith(".background_type") else item["label"])
            label_text = english_theme_label(label_text, item["path"])
            entry.name = label_text
            entry.label = label_text
            entry.path = item["path"]
            entry.section = section
            entry.number = number
            number += 1
        grouped_paths.update(group_color_paths)

    for item in candidates:
        if item["path"] in grouped_paths:
            continue
        if mode in {"SIMILAR", "EDIT_HISTORY"} and not is_color_theme_path(item["path"]):
            continue
        section = item.get("section", "LINKED")
        if show_sections and section != current_section:
            add_candidate_section_heading(collection, section)
            current_section = section
        entry = collection.add()
        label_text = english_theme_label(item["label"], item["path"])
        entry.name = label_text
        entry.label = label_text
        entry.path = item["path"]
        entry.section = section
        entry.number = number
        number += 1
    restore_candidate_preview()
    first_candidate_index = next((index for index, item in enumerate(collection) if item.path), -1)
    wm.theme_probe_candidate_index = first_candidate_index
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


def default_theme_preset_dir():
    return bpy.utils.user_resource("SCRIPTS", path=os.path.join("presets", "interface_theme"), create=True)


def current_theme_filepath():
    root = theme_root()
    if root is None:
        return ""
    return getattr(root, "filepath", "") or ""


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
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return
    km = kc.keymaps.new(name="Window", space_type="EMPTY")
    kmi = km.keymap_items.new(
        THEMEPROBE_OT_probe.bl_idname,
        "C",
        "PRESS",
        alt=True,
        ctrl=False,
        shift=False,
    )
    addon_keymaps.append((km, kmi))


def theme_probe_keymap_item(context):
    keyconfigs = getattr(context.window_manager, "keyconfigs", None) if context else None
    for kc in (getattr(keyconfigs, "user", None), getattr(keyconfigs, "addon", None)):
        if kc is None:
            continue
        km = kc.keymaps.get("Window")
        if km is None:
            continue
        for kmi in km.keymap_items:
            if kmi.idname == THEMEPROBE_OT_probe.bl_idname:
                return kc, km, kmi
    return None, None, None


def update_shortcut_map_type(self, context):
    _kc, _km, kmi = theme_probe_keymap_item(context)
    if kmi is None:
        sync_keymaps()
        _kc, _km, kmi = theme_probe_keymap_item(context)
    if kmi is not None:
        kmi.map_type = self.shortcut_map_type


class THEMEPROBE_OT_probe(Operator):
    bl_idname = "theme_probe.probe"
    bl_label = "Theme Dictionary"
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
        layout.label(text=translate_ui(self.label_text or "Color"))
        layout.label(text=self.theme_path)
        if owner is None:
            layout.label(text=translate_ui("This color field does not exist in the current Blender version."), icon="ERROR")
            return
        box = layout.box()
        box.use_property_split = True
        box.prop(owner, attr, text=translate_ui("Color"))

    def cancel(self, context):
        tag_redraw_all()


class THEMEPROBE_OT_restore_session(Operator):
    bl_idname = "theme_probe.restore_session"
    bl_label = "Reset Current Theme"
    bl_description = "Reset the current theme to the latest saved snapshot"

    def execute(self, context):
        if restore_snapshot():
            self.report({"INFO"}, "Current theme reset")
            return {"FINISHED"}
        self.report({"WARNING"}, "No session snapshot available")
        return {"CANCELLED"}


class THEMEPROBE_OT_undo_theme_change(Operator):
    bl_idname = "theme_probe.undo_theme_change"
    bl_label = "Undo Theme Change"
    bl_description = "Undo the last theme change recorded by Theme Dictionary"

    def execute(self, context):
        if undo_theme_change():
            self.report({"INFO"}, "Theme Probe change undone")
            return {"FINISHED"}
        self.report({"WARNING"}, "No Theme Probe change history")
        return {"CANCELLED"}


class THEMEPROBE_OT_redo_theme_change(Operator):
    bl_idname = "theme_probe.redo_theme_change"
    bl_label = "Redo Theme Change"
    bl_description = "Redo the last undone theme change recorded by Theme Dictionary"

    def execute(self, context):
        if redo_theme_change():
            self.report({"INFO"}, "Theme Probe change redone")
            return {"FINISHED"}
        self.report({"WARNING"}, "No Theme Probe redo history")
        return {"CANCELLED"}


class THEMEPROBE_OT_open_theme_folder(Operator):
    bl_idname = "theme_probe.open_theme_folder"
    bl_label = "Open Theme Folder"
    bl_description = "Open Blender's interface_theme preset folder"

    def execute(self, context):
        folder = open_theme_preset_folder()
        self.report({"INFO"}, f"Opened {folder}")
        return {"FINISHED"}


class THEMEPROBE_OT_pick_probe_target(Operator):
    bl_idname = "theme_probe.pick_probe_target"
    bl_label = "Pick Probe Target"
    bl_description = "Pick a UI area or sample color for probing"

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
    bl_label = "Toggle Candidate Selection"
    bl_description = "Select or deselect this color candidate"

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
    bl_label = "Toggle Candidate Lock"
    bl_description = "Lock or unlock this similar color candidate"

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
    bl_label = "Unlock All"
    bl_description = "Clear every locked state in the Theme Dictionary list"

    def execute(self, context):
        _locked_candidate_paths.clear()
        tag_redraw_all()
        return {"FINISHED"}


class THEMEPROBE_CandidateItem(PropertyGroup):
    label: StringProperty()
    path: StringProperty()
    section: StringProperty()
    number: IntProperty()


class THEMEPROBE_UL_candidates(UIList):
    bl_idname = "THEMEPROBE_UL_candidates"

    def filter_items(self, context, data, propname):
        self.use_filter_show = True
        items = getattr(data, propname)
        if not items:
            return [], []

        pattern = (self.filter_name or "").casefold()
        flags = []
        if pattern:
            bitflag = self.bitflag_filter_item
            flags = bpy.types.UI_UL_list.filter_items_by_name(
                self.filter_name,
                bitflag,
                items,
                "name",
                reverse=self.use_filter_invert,
            )
            if not flags:
                flags = [0] * len(items)

            for index, item in enumerate(items):
                search_parts = [
                    translate_ui(getattr(item, "label", "")),
                    translate_zh_cn(getattr(item, "label", "")),
                    getattr(item, "path", ""),
                ]
                search_text = " ".join(part for part in search_parts if part).casefold()
                supplemental_match = pattern in search_text
                if self.use_filter_invert:
                    official_match = not bool(flags[index] & bitflag)
                    flags[index] = 0 if (official_match or supplemental_match) else bitflag
                elif supplemental_match:
                    flags[index] |= bitflag

            for index, item in enumerate(items):
                if getattr(item, "path", ""):
                    continue
                if flags[index]:
                    continue
                previous_match = index + 1 < len(flags) and bool(flags[index + 1] & bitflag)
                next_match = index > 0 and bool(flags[index - 1] & bitflag)
                if previous_match or next_match:
                    flags[index] = bitflag
        else:
            flags = [self.bitflag_filter_item] * len(items)

        new_order = []
        if self.use_filter_sort_alpha:
            new_order = bpy.types.UI_UL_list.sort_items_by_name(items, "name")
            if self.use_filter_sort_reverse:
                max_index = len(new_order) - 1
                new_order = [max_index - index for index in new_order]
        return flags, new_order

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        self.use_filter_show = True
        if not item.path:
            row = layout.row(align=True)
            row.enabled = False
            row.alignment = "LEFT"
            row.label(text=translate_ui(item.label))
            return
        owner, attr = resolve_theme_path(item.path)
        row = layout.row(align=False)
        if owner is None:
            row.label(text=f"{item.number}. {translate_ui(item.label)}", icon="ERROR")
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
            text=translate_ui(item.label),
            emboss=False,
        )
        select_op.index = index
        color_part = split.row(align=False)
        color_part.prop(owner, attr, text="")


class THEMEPROBE_OT_show_candidates(Operator):
    bl_idname = "theme_probe.show_candidates"
    bl_label = "Theme Dictionary Candidates"
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
        width = getattr(wm, "theme_probe_popup_width", POPUP_WIDTH)

        header = layout.row(align=True)
        header.operator(THEMEPROBE_OT_pick_probe_target.bl_idname, text="", icon="EYEDROPPER")
        if wm.theme_probe_mode == "SIMILAR":
            title = color_hex(_similar_seed_signature) or "No Sample"
        elif wm.theme_probe_mode == "EDIT_HISTORY":
            title = "Edit History"
        elif zone:
            title = display_zone_label(zone)
        else:
            title = f"{area_type} / {region_type or 'NONE'}"
        if wm.theme_probe_mode == "SIMILAR":
            sample_factor = max(0.22, min(0.84, 178.0 / max(float(width), 1.0)))
            sample_split = header.split(factor=sample_factor, align=True)
            sample_row = sample_split.row(align=True)
            sample_width = max(float(width) * sample_factor, 1.0)
            label_target = 68.0 if width > 400 else 78.0
            label_factor = max(0.38, min(0.72, label_target / sample_width))
            compact_sample = sample_row.split(factor=label_factor, align=True)
            compact_sample.label(text=translate_ui(title))
            swatch = compact_sample.row(align=True)
            swatch.scale_x = 0.42
            swatch.prop(wm, "theme_probe_sample_color", text="")
            folder_row = sample_split.row(align=True)
            folder_row.alignment = "RIGHT"
            folder_row.operator(THEMEPROBE_OT_open_theme_folder.bl_idname, text="", icon="FILE_FOLDER")
        else:
            header.label(text=translate_ui(title))
            header.operator(THEMEPROBE_OT_open_theme_folder.bl_idname, text="", icon="FILE_FOLDER")
        if boundary.get("near_any"):
            layout.label(text=translate_ui("Near Boundary"), icon="MOD_EDGESPLIT")

        layout.prop(wm, "theme_probe_mode", text="Mode")
        controls = layout.row(align=True)
        controls.prop(wm, "theme_probe_popup_width", text="Width")
        tolerance_row = controls.row(align=True)
        tolerance_row.enabled = wm.theme_probe_mode == "SIMILAR"
        tolerance_row.prop(wm, "theme_probe_tolerance", text="Tolerance", slider=True)
        if wm.theme_probe_mode == "SIMILAR":
            tools_row = layout.row(align=True)
            unlock_row = tools_row.row(align=True)
            unlock_row.operator(THEMEPROBE_OT_unlock_all_candidates.bl_idname, text="Unlock All", icon="UNLOCKED")
            sync_row = tools_row.row(align=True)
            sync_row.alignment = "RIGHT"
            sync_row.label(text="Sync Changes")
            sync_row.prop(wm, "theme_probe_sync_similar", text="")
        layout.separator()

        if not wm.theme_probe_candidates:
            layout.label(text=translate_ui("No available candidates found"), icon="INFO")

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
        if hasattr(bpy.ops.wm, "interface_theme_preset_save"):
            preset_row.operator("wm.interface_theme_preset_save", text="", icon="FILE_TICK")
        else:
            preset_row.label(text=translate_ui("Use Blender native presets"), icon="INFO")

        footer = layout.row(align=True)
        footer.scale_y = 1.05
        footer.operator(
            THEMEPROBE_OT_restore_session.bl_idname,
            text="Reset Current Theme",
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

    shortcut_map_type: EnumProperty(
        name="Shortcut Input",
        description="Choose whether the panel shortcut uses keyboard or mouse input",
        items=SHORTCUT_MAP_TYPES,
        default="KEYBOARD",
        update=update_shortcut_map_type,
    )

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.43, align=True)
        assist_row = split.row(align=True)
        assist_row.label(text="Use shortcut to bring up the panel in blender")
        shortcut_row = split.row(align=True)
        shortcut_row.alignment = "RIGHT"
        _kc, _km, kmi = theme_probe_keymap_item(context)
        if kmi is None:
            sync_keymaps()
            _kc, _km, kmi = theme_probe_keymap_item(context)
        if kmi is None:
            shortcut_row.label(text="Shortcut not found. Please restart Blender.", icon="ERROR")
            return
        if kmi.map_type != self.shortcut_map_type:
            kmi.map_type = self.shortcut_map_type
        shortcut_row.prop(kmi, "active", text="", emboss=False)
        shortcut_row.label(text="pannel shortcut")
        shortcut_row.separator(factor=2.5)
        shortcut_row.prop(self, "shortcut_map_type", text="")
        event_row = shortcut_row.row(align=True)
        event_row.scale_x = 0.67
        if kmi.map_type in {"KEYBOARD", "MOUSE"}:
            event_row.prop(kmi, "type", text="", full_event=True)
        else:
            kmi.map_type = self.shortcut_map_type
            event_row.prop(kmi, "type", text="", full_event=True)


ThemeProbeOperator = THEMEPROBE_OT_probe
ThemeProbePopup = THEMEPROBE_OT_show_candidates
ThemeProbePreferences = THEMEPROBE_Preferences


classes = (
    THEMEPROBE_OT_probe,
    THEMEPROBE_OT_edit_color,
    THEMEPROBE_OT_restore_session,
    THEMEPROBE_OT_undo_theme_change,
    THEMEPROBE_OT_redo_theme_change,
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
    if translation is not None:
        try:
            bpy.app.translations.unregister(ADDON_ID)
        except Exception:
            pass
        bpy.app.translations.register(ADDON_ID, translation.translations_dict)
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.theme_probe_candidates = CollectionProperty(type=THEMEPROBE_CandidateItem)
    bpy.types.WindowManager.theme_probe_candidate_index = IntProperty(default=0, min=-1, update=update_candidate_index)
    bpy.types.WindowManager.theme_probe_candidate_preview_index = IntProperty(default=-1, min=-1)
    bpy.types.WindowManager.theme_probe_mode = EnumProperty(
        name="",
        description="Choose how Theme Dictionary searches for candidate colors",
        items=PROBE_MODE_ITEMS,
        default="AREA",
        update=update_probe_list_settings,
    )
    bpy.types.WindowManager.theme_probe_tolerance = IntProperty(
        name="Tolerance",
        default=SIMILAR_TOLERANCE_DEFAULT,
        min=0,
        max=255,
        description="Set the tolerance for similar color search",
        update=update_probe_list_settings,
    )
    bpy.types.WindowManager.theme_probe_sync_similar = BoolProperty(
        name="Sync Changes",
        description="Sync edits to all unlocked similar color candidates",
        default=True,
    )
    bpy.types.WindowManager.theme_probe_popup_width = IntProperty(
        name="Popup Width",
        default=POPUP_WIDTH,
        min=160,
        max=720,
        description="Reopen the panel after changing this width",
    )
    bpy.types.WindowManager.theme_probe_sample_color = FloatVectorProperty(
        name="Sample Color",
        description="Sample color used for similar color search",
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
    if translation is not None:
        try:
            bpy.app.translations.unregister(ADDON_ID)
        except Exception:
            pass


if __name__ == "__main__":
    register()
