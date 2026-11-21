"""No raw read of a stored file outside `sealed_files` (L-world-class-52 review).

A private space's recordings, library uploads and note files are sealed on
disk, so a reader handed the raw path reads ciphertext: an OCR pass, a
caption, a chat picture or a bundle would get garbage, or worse send it on.
Every function that names the uploads, media or recordings folder is listed
here by what it does with it. A new one fails until it is placed, and one in
`THROUGH` must itself call `sealed_files` or `downloads.unsealed`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "tessellate"

FOLDER = re.compile(
    r"media_dir\b|uploads_dir\b|recordings\.path_of\(|recordings\.directory\(|/\s*\"(?:media|uploads|recordings)\""
)
SEALED_CALL = re.compile(r"\bsealed_files\.|\bunsealed\(|\bsealed_aware\(")

#: Reads, writes or checks the bytes through `sealed_files` (or the route
#: helper `downloads.unsealed`, 423 locked and 409 damaged), or skips a
#: sealed file because it has no key (a background pass).
THROUGH = {
    "ai/docreader.py::_read_and_store",
    "api/app.py::_sweep_sealed_leftovers",
    "api/chat_attach.py::_attached_files",
    "api/chat_attach.py::_attached_media_files",
    "api/chat_attach.py::_attachment_readings",
    "api/chat_request.py::_caption_of",
    "api/chat_request.py::_resolve_chat_images",
    "api/routes_files.py::analyse_attachment",
    "api/routes_files.py::attached_file_html_preview",
    "api/routes_files.py::attached_file_pdf_info",
    "api/routes_files.py::attached_file_pdf_unlock",
    "api/routes_files.py::attached_file_pdf_page",
    "api/routes_files.py::attached_file_text",
    "api/routes_files.py::caption_media",
    "api/routes_files.py::download_file",
    "api/routes_files.py::get_media",
    "api/routes_files.py::media_text",
    "api/routes_files.py::ocr_media",
    "api/routes_files.py::save_attached_file_text",
    "api/routes_files.py::upload_file",
    "api/routes_files.py::upload_media",
    "api/routes_files_ocr.py::attachment_ocr_regions",
    "api/routes_files_ocr.py::media_ocr_regions",
    "api/routes_files_readings.py::attachment_ocr_page_read",
    "api/routes_files_readings.py::attachment_ocr_range_read",
    "api/routes_files_readings.py::attachment_page_caption",
    "api/routes_files_readings.py::media_ocr_page_read",
    "api/routes_files_readings.py::media_ocr_range_read",
    "api/routes_files_readings.py::media_page_caption",
    "api/routes_files_readings.py::vision_ocr_media",
    "api/routes_recordings.py::_append",
    "api/routes_recordings.py::recording_audio",
    "api/routes_recordings.py::transcribe_recording",
    "core/docexport.py::bundle",
    "core/media_process.py::process_committed_upload",
    "entry/export_folder.py::_write_note",
    "entry/sync_extras.py::file_bytes",
}

#: Hands the folder or a path in it to a function above (or to one that
#: refuses a sealed file with a 409), and reads nothing itself.
HANDS_ON = {
    "api/chat_attach.py::_picture_sizes": "core/imagesize reads the header through sealed_files",
    "api/chat_request.py::_image_caption_context": "_caption_of unseals or skips",
    "api/routes_captions.py::_keep_audio": "_seal_if_private seals the kept WAV",
    "api/routes_board_library.py::_process_pasted_images": "media_process skips a sealed file",
    "api/routes_conversations.py::_process_committed_media": "media_process skips a sealed file",
    "api/routes_documents.py::_process_committed_media": "media_process skips a sealed file",
    "api/routes_documents.py::export_bundle": "docexport.bundle reads through sealed_files",
    "api/routes_entries.py::_process_committed_media": "media_process skips a sealed file",
    "api/routes_files.py::_media_upload_path": "its callers open the path with unsealed",
    "api/routes_files.py::save_media_to_library": "media_process skips a sealed file",
    "api/routes_import.py::export_notebook_folder": "export_folder writes sealed files through sealed_files",
    "api/routes_recordings.py::label_speakers_by_voice": "_label_in_background reads through sealed_files.for_background",
    "api/routes_recordings.py::start_transcription": "_transcribe_in_background reads through sealed_files.for_background",
    "api/wb_items.py::create_object": "media_process skips a sealed file",
    "core/media_process.py::process_committed_upload_ids": "process_committed_upload skips a sealed file",
    "core/media_process.py::process_referenced_uploads": "process_committed_upload skips a sealed file",
    "entry/export_folder.py::export": "_write_note reads through sealed_files",
    "entry/export_folder.py::note_record": "_attachment_record hashes with _sha1_file, sealed-aware",
    "entry/export_folder.py::snapshot": "note_record, as above",
    "entry/export_folder.py::_attachment_record": "_sha1_file hashes the plain bytes of a sealed file",
    "entry/private_space.py::file_of": "the path seal_space_members and unseal_space_members rewrite",
    "entry/sync_extras.py::items": "file_state hashes for change detection; a sealed space's file is listed with no state",
    "entry/sync_extras.py::manifest": "as items",
    "entry/sync_pull.py::_round": "the folder apply_segment writes arrivals to",
}

#: Names, sizes on disk, deletes, moves or folders; no bytes are read.
PATHS_ONLY = {
    "ai/captions.py::_sweep_spools": "deletes stale live-caption spools",
    "api/app.py::_purge_expired_bin_entries": "deletes",
    "api/routes_entries.py::purge_entry": "deletes",
    "api/routes_files.py::_attachment_size": "size on disk",
    "api/routes_files.py::_media_size": "size on disk",
    "api/routes_files.py::clean_orphaned_media": "deletes",
    "api/routes_files.py::delete_file": "moves to the bin",
    "api/routes_files.py::delete_media": "moves to the bin",
    "api/routes_files.py::list_media": "size on disk",
    "api/routes_files.py::restore_file": "moves back",
    "api/routes_files.py::restore_media": "moves back",
    "api/routes_settings.py::empty_recycle_bin": "deletes",
    "api/routes_spaces.py::_purge_collect": "paths unlinked after the commit",
    "core/config.py::__init__": "makes the folder",
    "core/media_gc.py::delete_orphaned_media": "deletes",
    "core/recordings.py::directory": "the folder",
    "core/selfcheck.py::missing_files": "names only",
    "entry/manager_purge.py::_delete_attachments_and_vectors": "deletes",
    "entry/manager_purge.py::_detach_board_contents": "deletes",
    "entry/manager_purge.py::_forget_board_thumbs": "deletes",
    "entry/manager_purge.py::_hard_delete": "deletes",
    "entry/manager_purge.py::_upload_path": "the path to delete",
    "entry/manager_purge.py::delete_attachment": "deletes",
    "entry/manager_purge.py::empty_recycle_bin": "deletes",
    "entry/manager_purge.py::purge_entries": "deletes",
    "entry/manager_purge.py::purge_expired_deleted": "deletes",
    "entry/sync_extras_apply.py::board": "withdraws (deletes)",
    "entry/sync_extras_apply.py::remove_file": "deletes",
    "entry/sync_segments.py::withdraw": "deletes",
}

#: Writes plain bytes from a thread or an import that has no key; the next
#: unlock seals them (`private_space.seal_space_members` from `_open_spaces`).
PLAIN_WRITES = {
    "ai/captions.py::begin": "the live-caption PCM spool, removed when the take ends (L-world-class-670)",
    "core/recording_make.py::save_generated": "a background thread's WAV",
    "entry/export_folder.py::write": "an import",
    "entry/export_folder.py::_write_attachments": "an import",
    "entry/sync_extras_apply.py::file": "a file from the other computer, never a sealed space's",
    "api/routes_import.py::import_app": "an import",
}


def _sites() -> dict[str, str]:
    """`file::function` -> its source, for every function naming a stored-file folder."""
    found: dict[str, str] = {}
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if rel == "core/sealed_files.py":
            continue
        text = path.read_text(encoding="utf-8")
        if not FOLDER.search(text):
            continue
        lines = text.splitlines()
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            inner = set()
            for sub in ast.walk(node):
                if sub is not node and isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    inner.update(range(sub.lineno, sub.end_lineno + 1))
            own = [
                lines[n - 1]
                for n in range(node.lineno, node.end_lineno + 1)
                if n not in inner and not lines[n - 1].lstrip().startswith(("#", '"', "'"))
            ]
            if any(FOLDER.search(line) for line in own):
                found[f"{rel}::{node.name}"] = "\n".join(own)
    return found


def test_every_function_that_names_a_stored_file_folder_is_placed():
    placed = THROUGH | set(HANDS_ON) | set(PATHS_ONLY) | set(PLAIN_WRITES)
    sites = _sites()
    unplaced = sorted(set(sites) - placed)
    assert not unplaced, (
        "these name the uploads, media or recordings folder: read through "
        f"sealed_files (or downloads.unsealed) and list them here: {unplaced}"
    )
    stale = sorted(placed - set(sites))
    assert not stale, f"listed but no longer naming a stored-file folder: {stale}"


def test_a_reader_listed_as_through_calls_sealed_files_itself():
    sites = _sites()
    raw = sorted(name for name in THROUGH if name in sites and not SEALED_CALL.search(sites[name]))
    assert not raw, f"listed as reading through sealed_files but do not call it: {raw}"


def test_the_groups_do_not_overlap():
    groups = [THROUGH, set(HANDS_ON), set(PATHS_ONLY), set(PLAIN_WRITES)]
    seen: set[str] = set()
    for group in groups:
        assert not seen & group, sorted(seen & group)
        seen |= group
