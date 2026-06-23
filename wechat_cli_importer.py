"""
wechat-cli export 格式导入器

将 wechat-cli export 生成的 Markdown 文件转换为标准格式，
然后导入到知识库。
"""

import re
from pathlib import Path
from typing import List, Optional


class WeChatCliImporter:
    """wechat-cli export 格式的导入器"""
    
    def __init__(self, output_dir="knowledge_base/wechat"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def convert_to_standard_format(self, md_path: str) -> str:
        """
        将 wechat-cli export 格式转换为标准格式
        
        输入格式：
        - [2026-06-22 19:03] tony zhong: 英语这门学科真邪门
        
        输出格式：
        **tony zhong** (2026-06-22 19:03):
        
        英语这门学科真邪门
        """
        with open(md_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        output_path = str(Path(md_path).with_suffix('.standard.md'))
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # 复制元数据
            for line in lines:
                if line.startswith('#') or line.startswith('**') or line.strip() == '---':
                    f.write(line)
            
            # 转换消息
            for line in lines:
                if line.strip().startswith('- ['):
                    # 解析消息行
                    match = re.match(r'- \[(.+?)\] (.+?): (.+)', line.strip())
                    if match:
                        timestamp = match.group(1)
                        speaker = match.group(2)
                        content = match.group(3)
                        
                        f.write(f"\n**{speaker}** ({timestamp}):\n\n{content}\n\n")
        
        return output_path
    
    def import_to_kb(self, md_path: str, category: str = "微信聊天记录") -> str:
        """
        直接导入到知识库
        
        步骤：
        1. 转换为标准格式
        2. 使用 WeChatChunker 分块
        3. 索引到 ChromaDB
        """
        # 1. 转换为标准格式
        standard_md = self.convert_to_standard_format(md_path)
        
        # 2. 分块（使用 WeChatChunker）
        from knowledge_store import WeChatChunker
        chunker = WeChatChunker(chunk_size=500, overlap=50)
        chunks = chunker.chunk_wechat_md(standard_md)
        
        # 3. 索引到知识库
        from knowledge_store import vector_store
        doc_id = vector_store.add_documents(
            chunks,
            filename=Path(md_path).name,
            category=category
        )
        
        return doc_id


if __name__ == "__main__":
    # 测试
    importer = WeChatCliImporter()
    
    # 转换测试文件
    standard_md = importer.convert_to_standard_format(
        "D:/qwen3-asr/knowledge_base/wechat/信竞家长交流群_测试.md"
    )
    
    print(f"✅ 转换完成: {standard_md}")
