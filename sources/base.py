"""
Base Source - Common functionality for all sources
"""
import logging
from core import SourceInterface, Message
from core.template import TemplateEngine


class BaseSource(SourceInterface):
    """数据源基类 - 提供通用能力"""
    
    def __init__(self, **kwargs):
        self.template_engine = TemplateEngine()
        self.logger = logging.getLogger(f'Push.Source.{self.__class__.__name__}')
        self.force = kwargs.get('force', False)
    
    def render_template(self, template_name: str, context: dict) -> str:
        """
        渲染模板helper
        
        Args:
            template_name: 模板文件名
            context: 上下文变量
            
        Returns:
            str: 渲染结果
        """
        return self.template_engine.render(template_name, context)
