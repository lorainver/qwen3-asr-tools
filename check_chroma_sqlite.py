"""检查 ChromaDB SQLite 数据库"""
import sqlite3

conn = sqlite3.connect(r'D:\qwen3-asr\knowledge_base\chroma_db\chroma.sqlite3')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('Tables:', cursor.fetchall())

cursor.execute('SELECT COUNT(*) FROM embeddings')
print('embeddings count:', cursor.fetchone()[0])

cursor.execute('SELECT DISTINCT id, key, string_value FROM embedding_metadata WHERE key="doc_id"')
print('所有 doc_id:')
for r in cursor.fetchall():
    print(f'  segment_id={r[0]}, doc_id={r[2]}')

cursor.execute('SELECT COUNT(DISTINCT id) FROM embedding_metadata WHERE key="doc_id"')
print(f'总 doc 数: {cursor.fetchone()[0]}')

conn.close()
