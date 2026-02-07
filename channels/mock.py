"""
Mock Channel - For testing without actual sending
"""
from core import ChannelInterface, Message


class MockChannel(ChannelInterface):
    """Mock 通道 - 仅打印消息，不实际发送"""
    
    def __init__(self):
        self.sent_messages = []
    
    def send(self, message: Message) -> bool:
        """
        模拟发送（仅记录）
        
        Args:
            message: 消息对象
            
        Returns:
            bool: 总是返回 True
        """
        print(f"\n[MockChannel] Would send message:")
        print(f"  Title: {message.title}")
        print(f"  Type: {message.type.value}")
        print(f"  Content length: {len(str(message.content))} chars")
        print(f"  Tags: {message.tags}")
        
        self.sent_messages.append(message)
        return True
    
    def get_sent_count(self) -> int:
        """获取已发送消息数"""
        return len(self.sent_messages)
