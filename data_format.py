"""Versioned local format, additive migrations and validated SQLite snapshots."""
from functools import lru_cache
from pathlib import Path
from datetime import datetime, timezone, timedelta
import sqlite3, uuid, time, gzip, json, io

SCHEMA_VERSION = 5
EXPORT_FORMAT = 'personal-memory'
EXPORT_VERSION = 1
EXPORT_TABLES = ('metadata','records','revisions','sessions','messages','proposals','summaries','entry_digests','jobs','providers','usage')
class DataFormatError(ValueError): pass

SCHEMA_SQL = "\n   CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,category TEXT NOT NULL,title TEXT NOT NULL,content TEXT NOT NULL,source TEXT NOT NULL,event_date TEXT NOT NULL DEFAULT '',tags TEXT NOT NULL DEFAULT '',status TEXT NOT NULL,sensitivity TEXT NOT NULL,share_with_ai INTEGER NOT NULL DEFAULT 0,archived INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);\n   CREATE TABLE IF NOT EXISTS revisions(id INTEGER PRIMARY KEY,record_id INTEGER NOT NULL REFERENCES records(id),snapshot TEXT NOT NULL,changed_at TEXT NOT NULL);\n   CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);\n   CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at TEXT NOT NULL);\n   CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,session_id TEXT NOT NULL REFERENCES sessions(id),role TEXT NOT NULL,content TEXT NOT NULL,created_at TEXT NOT NULL,share_with_ai INTEGER NOT NULL,organized INTEGER NOT NULL DEFAULT 0,answer_for INTEGER UNIQUE,request_id TEXT UNIQUE,model TEXT NOT NULL DEFAULT '');\n   CREATE TABLE IF NOT EXISTS proposals(id INTEGER PRIMARY KEY,dedupe_key TEXT UNIQUE,kind TEXT NOT NULL,field_key TEXT,title TEXT NOT NULL,content TEXT NOT NULL,quote TEXT NOT NULL,source_ids TEXT NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',record_id INTEGER,created_at TEXT NOT NULL);\n   CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,dedupe_key TEXT UNIQUE,kind TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'queued',attempts INTEGER NOT NULL DEFAULT 0,due_at TEXT NOT NULL,last_error TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL);\n   CREATE TABLE IF NOT EXISTS summaries(id INTEGER PRIMARY KEY,period TEXT NOT NULL,type TEXT NOT NULL,fingerprint TEXT NOT NULL,summary TEXT NOT NULL,events TEXT NOT NULL,ideas TEXT NOT NULL,source_ids TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft',updated_at TEXT NOT NULL,UNIQUE(period,type));\n   CREATE TABLE IF NOT EXISTS providers(id TEXT PRIMARY KEY,name TEXT NOT NULL,base_url TEXT NOT NULL,model TEXT NOT NULL,organizer_model TEXT NOT NULL);\n   CREATE TABLE IF NOT EXISTS usage(id INTEGER PRIMARY KEY,day TEXT NOT NULL,provider_id TEXT NOT NULL,purpose TEXT NOT NULL,created_at TEXT NOT NULL,tokens INTEGER NOT NULL DEFAULT 0);\n   CREATE TABLE IF NOT EXISTS entry_digests(id INTEGER PRIMARY KEY,job_id INTEGER UNIQUE,source_ids TEXT NOT NULL,overview TEXT NOT NULL,events TEXT NOT NULL,ideas TEXT NOT NULL,created_at TEXT NOT NULL);\n   CREATE TABLE IF NOT EXISTS summary_cache(key TEXT PRIMARY KEY,result TEXT NOT NULL);\n   CREATE INDEX IF NOT EXISTS records_lookup ON records(kind,archived);\n   CREATE INDEX IF NOT EXISTS messages_pending ON messages(organized,share_with_ai);\n   CREATE INDEX IF NOT EXISTS jobs_ready ON jobs(status,due_at);\n   "
ADDED_COLUMNS = {'records': {'field_key':'TEXT','source_message_id':'INTEGER'}, 'messages': {'organize_offset':'INTEGER NOT NULL DEFAULT 0'}}

def table_names(c):
    return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}

def version(c):
    if 'metadata' not in table_names(c): return 0
    try:
        row=c.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
        text=str(row[0]) if row else '0'
        if not text.isdecimal(): raise DataFormatError('数据库版本标记无效，未修改数据')
        number=int(text)
        if number>SCHEMA_VERSION: raise DataFormatError('数据库来自更新版本的软件，请使用相应新版本打开；未修改数据')
        return number
    except sqlite3.Error: raise DataFormatError('数据库版本信息无法读取，未修改数据') from None

@lru_cache(maxsize=1)
def expected_columns():
    c=sqlite3.connect(':memory:')
    try:
        c.executescript(SCHEMA_SQL)
        return {t:{r[1] for r in c.execute('PRAGMA table_info('+t+')')} for t in table_names(c)}
    finally: c.close()

