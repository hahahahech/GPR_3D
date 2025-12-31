"""
拉伸工具（占位实现）
使用 img/拉伸.png 作为图标，由工具栏创建按钮后激活。
当前实现：点击画布选择点并在状态栏显示被选中的点（占位逻辑，后续可扩展为真正的拉伸操作）。
"""
from typing import Optional
import numpy as np
from PyQt5.QtCore import QPoint


class StretchOperator:
    """拉伸操作器（占位）"""

    def __init__(self, edit_mode_manager):
        self.edit_manager = edit_mode_manager
        self._active_point_id: Optional[str] = None

    def handle_click(self, screen_pos: QPoint, view) -> Optional[str]:
        """
        处理一次点击：尝试拾取点并设置为当前活动点（仅作可视化/占位）。
        返回被选中点的 id（如无则返回 None）。
        """
        try:
            # 使用 view 的屏幕点拾取辅助函数（若存在）
            if hasattr(view, "pick_point_at_screen"):
                pid = view.pick_point_at_screen(screen_pos, pixel_threshold=10)
            else:
                pid = None
        except Exception:
            pid = None

        if pid is None:
            # 尝试使用 edit_manager 的选择回退（世界投影/射线等）
            try:
                selected = self.edit_manager.select_at_screen_position(screen_pos, view, pixel_threshold=10)
                if selected and selected.get('type') == 'point':
                    pid = selected.get('id')
            except Exception:
                pid = None

        if pid is None:
            try:
                if hasattr(view, 'status_message'):
                    view.status_message.emit('未拾取到点以执行拉伸')
            except Exception:
                pass
            return None

        # 标记为活动点并给出提示（后续可在拖拽时对该点执行拉伸）
        self._active_point_id = pid
        try:
            if hasattr(view, 'status_message'):
                view.status_message.emit(f'已选中用于拉伸的点: {pid}')
        except Exception:
            pass
        return pid

    def reset(self):
        """重置活动状态"""
        self._active_point_id = None


