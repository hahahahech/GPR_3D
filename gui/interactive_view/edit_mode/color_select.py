"""
颜色选择工具：在编辑模式下为点/线/面设置颜色
"""
from typing import Optional, Dict, Any
from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import QColorDialog


class ColorSelector:
    """
    颜色选择器：点击对象弹出颜色选择器并应用到点/线/面
    """

    def __init__(self, edit_mode_manager):
        self.edit_manager = edit_mode_manager

    def handle_click(self, screen_pos: QPoint, view) -> Optional[Dict[str, Any]]:
        """
        屏幕点击：选中对象并弹出颜色对话框
        """
        selected = self.edit_manager.select_at_screen_position(screen_pos, view, pixel_threshold=10)
        if selected is None:
            return None

        color = QColorDialog.getColor(parent=view)
        if not color.isValid():
            return None

        r, g, b, _ = color.getRgbF()
        rgb = (float(r), float(g), float(b))
        obj_type = selected['type']
        obj_id = selected['id']

        if obj_type == 'point':
            self.edit_manager.set_point_color(obj_id, rgb, view)
        elif obj_type == 'line':
            self.edit_manager.set_line_color(obj_id, rgb, view)
        elif obj_type == 'plane':
            self.edit_manager.set_plane_color(obj_id, rgb, view)
        else:
            return None

        if hasattr(view, 'status_message'):
            view.status_message.emit(f"已设置{obj_type}颜色: {obj_id}")

        return {'type': obj_type, 'id': obj_id, 'color': rgb}

