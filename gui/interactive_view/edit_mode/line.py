"""
直线工具：通过点击依次生成线段
- 前两个点击生成首条线段
- 随后每次点击与上一个点连线（第三个点连第二个，以此类推）
"""
from typing import Optional, List
import numpy as np
from PyQt5.QtCore import QPoint

from ..coordinates import CoordinateConverter
from model.geometry import Point, Line


class LineOperator:
    """
    线操作器：管理基于已有点的连线逻辑
    点击仅选择已存在的点，不再新建点；连续两次点选即生成一条线段
    """

    def __init__(self, edit_mode_manager):
        self.edit_manager = edit_mode_manager
        # 记录已创建的点ID顺序，用于连续连线
        self._click_point_ids: List[str] = []

    def reset(self):
        """清空当前连线状态（不删除已生成的线）"""
        self._click_point_ids = []

    def handle_click(self, screen_pos: QPoint, view) -> Optional[str]:
        """
        处理一次屏幕点击：
        1) 在屏幕空间选中已有点（不创建新点）
        2) 当累计 >=2 个点时创建一条线段，连接最近两次选中的点
        Returns: 创建的线ID（若本次点击生成了新线），否则 None
        """
        # 仅选择已有点
        selected = self.edit_manager.select_at_screen_position(screen_pos, view, pixel_threshold=10)
        if selected is None or selected.get('type') != 'point':
            return None

        point_id = selected['id']

        # 记录点击顺序
        self._click_point_ids.append(point_id)

        # 当有两个以上点击时，连接最近两个点成线段
        if len(self._click_point_ids) >= 2:
            p1_id = self._click_point_ids[-2]
            p2_id = self._click_point_ids[-1]
            if p1_id == p2_id:
                return None

            if p1_id not in self.edit_manager._points or p2_id not in self.edit_manager._points:
                return None

            p1 = self.edit_manager._points[p1_id].position
            p2 = self.edit_manager._points[p2_id].position

            line_id = self._generate_line_id()
            if self.edit_manager.add_line(line_id, p1, p2, view):
                return line_id
        return None

    # ========== ID 生成 ==========
    def _generate_line_id(self) -> str:
        existing = set(self.edit_manager._lines.keys())
        i = 0
        while True:
            lid = f"line_{i}"
            if lid not in existing:
                return lid
            i += 1

