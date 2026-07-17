import matplotlib
matplotlib.use('Agg')  # 必须在 import pyplot 之前，确保 headless 环境（GitHub Actions）正常绘图
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.colors as mcolors
import matplotlib.dates as mdates
from matplotlib.patches import PathPatch
from matplotlib import font_manager
import os
import sys

class Plotter:
    """绘图辅助类 - 封装 Matplotlib 配置 (美化版)"""
    
    def __init__(self):
        self.figsize = (12, 5) # Slightly wider
        self.dpi = 120 # Higher DPI
        self.ratios = [2, 1] 
        
        # Style Config
        self.cjk_font_path, self.cjk_font_family = self._configure_cjk_font()
        self.cjk_font_ready = bool(self.cjk_font_path)
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.sans-serif'] = [
            self.cjk_font_family,
            'Noto Sans CJK SC',
            'Noto Sans CJK JP',
            'Microsoft YaHei',
            'WenQuanYi Micro Hei',
            'SimHei',
            'Arial Unicode MS',
            'DejaVu Sans',
        ]
        plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['lines.linewidth'] = 2.0
        
        self.colors = ['#E74C3C', '#3498DB', '#2ECC71', '#F1C40F', '#9B59B6'] # Flat UI Colors

    @staticmethod
    def _configure_cjk_font():
        """Register one concrete CJK font file instead of trusting family fallback.

        Matplotlib does not reliably fall back glyph-by-glyph. GitHub's
        ``fonts-noto-cjk`` package exposes a TTC whose reported family is often
        ``Noto Sans CJK JP`` even though it contains Simplified Chinese glyphs.
        Registering the file explicitly prevents production charts from being
        rendered with square placeholder glyphs.
        """
        candidates = [
            os.environ.get('PUSH_CJK_FONT_PATH', ''),
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf',
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
            r'C:\Windows\Fonts\msyh.ttc',
            r'C:\Windows\Fonts\msyhbd.ttc',
            '/System/Library/Fonts/PingFang.ttc',
        ]
        for candidate in candidates:
            path = str(candidate or '').strip()
            if not path or not os.path.isfile(path):
                continue
            try:
                font_manager.fontManager.addfont(path)
                family = font_manager.FontProperties(fname=path).get_name()
                return path, family
            except Exception:
                continue

        installed = {entry.name: entry.fname for entry in font_manager.fontManager.ttflist}
        for family in [
            'Noto Sans CJK SC',
            'Noto Sans CJK JP',
            'Microsoft YaHei',
            'WenQuanYi Micro Hei',
            'SimHei',
            'Arial Unicode MS',
        ]:
            path = installed.get(family, '')
            if path:
                return path, family
        return '', 'DejaVu Sans'
        
    def create_dual_axes(self):
        """创建双子图 (左长右短, 无间隙)"""
        fig, axes = plt.subplots(1, 2, figsize=self.figsize, dpi=self.dpi, 
                               gridspec_kw={'width_ratios': self.ratios, 'wspace': 0.05})
        return fig, axes

    def create_top_bottom_axes(self):
        """创建上下子图 (上长下短, 无间隙)"""
        fig, axes = plt.subplots(2, 1, figsize=(12, 8), dpi=self.dpi, 
                               gridspec_kw={'height_ratios': [2, 1], 'hspace': 0.1}, sharex=True)
        return fig, axes

    def create_single_ax(self):
        """创建单图"""
        fig, ax = plt.subplots(1, 1, figsize=self.figsize, dpi=self.dpi)
        return fig, ax

    def create_ratio_axes(self, ratios=[3, 1]):
        """创建上下双图（独立 X 轴；旧 3:1 请求按移动端等高呈现）。"""
        # The legacy 3:1 split wastes the lower half on a phone. Existing
        # finance indicators all use that legacy value, so render them 1:1
        # while preserving explicitly designed ratios such as [1, 1].
        effective_ratios = [1, 1] if ratios == [3, 1] else ratios
        fig, axes = plt.subplots(2, 1, figsize=(12, 15), dpi=self.dpi,
                               gridspec_kw={'height_ratios': effective_ratios, 'hspace': 0.24})
        return fig, axes

    def set_no_margins(self, ax):
        """去除左右空白"""
        ax.margins(x=0)

    def add_inset_plot(self, ax, rect=[0.1, 0.6, 0.35, 0.25]):
        """在主图中添加小图"""
        return ax.inset_axes(rect)

    def save(self, fig, path):
        """以透明背景保存并关闭，便于网页和小程序自行决定底色。"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fig.patch.set_alpha(0)
        for ax in fig.axes:
            ax.set_facecolor('none')
            legend = ax.get_legend()
            if legend:
                legend.get_frame().set_facecolor('none')
                legend.get_frame().set_edgecolor('none')
                legend.get_frame().set_alpha(0)
        try:
            # Add a small padding to prevent labels from being cut off
            plt.tight_layout(pad=2.0)
            fig.savefig(path, bbox_inches='tight', transparent=True, facecolor='none')
        except Exception as e:
            print(f"Save Warning: {e}")
            fig.savefig(path, transparent=True, facecolor='none')
        plt.close(fig)

    def _beautify(self, ax, data=None):
        """通用美化"""
        # Lighter grid
        ax.grid(True, linestyle='--', alpha=0.2, color='#bdc3c7')
        
        # Close the box (Show all spines)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color('#dfe6e9') # Lighter spines
            spine.set_linewidth(0.8)
            
        ax.tick_params(axis='both', which='both', colors='#636e72', labelsize=10)
        
        # Remove extra whitespace at the bottom
        ax.set_axisbelow(True) # Grid behind plots
        
        # Dynamic Y-axis scaling and Empty Data Safeguard
        is_empty = True
        if data is not None:
            try:
                import pandas as pd
                if isinstance(data, (list, tuple)):
                    # Handle None elements in list
                    data = [d for d in data if d is not None]
                    if data:
                        all_data = pd.concat([pd.to_numeric(d, errors='coerce') for d in data])
                    else:
                        all_data = pd.Series(dtype=float)
                else:
                    all_data = pd.to_numeric(data, errors='coerce')
                
                valid_data = all_data.dropna()
                if not valid_data.empty:
                    is_empty = False
                    d_min, d_max = valid_data.min(), valid_data.max()
                    if d_max == d_min:
                        padding = max(abs(float(d_min)) * 0.08, 0.5)
                        ax.set_ylim(d_min - padding, d_max + padding)
                    else:
                        diff = d_max - d_min
                        ax.set_ylim(d_min - diff * 0.12, d_max + diff * 0.12)
            except: pass
            
        if is_empty:
            # Add watermark for empty data
            ax.text(0.5, 0.5, '接口数据暂时缺失 / 数据处理中\n(Data Unavailable)', 
                    transform=ax.transAxes, fontsize=14, color='#7f8c8d', 
                    ha='center', va='center', alpha=0.5, weight='bold')

    def fill_gradient(self, ax, x, y, color='#273c75', alpha_top=0.3,
                      baseline=0, where=None, zorder=1):
        """绘制从基准线向数据线逐渐加深、且交叉处无白缝的渐变阴影。"""
        import numpy as np
        import pandas as pd

        x_values = np.asarray(mdates.date2num(pd.to_datetime(x)), dtype=float)
        y_values = np.asarray(pd.to_numeric(y, errors='coerce'), dtype=float)
        valid = np.isfinite(x_values) & np.isfinite(y_values)
        where_values = valid if where is None else np.asarray(where, dtype=bool) & valid
        if not where_values.any():
            return []

        collection = ax.fill_between(
            x_values, y_values, baseline, where=where_values,
            interpolate=True, facecolor='none', edgecolor='none', zorder=zorder,
        )
        rgb = mcolors.to_rgb(color)
        images = []
        for path in collection.get_paths():
            vertices = path.vertices
            if len(vertices) < 3:
                continue
            xmin, xmax = vertices[:, 0].min(), vertices[:, 0].max()
            ymin, ymax = vertices[:, 1].min(), vertices[:, 1].max()
            if not np.isfinite([xmin, xmax, ymin, ymax]).all() or xmax <= xmin or ymax <= ymin:
                continue
            levels = np.linspace(ymin, ymax, 256)
            span = max(abs(ymin - baseline), abs(ymax - baseline), 1e-12)
            # Ease-in keeps the area near the x/baseline visibly lighter on a
            # small phone screen, instead of looking like a flat solid block.
            alpha = np.power(np.clip(np.abs(levels - baseline) / span, 0, 1), 1.7) * alpha_top
            rgba = np.empty((256, 1, 4), dtype=float)
            rgba[:, :, :3] = rgb
            rgba[:, 0, 3] = alpha
            patch = PathPatch(path, facecolor='none', edgecolor='none')
            ax.add_patch(patch)
            images.append(ax.imshow(
                rgba, extent=(xmin, xmax, ymin, ymax), origin='lower',
                aspect='auto', interpolation='bicubic', zorder=zorder,
                clip_path=patch, clip_on=True,
            ))
        collection.remove()
        ax.update_datalim(np.column_stack([x_values[valid], y_values[valid]]))
        ax.autoscale_view()
        return images

    def fill_diverging_gradient(self, ax, x, y, baseline=0,
                                positive_color='#C94F45', negative_color='#3D8B68',
                                alpha_top=0.28, zorder=1):
        """按基准线上红、线下绿绘制连续渐变。"""
        import numpy as np
        import pandas as pd
        values = np.asarray(pd.to_numeric(y, errors='coerce'), dtype=float)
        finite = np.isfinite(values)
        return (
            self.fill_gradient(ax, x, values, positive_color, alpha_top, baseline,
                               finite & (values >= baseline), zorder)
            + self.fill_gradient(ax, x, values, negative_color, alpha_top, baseline,
                                 finite & (values <= baseline), zorder)
        )

    def _add_internal_title(self, ax, text):
        """Add title inside chart - moved to bottom left per user request"""
        if not text: return
        # Place at bottom-left to avoid blocking data
        ax.text(0.02, 0.05, text, transform=ax.transAxes, 
                fontsize=10, fontweight='bold', va='bottom', ha='left',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='none', alpha=0, edgecolor='none', linewidth=0))

    def fmt_twinx(self, fig, ax_left, ax_right, title='', ylabel_left='', ylabel_right='', rotation=15, 
                  data_left=None, data_right=None):
        """单图双轴格式化"""
        is_history_trend = '历史' in title or 'History' in title
        
        if is_history_trend:
            self._add_internal_title(ax_left, title)
        else:
            ax_left.set_title(title, fontsize=16, weight='bold', pad=15, color='#2d3436')

        self._beautify(ax_left, data_left)
        ax_left.set_ylabel(ylabel_left, fontsize=11, weight='bold', color='#2d3436')
        
        # Mirror y-axis formatting for right
        # self._beautify(ax_right, data_right) # Don't re-add grid
        ax_right.tick_params(axis='y', colors='#636e72', labelsize=10)
        for spine in ax_right.spines.values():
            spine.set_visible(True)
            spine.set_color('#dfe6e9')
            spine.set_linewidth(0.8)
        # The primary axis owns left/top/bottom. Drawing twin-axis spines on
        # top of them makes those sides darker than the right border.
        for side in ('left', 'top', 'bottom'):
            ax_right.spines[side].set_visible(False)
        if ylabel_right:
            ax_right.set_ylabel(ylabel_right, fontsize=11, weight='bold', color='#2d3436')
        ax_right.grid(False)
        self._pad_y_only(ax_right, data_right)
        
        # Force rotation
        for label in ax_left.get_xticklabels():
            label.set_rotation(rotation)
            label.set_ha('right')
        
        # Legends - loc='upper center' to avoid blocking curves, or 'best'
        h1, l1 = ax_left.get_legend_handles_labels()
        h2, l2 = ax_right.get_legend_handles_labels()
        if h1 or h2:
            legend = ax_left.legend(h1+h2, l1+l2, loc='best',
                         frameon=True, framealpha=0.8, fontsize=9, edgecolor='#dfe6e9')
            legend.get_frame().set_linewidth(0.5)


    def fmt_single(self, fig, ax, title='', xlabel='', ylabel='', sci_on=False, rotation=15, data=None):
        """单图格式化"""
        is_history_trend = '历史' in title or 'History' in title
        
        if is_history_trend:
             self._add_internal_title(ax, title)
        else:
             ax.set_title(title, fontsize=16, weight='bold', pad=10)
             
        self._beautify(ax, data)
        ax.set_ylabel(ylabel, fontsize=11, weight='bold')
        if xlabel: ax.set_xlabel(xlabel, fontsize=11, weight='bold')
        
        # Force rotation
        for label in ax.get_xticklabels():
            label.set_rotation(rotation)
            label.set_ha('right')
            
        # Legend (loc='best')
        h, l = ax.get_legend_handles_labels()
        if h:
             ax.legend(loc='best', frameon=True, framealpha=0.8, fontsize=9, 
                      edgecolor='#dfe6e9', fancybox=False)
        
        if sci_on:
             ax.ticklabel_format(style='sci', scilimits=(-1,2), axis='y')

    @staticmethod
    def _pad_y_only(ax, data):
        """Give a secondary y axis the same safe edge padding as the main axis."""
        import pandas as pd
        if data is None:
            return
        try:
            if isinstance(data, (list, tuple)):
                series = pd.concat([pd.to_numeric(item, errors='coerce') for item in data]).dropna()
            else:
                series = pd.to_numeric(data, errors='coerce').dropna()
            if series.empty:
                return
            d_min, d_max = float(series.min()), float(series.max())
            padding = max(abs(d_min) * 0.08, 0.5) if d_max == d_min else (d_max - d_min) * 0.12
            ax.set_ylim(d_min - padding, d_max + padding)
        except Exception:
            return

    def draw_current_line(self, val, ax, color):
        """绘制当前值虚线"""
        try:
            import pandas as pd
            if pd.isna(val) or val is None: return
            ax.axhline(y=val, color=color, linestyle='--', alpha=0.7, linewidth=1)
        except: pass

