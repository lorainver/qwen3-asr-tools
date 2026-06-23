"""检查 knowledge_store 模块的 vectorstore 缓存"""
import knowledge_store

print('_vectorstore:', knowledge_store._vectorstore)
print('type:', type(knowledge_store._vectorstore))

# 检查是否有其他缓存
import inspect
src = inspect.getsource(knowledge_store.get_vectorstore)
print('\nget_vectorstore source:')
print(src)

# 检查全局变量
print('\n知识库相关模块变量:')
for name in dir(knowledge_store):
    if 'vector' in name.lower() or 'vs' in name.lower() or 'store' in name.lower():
        val = getattr(knowledge_store, name, None)
        t = type(val).__name__
        print(f'  {name}: {t}')