def check_shape(c):
    tables=table_names(c); v=version(c)
    if tables and 'records' not in tables: raise DataFormatError('文件不是受支持的个人数据库')
    for table, required in expected_columns().items():
        if table in tables:
            columns={r[1] for r in c.execute('PRAGMA table_info('+table+')')}
            if not required<=columns: raise DataFormatError('数据库表结构不完整：'+table+'；未覆盖现有数据')
    if v>=4:
        for table in ('records','messages','revisions'):
            if table in tables and 'compressed_text' not in {r[1] for r in c.execute('PRAGMA table_info('+table+')')}: raise DataFormatError('压缩记录字段缺失，未修改数据')
        for table,fields in {'memory_chunks':{'id','record_id','start','end','digest','tags'},'memory_dirty':{'record_id'},'embedding_cache':{'key','vector','updated_at'}}.items():
            if table in tables and not fields<={r[1] for r in c.execute('PRAGMA table_info('+table+')')}: raise DataFormatError('检索索引格式无效，未修改数据')
    if v>=5:
        for table,fields in {'records':{'content_state'},'messages':{'retention_state','compact_content','source_hash'},'proposals':{'review_level','evidence_verified'}}.items():
            if table in tables and not fields<={r[1] for r in c.execute('PRAGMA table_info('+table+')')}: raise DataFormatError('关键信息字段缺失，未修改数据')
    if v>=3:
        row=c.execute("SELECT value FROM metadata WHERE key='dataset_id'").fetchone()
        try: uuid.UUID(row[0] if row else '')
        except (ValueError,TypeError,AttributeError): raise DataFormatError('数据库身份信息无效，未修改数据') from None
    return v

def check_integrity(c):
    if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise DataFormatError('数据库完整性检查未通过')
    if c.execute('PRAGMA foreign_key_check').fetchone() is not None: raise DataFormatError('数据库来源关联检查未通过')
    for table in ('records','messages','revisions'):
        if table in table_names(c) and 'compressed_text' in {r[1] for r in c.execute('PRAGMA table_info('+table+')')}:
            old_factory=c.row_factory; c.row_factory=sqlite3.Row
            try:
                for row in c.execute('SELECT * FROM '+table+' WHERE compressed_text IS NOT NULL'): decode_row(table,row)
            finally: c.row_factory=old_factory

def copy_database(source, destination):
    src=sqlite3.connect(Path(source).resolve().as_uri()+'?mode=ro',uri=True,timeout=15)
    dst=sqlite3.connect(destination,timeout=15)
    deadline=time.monotonic()+30
    def progress(status,remaining,total):
        if remaining and time.monotonic()>deadline: raise DataFormatError('数据库复制超时，操作已停止')
    try:
        src.backup(dst,pages=128,progress=progress,sleep=0.05)
        check_integrity(dst)
    finally: dst.close(); src.close()

def backup_database(path, prefix='personal'):
    path=Path(path).resolve(); folder=path.parent.parent/'backups'; folder.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')
    target=folder/(prefix+'-'+stamp+'-'+uuid.uuid4().hex[:8]+'.sqlite3')
    partial=target.with_suffix('.partial')
    try:
        copy_database(path,partial)
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return target

def migrate_base(c):
    # executescript would commit a pending transaction; execute each statement separately.
    for statement in SCHEMA_SQL.split(';'):
        if statement.strip(): c.execute(statement)

def migrate_columns(c):
    migrate_base(c)
    for table, additions in ADDED_COLUMNS.items():
        columns={r[1] for r in c.execute('PRAGMA table_info('+table+')')}
        for name, declaration in additions.items():
            if name not in columns: c.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+declaration)
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS field_unique ON records(field_key) WHERE field_key IS NOT NULL AND archived=0')

def migrate_identity(c):
    row=c.execute("SELECT value FROM metadata WHERE key='dataset_id'").fetchone()
    if row:
        try: uuid.UUID(row[0])
        except (ValueError,TypeError,AttributeError): raise DataFormatError('已有数据库身份信息无效，未覆盖') from None
    else: c.execute("INSERT INTO metadata VALUES ('dataset_id',?)",(str(uuid.uuid4()),))

def migrate_storage(c):
    for table in ('records','messages','revisions'):
        columns={r[1] for r in c.execute('PRAGMA table_info('+table+')')}
        if 'compressed_text' not in columns: c.execute('ALTER TABLE '+table+' ADD COLUMN compressed_text BLOB')
    c.execute('CREATE TABLE IF NOT EXISTS memory_chunks(id INTEGER PRIMARY KEY,record_id INTEGER NOT NULL REFERENCES records(id),start INTEGER NOT NULL,end INTEGER NOT NULL,digest TEXT NOT NULL,tags TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS memory_dirty(record_id INTEGER PRIMARY KEY)')
    c.execute('CREATE TABLE IF NOT EXISTS embedding_cache(key TEXT PRIMARY KEY,vector BLOB NOT NULL,updated_at TEXT NOT NULL)')
    c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(tokens,tokenize='unicode61')")
    for event in ('INSERT','UPDATE','DELETE'):
        ref='OLD' if event=='DELETE' else 'NEW'
        c.execute('CREATE TRIGGER IF NOT EXISTS memory_dirty_'+event.lower()+' AFTER '+event+' ON records BEGIN INSERT OR IGNORE INTO memory_dirty VALUES ('+ref+'.id); END')
    c.execute("CREATE TRIGGER IF NOT EXISTS memory_dirty_sources AFTER UPDATE ON records WHEN NEW.source_message_id IS NOT NULL BEGIN INSERT OR IGNORE INTO memory_dirty SELECT p.record_id FROM proposals p,json_each(p.source_ids) j WHERE j.value=NEW.source_message_id AND p.record_id IS NOT NULL; END")
    c.execute('INSERT OR IGNORE INTO memory_dirty SELECT id FROM records')

