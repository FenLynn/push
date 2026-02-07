"""
Push Core Module - Message Protocol & Interfaces
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
from enum import Enum


class ContentType(Enum):
    """消息内容类型"""
    TEXT = "text"
    MARKDOWN = "markdown"
    HTML = "html"
    IMAGE = "image"
    FILE = "file"


@dataclass
class Message:
    """标准消息体 - 系统内部流转的唯一数据格式"""
    title: str
    content: Any
    type: ContentType = ContentType.TEXT
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if isinstance(self.type, str):
            self.type = ContentType(self.type)


class SourceInterface(ABC):
    """数据源接口 - 所有业务模块必须实现"""
    
    @abstractmethod
    def run(self) -> Message:
        """
        获取数据并生成消息
        
        Returns:
            Message: 标准消息对象
        """
        pass
    
    @property
    def name(self) -> str:
        """数据源名称"""
        return self.__class__.__name__


class ChannelInterface(ABC):
    """推送通道接口 - 所有推送方式必须实现"""
    
    @abstractmethod
    def send(self, message: Message) -> bool:
        """
        发送消息
        
        Args:
            message: 要发送的消息
            
        Returns:
            bool: 发送是否成功
        """
        pass
    
    @property
    def name(self) -> str:
        """通道名称"""
        return self.__class__.__name__
