"""
Template Engine - Jinja2 wrapper for HTML/Markdown generation
"""
from pathlib import Path
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape


class TemplateEngine:
    """模板引擎 - 统一 HTML/Markdown 生成"""
    
    def __init__(self, template_dir: str = None):
        """
        初始化模板引擎
        
        Args:
            template_dir: 模板目录路径
        """
        if template_dir is None:
            # 默认使用 push/templates
            template_dir = Path(__file__).parent.parent / "templates"
        
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        渲染模板
        
        Args:
            template_name: 模板文件名 (如 'paper.html')
            context: 模板变量字典
            
        Returns:
            str: 渲染后的内容
        """
        template = self.env.get_template(template_name)
        return template.render(**context)
    
    def render_string(self, template_str: str, context: Dict[str, Any]) -> str:
        """
        直接渲染字符串模板
        
        Args:
            template_str: 模板字符串
            context: 模板变量
            
        Returns:
            str: 渲染结果
        """
        template = self.env.from_string(template_str)
        return template.render(**context)