def migrate_compact(c):
    additions={'records':{'content_state':"TEXT NOT NULL DEFAULT 'entered'"},'messages':{'retention_state':"TEXT NOT NULL DEFAULT 'pending'",'compact_content':"TEXT NOT NULL DEFAULT ''",'source_hash':"TEXT NOT NULL DEFAULT ''"},'proposals':{'review_level':"TEXT NOT NULL DEFAULT 'routine'",'evidence_verified':"INTEGER NOT NULL DEFAULT 0"}}
    for table,fields in additions.items():
        columns={r[1] for r in c.execute('PRAGMA table_info('+table+')')}
        for name,declaration in fields.items():
            if name not in columns:c.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+declaration)
    # Old originals are queued for extraction, not silently discarded by migration.
    c.execute("UPDATE messages SET organized=0,organize_offset=0 WHERE role='user' AND share_with_ai=1 AND content!=''")
    c.execute("UPDATE records SET content_state='pending' WHERE kind='journal' AND source_message_id IN (SELECT id FROM messages WHERE role='user' AND share_with_ai=1)")
    c.execute("UPDATE jobs SET payload='{}' WHERE kind='organize' AND status='done'")
    c.execute("UPDATE proposals SET review_level='core' WHERE kind='profile'")
    c.execute('DELETE FROM summary_cache')
    settings=c.execute("SELECT value FROM metadata WHERE key='settings'").fetchone()
    if settings:
        values=json.loads(settings[0]);values['auto_update_profile']=False
        c.execute("UPDATE metadata SET value=? WHERE key='settings'",(json.dumps(values),))
    c.execute('CREATE INDEX IF NOT EXISTS records_source_message ON records(source_message_id)')
    c.execute('CREATE INDEX IF NOT EXISTS records_summary_dates ON records(kind,archived,event_date)')

MIGRATIONS = {1:migrate_base,2:migrate_columns,3:migrate_identity,4:migrate_storage,5:migrate_compact}

def decode_row(table, row):
    value=dict(row); compressed=value.pop('compressed_text',None)
    if compressed is not None:
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(compressed),mode='rb') as reader: raw=reader.read(2_000_001)
            if len(raw)>2_000_000: raise DataFormatError('单条压缩记录超过支持范围')
            value['snapshot' if table=='revisions' else 'content']=raw.decode('utf-8')
        except (OSError,UnicodeError,EOFError,TypeError): raise DataFormatError('压缩记录校验失败，原文件已保留') from None
    return value


def initialize_database(path, make_backup=True):
    path=Path(path); c=sqlite3.connect(path,timeout=15)
    try:
        c.execute('PRAGMA foreign_keys=ON'); c.execute('BEGIN IMMEDIATE')
        current=check_shape(c); tables=table_names(c)
        missing=bool(set(expected_columns())-tables)
        for table, additions in ADDED_COLUMNS.items():
            if table in tables:
                missing=missing or not set(additions)<={r[1] for r in c.execute('PRAGMA table_info('+table+')')}
        missing=missing or not c.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='field_unique'").fetchone()
        if current>=4:
            missing=missing or not {'memory_chunks','memory_dirty','memory_fts','embedding_cache'}<=tables
            missing=missing or any('compressed_text' not in {r[1] for r in c.execute('PRAGMA table_info('+t+')')} for t in ('records','messages','revisions'))
        if current==SCHEMA_VERSION and not missing: c.rollback(); return
        check_integrity(c)
        # A second read connection can snapshot while this connection holds the writer reservation.
        if tables and make_backup: backup_database(path,'migration-v'+str(current)+'-personal')
        for target in range(current+1,SCHEMA_VERSION+1):
            MIGRATIONS[target](c)
            c.execute("INSERT OR REPLACE INTO metadata VALUES ('schema_version',?)",(str(target),))
        if missing:
            migrate_columns(c)
            if current>=4: migrate_storage(c)
        check_shape(c); check_integrity(c); c.commit()
    except Exception:
        c.rollback(); raise
    finally: c.close()

def export_document(c, exported_at):
    c.execute('BEGIN')
    check_shape(c)
    identity=c.execute("SELECT value FROM metadata WHERE key='dataset_id'").fetchone()[0]
    result={'format':EXPORT_FORMAT,'format_version':EXPORT_VERSION,'database_schema_version':version(c),'dataset_id':identity,'exported_at':exported_at,'encoding':'UTF-8','timezone':'Asia/Shanghai'}
    result.update({t:[decode_row(t,r) for r in c.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in EXPORT_TABLES})
    return result
