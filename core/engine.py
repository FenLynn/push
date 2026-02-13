"""
Engine - Core dispatcher and orchestrator
"""
from typing import List, Dict
from core import Message, SourceInterface, ChannelInterface
from core.splitter import Splitter
import time


import logging

class Engine:
    """引擎 - 调度 Sources 和 Channels"""
    
    def __init__(self, splitter: Splitter = None):
        """
        初始化引擎
        
        Args:
            splitter: 内容分割器
        """
        self.splitter = splitter or Splitter()
        self.sources: Dict[str, SourceInterface] = {}
        self.channels: Dict[str, ChannelInterface] = {}
        self.logger = logging.getLogger('Push.Engine')
    
    def register_source(self, name: str, source: SourceInterface):
        """注册数据源"""
        self.sources[name] = source
    
    def register_channel(self, name: str, channel: ChannelInterface):
        """注册推送通道"""
        self.channels[name] = channel
    
    
    def save_output(self, source_name: str, message: Message, suffix: str = "") -> str:
        """
        保存消息内容到文件
        """
        import os
        from datetime import datetime
        from core import ContentType
        
        # 确定后缀
        ext = 'html' if message.type == ContentType.HTML else 'md'
        
        # 创建目录 output/<source_name>
        out_dir = os.path.join(os.getcwd(), 'output', source_name)
        os.makedirs(out_dir, exist_ok=True)
        
        # 1. 保存为 latest.<ext>
        latest_path = os.path.join(out_dir, f'latest{suffix}.{ext}')
        with open(latest_path, 'w', encoding='utf-8') as f:
            f.write(message.content)
            
        # 2. 保存为归档 yyyy-mm-dd.<ext> (覆盖同日之前的)
        date_str = datetime.now().strftime('%Y-%m-%d')
        archive_path = os.path.join(out_dir, f'{date_str}{suffix}.{ext}')
        with open(archive_path, 'w', encoding='utf-8') as f:
            f.write(message.content)
            
        self.logger.info(f"Output saved to: {latest_path}")
        
        # 3. Cloud Mode: Upload to R2
        from core.config import config
        if config.RUN_MODE == 'cloud':
            try:
                from core.image_upload import R2Uploader
                uploader = R2Uploader()
                if uploader.s3:
                    # Upload latest version (overwrite)
                    # Object Name: output/source_name/latest.html
                    latest_key = f"output/{source_name}/latest{suffix}.{ext}"
                    url = uploader.upload_file(latest_path, object_name=latest_key)
                    if url:
                        self.logger.info(f"☁️ Uploaded to R2 (Latest): {url}")
                        
                    # Upload archive version (history)
                    # Object Name: output/source_name/yyyy-mm-dd.html
                    # Lifecycle rule on bucket handles 7-day deletion
                    archive_key = f"output/{source_name}/{date_str}{suffix}.{ext}"
                    url_arch = uploader.upload_file(archive_path, object_name=archive_key)
                    if url_arch:
                        self.logger.info(f"☁️ Uploaded to R2 (Archive): {url_arch}")
            except Exception as e:
                self.logger.error(f"Failed to upload output to R2: {e}")
                
        return latest_path

    def run_source_only(self, source_name: str) -> str:
        """
        仅运行源并生成文件 (Gen Mode)
        
        Returns:
            str: 生成的文件路径
        """
        if source_name not in self.sources:
            self.logger.error(f"Source '{source_name}' not found")
            return None
        
        source = self.sources[source_name]
        self.logger.info(f"Generating content for: {source_name}")
        
        try:
            results = source.run()
            if isinstance(results, list):
                paths = []
                for idx, message in enumerate(results):
                    suffix = "" if idx == 0 else f"_{idx+1}"
                    paths.append(self.save_output(source_name, message, suffix=suffix))
                return ", ".join(paths) if paths else None
            else:
                return self.save_output(source_name, results)
        except Exception as e:
            self.logger.error(f"Generation failed: {str(e)}", exc_info=True)
            return None

    def run_source(self, source_name: str, channel_names: List[str] = None) -> bool:
        """
        运行指定数据源并推送 (Run Mode)
        """
        if source_name not in self.sources:
            self.logger.error(f"Source '{source_name}' not found")
            return False
        
        source = self.sources[source_name]
        
        # 获取数据
        self.logger.info(f"Running source: {source_name}")
        try:
            results = source.run()
            if not isinstance(results, list):
                results = [results]
            
            total_success = 0
            
            for idx, message in enumerate(results):
                # 自动保存 (Handle pagination suffixes if needed)
                suffix = f"_{idx+1}" if len(results) > 1 else ""
                self.save_output(source_name, message, suffix=suffix)
                
                # 分割内容 (HTML typically won't split well here if generic splitter is used, but we rely on source-level pagination now)
                messages = self.splitter.split(message)
                
                # 确定目标通道
                targets = channel_names or list(self.channels.keys())
                if not targets:
                    self.logger.warning("No channels available")
                    continue
                
                # 推送
                success_count = 0
                for channel_name in targets:
                    if channel_name not in self.channels:
                        self.logger.warning(f"Channel '{channel_name}' not found")
                        continue
                    
                    channel = self.channels[channel_name]
                    
                    for msg in messages:
                        if channel.send(msg):
                            success_count += 1
                            self.logger.info(f"Sent message to '{channel_name}'")
                        else:
                            self.logger.error(f"Failed to send to '{channel_name}'")
                        time.sleep(2)
                
                if success_count > 0:
                    total_success += 1
                    
            return total_success > 0
            
        except Exception as e:
            self.logger.error(f"Source failed: {str(e)}", exc_info=True)
            return False

    def run_with_message(self, message: Message, source_name: str, channel_names: List[str] = None) -> bool:
        """
        使用已有消息进行推送 (支持自定义标题等修改)
        """
        # 自动保存
        self.save_output(source_name, message)
        
        # 分割内容
        messages = self.splitter.split(message)
        
        # 确定目标通道
        targets = channel_names or list(self.channels.keys())
        if not targets:
            self.logger.warning("No channels available")
            return False
        
        # 推送
        success_count = 0
        for channel_name in targets:
            if channel_name not in self.channels:
                self.logger.warning(f"Channel '{channel_name}' not found")
                continue
            
            channel = self.channels[channel_name]
            
            for msg in messages:
                if channel.send(msg):
                    success_count += 1
                    self.logger.info(f"Sent message to '{channel_name}'")
                else:
                    self.logger.error(f"Failed to send to '{channel_name}'")
                time.sleep(2)  # 避免频繁请求
        
        self.logger.info(f"Sent {success_count}/{len(messages)} messages")
        return success_count > 0
