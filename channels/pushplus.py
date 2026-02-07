"""
PushPlus Channel - 微信推送
Extracted from cloud/net.py
"""
import os
import requests
from core import ChannelInterface, Message, ContentType


class PushPlusChannel(ChannelInterface):
    """PushPlus 推送通道"""
    
    def __init__(self, token: str = None, topic: str = "me"):
        """
        初始化 PushPlus 通道
        
        Args:
            token: PushPlus Token (优先从环境变量读取)
            topic: 推送主题
        """
        self.token = token or os.getenv('PUSHPLUS_TOKEN')
        if not self.token:
            raise ValueError("PushPlus token not provided")
        
        self.topic = topic
        self.api_url = "http://www.pushplus.plus/send"
    
    def send(self, message: Message) -> bool:
        """
        发送消息到 PushPlus
        
        Args:
            message: 消息对象
            
        Returns:
            bool: 是否成功
        """
        SAFE_LENGTH = 19800  # User Requested Limit (Maximized)
        
        # 检查内容长度，如果过长则分割发送
        if len(str(message.content)) > SAFE_LENGTH:
            print(f"[PushPlus] Content length {len(str(message.content))} exceeds {SAFE_LENGTH}, splitting...")
            from core.splitter import Splitter
            splitter = Splitter(max_length=SAFE_LENGTH)
            messages = splitter.split(message)
            
            import time
            success = True
            for i, msg in enumerate(messages, 1):
                if i > 1:
                    print("[PushPlus] Waiting 2s to avoid rate limiting...")
                    time.sleep(2)
                
                print(f"[PushPlus] Sending part {i}/{len(messages)}...")
                if not self._send_single(msg):
                    success = False
                    print(f"[PushPlus] Failed to send part {i}")
            return success
            
        return self._send_single(message)
    
    def _send_single(self, message: Message) -> bool:
        """发送单个消息"""
        # 映射 ContentType 到 PushPlus template
        template_map = {
            ContentType.TEXT: 'txt',
            ContentType.HTML: 'html',
            ContentType.MARKDOWN: 'markdown',
            ContentType.IMAGE: 'cloudimage',
            ContentType.FILE: 'html'  # 文件当作 HTML 处理
        }
        
        template = template_map.get(message.type, 'html')
        
        # 构建请求数据（与旧代码完全一致）
        data = {
            "token": self.token,
            "title": message.title,
            "content": str(message.content),
            "template": template
        }
        
        # topic 映射（仅当非 'me' 时添加数字 topic）
        topic_map = {
            'baobao': 12,
            'family': 13,
            'stock': 14,
            'paper': 15
        }
        
        if self.topic in topic_map:
            data['topic'] = topic_map[self.topic]
        
        # 使用与旧代码完全一致的请求方式
        import json
        headers = {'Content-type': 'application/json'}
        body = json.dumps(data).encode(encoding='utf-8')
        
        try:
            response = requests.post(self.api_url, data=body, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if result.get('code') == 200:
                print(f"[PushPlus] Sent: {message.title}")
                return True
            else:
                print(f"[PushPlus] Failed: {result.get('msg')}")
                return False
                
        except Exception as e:
            print(f"[PushPlus] Error: {str(e)}")
            return False
