# devsize-1011: sizes per device (INBOX 897)

Decision (saved looks): zoom, text size and density are NOT part of a saved look. A look is colours; LOOK_KEYS drops DEVICE_ONLY_KEYS and applySavedTheme skips them in older saves. Radius stays in the look (a shape, not a size on this screen).
Finding: avatar-buddy-size and nm-buddy-spots were never in the mirror (only zoom, fontsize, density, chat-composer-height, wb-panel-pos-* were); all are pinned device-only now.

done: f8597d361 (code, tests, help, sweep). INBOX 897 resolved. next: nothing; companion-size menu has no on-device label (menu only, row has it).
