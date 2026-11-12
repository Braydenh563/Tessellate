BEGIN TRANSACTION;
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO "alembic_version" VALUES('8a8a14407cc0');
CREATE TABLE ask_turns (
	id INTEGER NOT NULL, 
	question TEXT NOT NULL, 
	answer TEXT NOT NULL, 
	raw_result_ids TEXT NOT NULL, 
	search_mode VARCHAR(40) NOT NULL, 
	when_phrase VARCHAR(120) NOT NULL, 
	match_info TEXT NOT NULL, 
	connected_ids TEXT NOT NULL, 
	pinned BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	workspace_id VARCHAR DEFAULT 'default' NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE attachments (
	id INTEGER NOT NULL, 
	entry_id INTEGER NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	stored_name VARCHAR(80) NOT NULL, 
	mime VARCHAR(100) NOT NULL, 
	size INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	caption TEXT, 
	caption_model VARCHAR(200), 
	caption_edited BOOLEAN NOT NULL, 
	ocr_text TEXT, 
	vision_ocr_text TEXT, 
	vision_ocr_model VARCHAR(200), 
	workspace_id VARCHAR DEFAULT 'default' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(entry_id) REFERENCES entries (id), 
	UNIQUE (stored_name)
);
CREATE TABLE audit_log (
	id INTEGER NOT NULL, 
	action VARCHAR(50) NOT NULL, 
	entity_type VARCHAR(50) NOT NULL, 
	entity_id INTEGER, 
	detail TEXT, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
INSERT INTO "audit_log" VALUES(1,'created','entry',1,'first note','2026-08-01 10:00:00');
CREATE TABLE bookmarks (
	id INTEGER NOT NULL, 
	url VARCHAR(2000) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	note TEXT NOT NULL, 
	pinned BOOLEAN NOT NULL, 
	group_name VARCHAR(120) NOT NULL, 
	created_at DATETIME NOT NULL, 
	workspace_id VARCHAR DEFAULT 'default' NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE categories (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	created_at DATETIME NOT NULL, 
	workspace_id VARCHAR DEFAULT 'default' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_categories_workspace_name UNIQUE (workspace_id, name)
);
INSERT INTO "categories" VALUES(1,'Travel','trips','2026-08-01 10:00:00','default');
CREATE TABLE conversations (
	id INTEGER NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	messages TEXT NOT NULL, 
	pinned BOOLEAN NOT NULL, 
	archived_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	workspace_id VARCHAR DEFAULT 'default' NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE document_ai_edits (
	id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	verb VARCHAR(10) NOT NULL, 
	instruction VARCHAR(500) NOT NULL, 
	selection_excerpt VARCHAR(200) NOT NULL, 
	before_content TEXT NOT NULL, 
	after_content TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id)
);
CREATE TABLE document_bookmarks (
	id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	bookmark_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(bookmark_id) REFERENCES bookmarks (id)
);
CREATE TABLE document_links (
	id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	entry_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id), 
	FOREIGN KEY(entry_id) REFERENCES entries (id)
);
CREATE TABLE document_revisions (
	id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	content TEXT NOT NULL, 
	source VARCHAR(10) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(document_id) REFERENCES documents (id)
);
CREATE TABLE documents (
	id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	content TEXT NOT NULL, 
	file_type VARCHAR(20) NOT NULL, 
	archived_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	workspace_id VARCHAR DEFAULT 'default' NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE embeddings (
	id INTEGER NOT NULL, 
	entry_id INTEGER NOT NULL, 
	embedding BLOB NOT NULL, 
	dim INTEGER NOT NULL, 
	model_version VARCHAR(200) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (entry_id), 
	FOREIGN KEY(entry_id) REFERENCES entries (id)
);
CREATE TABLE entities (
	id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE entity_mentions (
	id INTEGER NOT NULL, 
	entity_id INTEGER NOT NULL, 
	entry_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(entity_id) REFERENCES entities (id), 
	FOREIGN KEY(entry_id) REFERENCES entries (id)
);
CREATE TABLE entries (
	id INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	category_id INTEGER, 
	tags TEXT NOT NULL, 
	ai_confidence INTEGER NOT NULL, 
	filing_state VARCHAR(10) NOT NULL, 
	filing_similar_id INTEGER, 
	access_count INTEGER NOT NULL, 
	parent_id INTEGER, 
	pinned BOOLEAN NOT NULL, 
	user_filed BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	is_deleted BOOLEAN NOT NULL, 
	archived_at DATETIME, 
	is_private BOOLEAN NOT NULL, 
	deleted_at DATETIME, 
	entities_extracted_at DATETIME, 
	is_draft BOOLEAN NOT NULL, 
	source_url VARCHAR(2000), 
	source_title VARCHAR(300), 
	is_board BOOLEAN NOT NULL, 
	board_settings TEXT, 
	source_path VARCHAR(500) NOT NULL, 
	graph_pin_x FLOAT, 
	graph_pin_y FLOAT, 
	workspace_id VARCHAR DEFAULT 'default' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(category_id) REFERENCES categories (id), 
	FOREIGN KEY(parent_id) REFERENCES entries (id)
);
INSERT INTO "entries" VALUES(1,'Book the ferry to Hvar for June',1,'[]',90,'filed',NULL,0,NULL,1,0,'2026-08-01 10:00:00','2026-08-01 10:00:00',0,NULL,0,NULL,NULL,0,NULL,NULL,0,NULL,'',NULL,NULL,'default');
INSERT INTO "entries" VALUES(2,'A binned note about tram times',NULL,'[]',0,'pending',NULL,0,NULL,0,0,'2026-08-02 10:00:00','2026-08-02 10:00:00',1,NULL,0,NULL,NULL,0,NULL,NULL,0,NULL,'',NULL,NULL,'default');
PRAGMA writable_schema=ON;
CREATE TABLE entry_bookmarks (
	id INTEGER NOT NULL, 
	entry_id INTEGER NOT NULL, 
	bookmark_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(entry_id) REFERENCES entries (id), 
	FOREIGN KEY(bookmark_id) REFERENCES bookmarks (id)
);
CREATE TABLE entry_dates (
	id INTEGER NOT NULL, 
	entry_id INTEGER NOT NULL, 
	phrase VARCHAR(60) NOT NULL, 
	at DATETIME NOT NULL, 
	precision VARCHAR(10) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(entry_id) REFERENCES entries (id)
);
CREATE TABLE entry_links (
	id INTEGER NOT NULL, 
	source_entry_id INTEGER NOT NULL, 
	target_entry_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	reason TEXT, 
	reason_confidence FLOAT, 
	link_type VARCHAR(24), 
	workspace_id VARCHAR DEFAULT 'default' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(source_entry_id) REFERENCES entries (id), 
	FOREIGN KEY(target_entry_id) REFERENCES entries (id)
);
CREATE TABLE entry_revisions (
	id INTEGER NOT NULL, 
	entry_id INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	tags TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(entry_id) REFERENCES entries (id)
);
CREATE TABLE media_uploads (
	id INTEGER NOT NULL, 
	filename VARCHAR(140) NOT NULL, 
	original_name VARCHAR(300) NOT NULL, 
	created_at DATETIME NOT NULL, 
	ocr_text TEXT, 
	caption TEXT, 
	caption_model VARCHAR(200), 
	caption_edited BOOLEAN NOT NULL, 
	vision_ocr_text TEXT, 
	vision_ocr_model VARCHAR(200), 
	size_bytes INTEGER, 
	workspace_id VARCHAR DEFAULT 'default' NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE page_reads (
	id INTEGER NOT NULL, 
	kind VARCHAR(16) NOT NULL, 
	source_id INTEGER NOT NULL, 
	page INTEGER NOT NULL, 
	reader VARCHAR(16) NOT NULL, 
	model VARCHAR(200) NOT NULL, 
	text TEXT NOT NULL, 
	caption TEXT NOT NULL, 
	caption_model VARCHAR(200) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_page_read_source_page UNIQUE (kind, source_id, page)
);
CREATE TABLE reminders (
	id INTEGER NOT NULL, 
	entry_id INTEGER, 
	text VARCHAR(500) NOT NULL, 
	due_at DATETIME NOT NULL, 
	done BOOLEAN NOT NULL, 
	priority VARCHAR(10) NOT NULL, 
	recurring VARCHAR(10) NOT NULL, 
	created_at DATETIME NOT NULL, 
	workspace_id VARCHAR DEFAULT 'default' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(entry_id) REFERENCES entries (id)
);
CREATE TABLE spaces (
	id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	icon VARCHAR NOT NULL, 
	hidden_from_all BOOLEAN DEFAULT '0' NOT NULL, 
	PRIMARY KEY (id)
);
INSERT INTO "spaces" VALUES('default','Default Space','ph-house',0);
INSERT INTO "spaces" VALUES('work','Work','ph-briefcase',0);
INSERT INTO "spaces" VALUES('personal','Personal','ph-user',0);
INSERT INTO "spaces" VALUES('projects','Projects','ph-kanban',0);
CREATE TABLE user_preferences (
	id INTEGER NOT NULL, 
	content VARCHAR(500) NOT NULL, 
	created_at DATETIME NOT NULL, 
	active BOOLEAN NOT NULL, 
	proposed BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE users (
	id INTEGER NOT NULL, 
	username VARCHAR(100) NOT NULL, 
	password_hash VARCHAR(200) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username)
);
CREATE TABLE vault (
	id INTEGER NOT NULL, 
	kdf_salt BLOB NOT NULL, 
	wrapped_dek BLOB NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE whiteboard_nodes (
	id INTEGER NOT NULL, 
	board_id INTEGER, 
	entry_id INTEGER NOT NULL, 
	x FLOAT NOT NULL, 
	y FLOAT NOT NULL, 
	z INTEGER NOT NULL, 
	width FLOAT, 
	height FLOAT, 
	rotation FLOAT, 
	group_id VARCHAR(40), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	workspace_id VARCHAR DEFAULT 'default' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(board_id) REFERENCES entries (id), 
	FOREIGN KEY(entry_id) REFERENCES entries (id)
);
CREATE TABLE whiteboard_objects (
	id INTEGER NOT NULL, 
	board_id INTEGER, 
	kind VARCHAR(20) NOT NULL, 
	data TEXT NOT NULL, 
	parent_id INTEGER, 
	x FLOAT NOT NULL, 
	y FLOAT NOT NULL, 
	z INTEGER NOT NULL, 
	width FLOAT NOT NULL, 
	height FLOAT NOT NULL, 
	rotation FLOAT, 
	group_id VARCHAR(40), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	workspace_id VARCHAR DEFAULT 'default' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(board_id) REFERENCES entries (id)
);
CREATE TABLE whiteboard_sketches (
	id INTEGER NOT NULL, 
	board_id INTEGER, 
	data TEXT NOT NULL, 
	x FLOAT NOT NULL, 
	y FLOAT NOT NULL, 
	z INTEGER NOT NULL, 
	group_id VARCHAR(40), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	workspace_id VARCHAR DEFAULT 'default' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(board_id) REFERENCES entries (id)
);
CREATE INDEX ix_categories_workspace_id ON categories (workspace_id);
CREATE INDEX ix_conversations_workspace_id ON conversations (workspace_id);
CREATE INDEX ix_ask_turns_workspace_id ON ask_turns (workspace_id);
CREATE INDEX ix_bookmarks_workspace_id ON bookmarks (workspace_id);
CREATE INDEX ix_documents_workspace_id ON documents (workspace_id);
CREATE INDEX ix_page_reads_kind ON page_reads (kind);
CREATE INDEX ix_page_reads_source_id ON page_reads (source_id);
CREATE INDEX ix_media_uploads_workspace_id ON media_uploads (workspace_id);
CREATE INDEX ix_entries_workspace_id ON entries (workspace_id);
CREATE INDEX ix_document_ai_edits_document_id ON document_ai_edits (document_id);
CREATE INDEX ix_document_revisions_document_id ON document_revisions (document_id);
CREATE INDEX ix_entry_links_workspace_id ON entry_links (workspace_id);
CREATE INDEX ix_attachments_workspace_id ON attachments (workspace_id);
CREATE INDEX ix_reminders_workspace_id ON reminders (workspace_id);
CREATE INDEX ix_entry_revisions_entry_id ON entry_revisions (entry_id);
CREATE INDEX ix_entry_dates_entry_id ON entry_dates (entry_id);
CREATE INDEX ix_document_links_document_id ON document_links (document_id);
CREATE INDEX ix_document_links_entry_id ON document_links (entry_id);
CREATE INDEX ix_whiteboard_nodes_group_id ON whiteboard_nodes (group_id);
CREATE INDEX ix_whiteboard_nodes_workspace_id ON whiteboard_nodes (workspace_id);
CREATE INDEX ix_whiteboard_sketches_workspace_id ON whiteboard_sketches (workspace_id);
CREATE INDEX ix_whiteboard_sketches_group_id ON whiteboard_sketches (group_id);
CREATE INDEX ix_whiteboard_objects_workspace_id ON whiteboard_objects (workspace_id);
CREATE INDEX ix_whiteboard_objects_parent_id ON whiteboard_objects (parent_id);
CREATE INDEX ix_whiteboard_objects_group_id ON whiteboard_objects (group_id);
CREATE INDEX ix_entries_live ON entries (workspace_id, is_deleted, archived_at, pinned DESC, created_at DESC, id DESC);
CREATE INDEX ix_entries_bin ON entries (workspace_id, is_deleted, deleted_at DESC, id DESC);
CREATE INDEX ix_entries_archive ON entries (workspace_id, is_deleted, archived_at DESC, id DESC);
CREATE INDEX ix_entries_live_nodraft ON entries (workspace_id, is_deleted, is_draft, archived_at, created_at DESC, id DESC);
CREATE INDEX ix_entries_category_id ON entries (category_id);
CREATE INDEX ix_attachments_entry_id ON attachments (entry_id);
CREATE INDEX ix_media_uploads_workspace_created ON media_uploads (workspace_id, created_at DESC);
CREATE INDEX ix_documents_workspace_live_updated ON documents (workspace_id, archived_at, updated_at DESC);
PRAGMA writable_schema=OFF;
COMMIT;
