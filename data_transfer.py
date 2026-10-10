"""Portable JSON import into a new database only; never overwrite an existing one."""
import argparse, json, gzip, sqlite3, uuid
from pathlib import Path
from storage import Store
from profile_schema import check_profile_metadata
from data_format import EXPORT_FORMAT,EXPORT_VERSION,EXPORT_TABLES,SCHEMA_VERSION,check_integrity,initialize_database,DataFormatError


def import_document(document,destination):
    if not isinstance(document,dict) or not isinstance(document.get('records'),list): raise DataFormatError('导入文件没有有效记录集合')
    supported=set(EXPORT_TABLES)|{'format','format_version','database_schema_version','dataset_id','exported_at','encoding','timezone'}
    if set(document)-supported: raise DataFormatError('导入含当前版本无法处理的数据集合，请使用相应版本')
    if 'format' in document and document['format']!=EXPORT_FORMAT: raise DataFormatError('导入文件格式不受支持')
    if 'format_version' in document and (type(document['format_version']) is not int or document['format_version']!=EXPORT_VERSION): raise DataFormatError('导入文件来自未支持的格式版本，请升级软件')
    if type(document.get('database_schema_version',0)) is not int or document.get('database_schema_version',0)>SCHEMA_VERSION: raise DataFormatError('导入文件来自更新版本的软件')
    destination=Path(destination).resolve()
    if destination.exists(): raise DataFormatError('导入只能创建新数据库，不能覆盖已有文件')
    destination.parent.mkdir(parents=True,exist_ok=True); stage=destination.parent/('.import-'+uuid.uuid4().hex+'.sqlite3')
    try:
        store=Store(stage)
        with store.connection() as c:
            # Existing exports retain their tables, row IDs, revisions and data namespace.
            metadata=document.get('metadata',[])
            if not isinstance(metadata,list): raise DataFormatError('元数据格式无效')
            for table in EXPORT_TABLES:
                rows=document.get(table,[])
                if not isinstance(rows,list): raise DataFormatError('导入集合格式无效：'+table)
                columns={r[1] for r in c.execute('PRAGMA table_info('+table+')')}-{'compressed_text'}
                for row in rows:
                    if not isinstance(row,dict) or set(row)-columns: raise DataFormatError('导入含当前版本无法处理的字段：'+table)
                    if table=='metadata':
                        if set(row)!={'key','value'}: raise DataFormatError('元数据字段无效')
                        c.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',(row['key'],row['value'])); continue
                    if not row: raise DataFormatError('导入存在空记录')
                    if table=='records' and (row.get('kind') not in ('profile','state','journal','project','decision','resource','memory') or row.get('status') not in ('confirmed','inferred','unconfirmed') or row.get('sensitivity') not in ('normal','sensitive')): raise DataFormatError('个人记录类型或权限无效')
                    keys=list(row); c.execute('INSERT INTO '+table+'('+','.join(keys)+') VALUES ('+','.join('?' for _ in keys)+')',[row[k] for k in keys])
            if document.get('dataset_id'):
                row=c.execute("SELECT value FROM metadata WHERE key='dataset_id'").fetchone()
                if not row or row[0]!=document['dataset_id']: raise DataFormatError('数据库身份与导出标记不一致')
            check_profile_metadata(c)
            c.execute("UPDATE jobs SET status='queued' WHERE status='running'")
        initialize_database(stage,make_backup=False)
        with store.connection() as c: check_integrity(c)
        # Exclusive creation: a concurrent file appearing here is never replaced.
        created=False
        try:
            with destination.open('xb') as output, stage.open('rb') as source:
                import shutil
                created=True; shutil.copyfileobj(source,output)
        except Exception:
            if created: destination.unlink(missing_ok=True)
            raise
        return destination
    except Exception:
        raise
    finally: stage.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('--destination',type=Path,required=True);args=parser.parse_args()
    opener=gzip.open if args.source.name.endswith('.gz') else open
    with opener(args.source,'rt',encoding='utf-8-sig') as file: document=json.load(file)
    import_document(document,args.destination); print('Import verified. Original database was not replaced. API credentials must be configured separately.')

if __name__=='__main__': main()
