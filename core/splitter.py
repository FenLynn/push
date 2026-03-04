"""
Content Splitter - Handle PushPlus character limit
"""
from typing import List
import re
from core import Message, ContentType
from core.constants import PUSHPLUS_MAX_CONTENT_LENGTH


class Splitter:
    """内容分割器 - 处理超长内容"""
    
    def __init__(self, max_length: int = PUSHPLUS_MAX_CONTENT_LENGTH):
        """
        初始化分割器
        
        Args:
            max_length: 最大长度（字符数），默认使用 PushPlus 单条消息安全上限
        """
        self.max_length = max_length
    
    def split(self, message: Message) -> List[Message]:
        """
        智能分割消息
        
        Args:
            message: 原始消息
            
        Returns:
            List[Message]: 分割后的消息列表
        """
        content = str(message.content)
        
        if len(content) <= self.max_length:
            return [message]
        
        # 根据内容类型选择分割策略
        if message.type == ContentType.HTML:
            chunks = self._split_html(content)
        elif message.type == ContentType.MARKDOWN:
            chunks = self._split_markdown(content)
        else:
            chunks = self._split_plain(content)
        
        # 创建分页消息
        messages = []
        total_pages = len(chunks)
        
        for i, chunk in enumerate(chunks, 1):
            page_title = f"{message.title} [{i}/{total_pages}]" if total_pages > 1 else message.title
            
            messages.append(Message(
                title=page_title,
                content=chunk,
                type=message.type,
                tags=message.tags,
                metadata={**message.metadata, 'page': i, 'total_pages': total_pages}
            ))
        
        return messages
    
    def _split_html(self, html: str) -> List[str]:
        """
        智能分割 HTML - 针对 Card 布局优化
        """
        # 提取头部 (Head + Style + Container start)
        # 假设标准模板结构
        head_match = re.search(r'(<html.*?>.*?<div class="container">)', html, re.DOTALL | re.IGNORECASE)
        footer_match = re.search(r'(<div class="(?:footer|ft)">.*?</html>)', html, re.DOTALL | re.IGNORECASE)
        
        if not head_match or not footer_match:
            # 无法识别结构，降级到简单分割
            return self._split_simple(html)
            
        head_html = head_match.group(1)
        footer_html = footer_match.group(1)
        
        # 提取 Header (只在第一页显示完整 Header，或者都显示)
        # 这里简单处理：Header 作为第一个 block
        
        # 提取中间内容
        content_start = head_match.end()
        content_end = footer_match.start()
        body_content = html[content_start:content_end]
        
        chunks = []
        current_chunk = head_html
        
        # 简单方案：按 <div class="card"> 分割 (新模板使用 .card)
        # 如果没有找到 card，尝试找 journal-card (兼容旧版)
        split_token = '<div class="card">'
        if split_token not in body_content:
            split_token = '<div class="journal-card">'
            
        parts = body_content.split(split_token)
        
        # parts[0] 通常是 Header 部分
        header_part = parts[0]
        current_content = header_part
        
        for i in range(1, len(parts)):
            card_html = split_token + parts[i]
            
            # 预估添加此卡片后的长度 ( + footer 长度)
            if len(current_chunk) + len(current_content) + len(card_html) + len(footer_html) < self.max_length:
                current_content += card_html
            else:
                # 当前块已满，保存
                chunks.append(current_chunk + current_content + footer_html)
                # 开启新块
                current_chunk = head_html
                # 后续页显示简略信息
                current_content = "<div class='header'><div class='h-main'><div class='h-meta'>接上页...</div></div></div>" + card_html
        
        # 添加最后一个块
        if current_content:
            chunks.append(current_chunk + current_content + footer_html)
            
        return chunks if chunks else [html]

    def _split_simple(self, html: str) -> List[str]:
        """简单分割（旧版/通用）"""
        return [html[i:i+self.max_length] for i in range(0, len(html), self.max_length)]

    
    def _split_markdown(self, md: str) -> List[str]:
        """按段落分割 Markdown"""
        chunks = []
        current = ""
        
        for line in md.split('\n'):
            if len(current) + len(line) + 1 < self.max_length:
                current += line + '\n'
            else:
                if current:
                    chunks.append(current.rstrip())
                current = line + '\n'
        
        if current:
            chunks.append(current.rstrip())
        
        return chunks if chunks else [md]
    
    def _split_plain(self, text: str) -> List[str]:
        """按字符数强制分割纯文本"""
        return [text[i:i+self.max_length] for i in range(0, len(text), self.max_length)]
