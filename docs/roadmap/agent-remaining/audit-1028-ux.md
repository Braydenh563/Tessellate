# Audit 1028: whiteboard, mind map, documents, code editor (UX create)

Driven in Chromium/Playwright, 1440x900 and 390x844, light and dark, server on 8796. Findings only.

| id | severity | lens | surface | finding | measurement | selector or file:line | fix | effort |
|---|---|---|---|---|---|---|---|---|
| U1 | High | WCAG | Board dark | Stored black ink does not remap per theme, near-invisible on dark canvas | #000000 on rgb(30,30,28) = 1.26:1 (need 3:1 non-text/4.5 text) | board stroke/text colour | Remap ink by theme at render, or store a 'default ink' token | M |
| U2 | High | WCAG | Board dark | Default white ink on yellow sticky is unreadable | white on rgb(255,244,163) = 1.12:1 | sticky text colour | Pick sticky text colour from fill luminance | S |
| U3 | High | UX | Board | Insert > Sticky note by keyboard adds no object and drops focus to BODY | objects 1 to 1; activeElement BODY | #wb-insert menu .wb-menu-item (Sticky note) | Keyboard-activated tool items should arm the tool and keep focus on canvas | M |
| U4 | High | WCAG | Mind map | Reparent has no discovered non-drag path in keys list | Keys panel lists no reparent key; drag worked (parent 22 to 23) | Keys panel (?), topic menu | Add 'Move under...' to topic menu / Cut-paste documented (WCAG 2.5.7) | M |
| U5 | High | WCAG | Mind map | Ring/chevron buttons shrink under zoom below 24px | 28x28 at 100%, 21.7x21.7 at fit 77%, 10.1x10.1 phone fit; .wb-map-count 4.6px | button.wb-map-collapse and ring buttons | Counter-scale controls or enforce min 24px hit area (::before) | M |
| U6 | High | UX | Code editor | Code editor undiscoverable: not under New | Only via 32px icon-only #doc-new-template or More > file type; 6 inputs from Library | #doc-new-template, #doc-file-type | Add 'Code file' to Library New menu and label the template button | S |
| U7 | High | Polish | Code editor | Code text is proportional, not monospace | font-family system-ui, 14.72px on .cm-line, .cm-content, gutter | div.cm-content, .cm-gutters | Set monospace stack for code file types | S |
| U8 | High | UX | Doc phone | New doc opens in Read mode on phone; first tap on screen does nothing | aria-pressed true on Read; +1 tap to Edit | doc mode segment | Open new empty docs in Edit | S |
| U9 | High | WCAG | Doc find | Find/replace panel is unstyled CodeMirror default with tiny close | close button 9.8x22.1px; checkboxes 28px with 11.776px labels; buttons radius 2.4px | div.cm-search, button[aria-label=close] | Restyle with design tokens; 24px min close; add match count | M |
| U10 | High | UX | Doc | Image menu inserts a bare stub with no picker or upload | inserts ![image](https://); 0 dialogs | Insert (links/images) > Image | Open a file picker or paste hint; keep stub as fallback | M |
| U11 | Med | UX | Doc | Two menus both named Insert with different contents | Block menu: 6 items; links menu: 3 items (Link, Image, Numbered list) | doc dock summary.doc-dock-menu-btn | Rename second ('Links and media') and move Numbered list to the block menu | S |
| U12 | Med | Learn | Board | Insert menu hides key hints for most tools | Sticky hint reads 'click' not N; Rectangle R, Circle O, Arrow A, Connector have none | #wb-insert .wb-menu-item | Show kbd hints on every item that has a key | S |
| U13 | Med | UX | Board | Two buttons labelled Library | #wb-add-note 'Library' and #wb-side-tab-library | #wb-add-note | Rename first to 'Add from library' or 'Add note' | S |
| U14 | Med | UX | Board | Delete tool sits 2px from Undo/Redo | gap 2px in dock | dock delete/undo buttons | Separate with divider, gap >= 8px | S |
| U15 | Med | UX | Board | Arrange menu is 23 items, ~780px tall, 10px from viewport bottom at 900px | 23 x 36px; Insert 589, Board 622, View 427px | Arrange .wb-menu-panel | Group into submenus / ensure max-height with scroll; at 768px high likely clipped (not verified, script timed out) | M |
| U16 | Med | WCAG | Board | Side tabs below comfortable size | 28x28 (passes 24 minimum, fails 44 phone-parity) | #wb-side-tab-* | Raise to 32px | S |
| U17 | Med | WCAG | Board dark | Object grip glyph low contrast | ⠿ 1.87:1 at 12px | div.wb-object-grip | Use text-muted token that passes 3:1 | S |
| U18 | Med | Perf | Board | Long tasks up to 225ms on board interactions | undo click 118ms; board list open 208ms | undo, #wb-board-select list | Profile and defer thumbnails/layout | M |
| U19 | Med | Perf | Mind map | Long tasks on sibling add | 229ms typical, 509ms max under load | map sibling add (Enter) | Batch layout recompute with rAF | M |
| U20 | Med | Perf | Code editor | Long task opening file | 305ms | doc open | Lazy-init minimap and highlighters | M |
| U21 | Med | UX | Board phone | Tools sheet items are icon-only with no labels | sheet from #wb-tools-opener (90x44); toast covers 'Connect' heading | tools sheet | Add text labels; keep toast out of sheet | S |
| U22 | Med | UX | Board phone | Header is 104px tall and title clipped | barBottom 178; title scrollWidth 237 vs clientWidth 178 | #wb-board-select / title | Collapse to one row; ellipsis with full name in tooltip | M |
| U23 | Med | UX | Mind map phone | Map not panned to new node; title select shows 39 of 229px | root centre x=-297px | map viewport, map title select | Pan to new/selected node; widen title | M |
| U24 | Med | UX | Mind map | Newest node sits 5px from canvas right edge, radial layout unfit until fit | 5px margin | map canvas | Auto-fit or pan after layout change | S |
| U25 | Med | Polish | Mind map | Collapse chevrons overlap node edges and connector dots | observed in 1440 screenshots | button.wb-map-collapse | Offset chevron outside node bounds | S |
| U26 | Med | UX | Mind map | Template strip clipped at right edge ('Caus...') | 28 tiles 88x77; dismiss button 28x28 | map template strip | Add scroll affordance (fade/arrows); 32px dismiss | S |
| U27 | Med | UX | Mind map | Layout menu: 10 text-only options, 34.5px tall | 2 clicks | layout menu | Add preview icons | M |
| U28 | Med | Learn | Mind map | Font size stepper shows '22px' for root vs 'M' for others | mixed units | size stepper | Use a single scale (S/M/L) or all px | S |
| U29 | Med | UX | Documents | Two 'New document' buttons on empty state | 28px primary in header, 32px ghost in empty state | Documents header / empty state | Keep one; make sizes match | S |
| U30 | Med | Polish | Documents | Editor toolbar heights inconsistent | Edit/Read segment 28px vs 32px buttons | doc toolbar | Align to 32px | S |
| U31 | Med | UX | Documents | Formatting toolbar hidden by default; visibility persists as a pref | needs 1 extra click; my click toggled it off | Formatting button | Show by default on first use; add label state | S |
| U32 | Med | UX | Documents | Export is 3 clicks deep, in a 15-item More menu | More > Download or print > format | doc More menu | Promote Export to dock or top of More | S |
| U33 | Med | UX | Documents | New-document prompt lacks heading or placeholder; label ends with colon | observed | new doc title prompt | Add heading and placeholder; drop colon | S |
| U34 | Med | UX | Code editor | Titled blank creation first leaves a stray empty .md doc | extra doc created before template | template flow | Create the document only after template is chosen | M |
| U35 | Med | WCAG | Doc | Small targets in list and header | doc-crumb 22.8px high; #doc-suggest-mode 32x18.4; #doc-counts 16.8; .card-open 22.1; library search inputs 20.4px | those selectors | Raise to >= 24px (WCAG 2.5.8) | S |
| U36 | Med | WCAG | Doc dark | Low contrast labels | span.doc-ai-label 4.49:1; menu-submenu-arrow 4.2:1 | span.doc-ai-label, .menu-submenu-arrow | Darken/lighten to >= 4.5:1 | S |
| U37 | Med | WCAG | Code editor | Run disabled text contrast | 2.82:1 dark (disabled exempt, but reason link is 254px beside it) | Run button | Keep reason link at full contrast | S |
| U38 | Low | UX | Documents | Duplicate document titles allowed silently | observed | doc create | Warn or auto-suffix | S |
| U39 | Low | Polish | Documents | Template dialog check mark overlaps description on selected item | observed | #doc-new-template dialog | Reserve padding for the check | S |
| U40 | Low | Polish | Board | Empty-board thumbnail shows mind-map-like placeholder | observed in boards list | boards list thumbnail | Use a neutral blank-board placeholder | S |
| U41 | Low | UX | Board | New-board toast persists; map toast is 3 lines and stacks with '+1 more' | observed | toast | Auto-dismiss at ~4s, shorten text | S |
| U42 | Low | Consist | Spacing | Off-scale spacing values | #library-boards-filter margin-bottom 12px; i.ph-tree-structure margin-right 4.83px | those selectors | Use --space tokens | S |
| U43 | Low | Consist | Radius | Off-scale radius | input.library-card-tick and input.doc-list-tick 3.2px; find panel 2.4px | those selectors | Use radius tokens | S |
| U44 | Low | Consist | Type | Off-scale font size | find-panel labels 11.776px | div.cm-search label | Use 12px token | S |
| U45 | Low | Consist | Type | Board distinct sizes | 11.2/12/13.6/14.72px (+16); radii 4.8/6.4/8/999/50%/2.4px | board surface | Acceptable; 2.4px is the stray | S |
| U46 | Low | WCAG | Board | Hidden native select is 1px wide | #wb-board-select 1px | #wb-board-select | Intentional (hidden); ensure aria-hidden or visible replacement | S |
| U47 | Low | Copy | All | Copy rules | 0 em-dashes, 0 exclamation marks, 0 'Oops' found in scan | n/a | None (pass) | - |
| U48 | Low | UX | Board | Export default scope is 'On screen' with '(view)' in filename | observed | export dialog | Default to whole board for first-time users | S |
| U49 | Low | WCAG | Board | Board toolbar has 33 tab stops; canvas is stop 10 | tab order | board toolbar | Add roving tabindex in toolbars | M |
| U50 | Pass | WCAG | Board | Focus ring consistent | 2px solid #2f5bd3 on all stops | focus-visible | None | - |
| U51 | Pass | WCAG | Board | Icon-only buttons all have names; help targets resolve | 126 data-help-for, all resolve | n/a | None | - |
| U52 | Pass | UX | Board | Core tasks are short | new board 2, sticky 3, rect 2, arrow 2, group 1 (Ctrl+G), undo/redo/fit 1, align 2, export PNG 3 (2816x1574, 1133ms) | n/a | None | - |
| U53 | Pass | WCAG | All | No horizontal overflow at 390; no console/page errors | scrollWidth 390 | n/a | None | - |
| U54 | Pass | WCAG | Code editor | Syntax colour contrast | 6.5-17:1 light, 8.8-14:1 dark; gutter 5.91 / 7.96 | n/a | None | - |

## Could not verify
- Shape picker contents and keyboard-only shape placement.
- Branch submenu; whether Cut/paste serves as keyboard reparent.
- Document drag and drop.
- Real AI paths, error and offline states (fake transport only).
- Arrange menu at 768px height and docs-list font/radius sweep: final script timed out.
- File:line locations: selectors only, repo source mostly not traced.
