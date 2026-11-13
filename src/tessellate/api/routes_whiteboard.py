"""Whiteboard: note cards and freehand sketches placed on a canvas.

A "board" is itself a note (`board_id` points at an entry), so a board is
something you can search, tag and file like anything else in the notebook, 
and `board_id = NULL` is the one unnamed scratch board every notebook starts
with.

Two rules run through all of it, both learned by their absence in the first
version:

- **A node has to point at a note that exists.** Nothing validated `entry_id`,
  so a card could be created for note 9999 and the board would then fail to
  render for good, with no way to remove the card from the UI.
- **A write has to be scoped to the board it claims.** `PUT`/`DELETE` took an
  id and nothing else, so any node on any board could be moved or deleted by
  guessing a number: and `PUT` silently ignored `board_id`, so "move this
  card to that board" quietly did nothing at all.

Layers, in import order (each imports only those above it; this module
imports them all and re-exports every name that anything else reads):

1. `wb_model`: limits, kinds, layouts, and the models and state helpers for
   comments, nodes, sketches and objects.
2. `wb_board`: a board as a whole (lookups, state route, settings, theme,
   layers, background, the board models).
3. `wb_preview`: the library card, its cache, and the thumbnail routes.
4. `wb_boards`: list, images, create, duplicate, rename.
5. `wb_items`: node, sketch and object routes.
6. `wb_tree`: a map's tree, references and styling.
7. `wb_export`: the map writers and the export route.
8. `wb_import`: the map readers and the placing of what they read.
9. `wb_map`: a map's node routes.
10. `wb_make`: a map proposed, generated or imported.

Each layer holds its own `APIRouter`; the routers are included below in the
order their routes had in this file, so every URL and operation id and the
route order are unchanged.
"""

from __future__ import annotations

from fastapi import APIRouter

from tessellate.api.wb_model import BOARD_LAYOUTS, Layer, MAP_APP_DEFAULT_PINS, MAP_LEVEL_FIELDS, MAP_REFERENCE_KINDS, MAP_THEME_FIELDS, MAP_TOPIC_KIND, MAX_SKETCH_CHARS, MEDIA_URL_RE, WhiteboardObjectBase, WhiteboardObjectData, WhiteboardSketchIn, _clamp, _is_one_emoji, _object_to_out, _require_object_data  # noqa: F401  (moved; re-exported)
from tessellate.api.wb_board import BOARD_BG_COLOR_RE, BoardBackground, BoardOut, _board_filter, _board_settings, _clean_levels, _clean_theme, _drop_orphan_links, _forget_links_to, _on_current_layer, _require_board, _store_board_background, _store_board_settings, _store_board_theme, _themed_style  # noqa: F401  (moved; re-exported)
from tessellate.api import wb_board
from tessellate.api.wb_preview import MAP_BRANCH_PALETTE, MAP_BRANCH_PALETTES, PREVIEW_ASPECT_RANGE, PREVIEW_CACHE_STATS, PREVIEW_POINTS, _map_branch_colors, _preview_fields, _preview_items, _preview_points, _sketch_preview, _thumb_writable, media_router, put_thumbnail  # noqa: F401  (moved; re-exported)
from tessellate.api import wb_preview
from tessellate.api.wb_boards import create_board, duplicate_board, list_boards, rename_board  # noqa: F401  (moved; re-exported)
from tessellate.api import wb_binds, wb_boards
from tessellate.api.wb_items import create_node, create_object, create_sketch, delete_node, delete_object, delete_sketch, update_node, update_object, update_sketch  # noqa: F401  (moved; re-exported)
from tessellate.api import wb_items
from tessellate.api.wb_tree import MAP_COL, MAP_ROW, MAX_IMPORT_DEPTH, MAX_MAP_DEPTH, _build_tree, _map_objects, _reference_label  # noqa: F401  (moved; re-exported)
from tessellate.api.wb_export import _export_freemind, _export_markdown, _export_opml, export_board  # noqa: F401  (moved; re-exported)
from tessellate.api import wb_export
from tessellate.api.wb_import import MAX_XMIND_JSON_BYTES, _clean_import_style, _parse_markdown_outline, _parse_xml_document, _place_map_nodes, _restore_import_links  # noqa: F401  (moved; re-exported)
from tessellate.api.wb_map import _is_descendant, _next_position, create_map_node, move_map_node, move_map_nodes  # noqa: F401  (moved; re-exported)
from tessellate.api import wb_map
from tessellate.api.wb_make import _record_map_creation, generate_map, import_board, propose_map  # noqa: F401  (moved; re-exported)
from tessellate.api import wb_make

router = APIRouter(prefix="/whiteboard", tags=["whiteboard"])
for _layer in (wb_board, wb_preview, wb_boards, wb_items, wb_map, wb_export, wb_make, wb_binds):
    router.include_router(_layer.router)
