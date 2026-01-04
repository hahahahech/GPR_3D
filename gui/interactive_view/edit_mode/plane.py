"""
平面工具：通过选取已存在的线段或同一平面上的点生成面
- 线段模式：依次点击线段（不新建），至少3条且首尾闭合后生成面，可自动反转方向
- 点模式：依次点击同一平面上的点（不新建），至少3点自动排序生成面
"""
from typing import Optional, List
import numpy as np
from PyQt5.QtCore import QPoint
from model.geometry import Plane


class PlaneOperator:
    """
    平面操作器：基于已有线段或点生成面
    """

    def __init__(self, edit_mode_manager):
        self.edit_manager = edit_mode_manager
        self._selected_line_ids: List[str] = []
        self._selected_point_ids: List[str] = []

    def reset(self):
        """清空当前选中的线段/点列表"""
        self._selected_line_ids = []
        self._selected_point_ids = []

    def add_selection(self, screen_pos: QPoint, view) -> bool:
        """
        左键点击：选中点或线并添加到选中列表
        Returns: 是否成功添加
        """
        selected = self.edit_manager.select_at_screen_position(
            screen_pos, view, pixel_threshold=10
        )
        if selected is None:
            return False

        sel_type = selected.get('type')
        if sel_type == 'line':
            line_id = selected['id']
            if line_id in self._selected_line_ids:
                if hasattr(view, 'status_message'):
                    view.status_message.emit(f'线 {line_id} 已选中')
                return False
            self._selected_line_ids.append(line_id)
            if hasattr(view, 'status_message'):
                view.status_message.emit(f'已选中线: {line_id} (总计 {len(self._selected_line_ids)} 条线)')
            return True
        elif sel_type == 'point':
            point_id = selected['id']
            if point_id in self._selected_point_ids:
                if hasattr(view, 'status_message'):
                    view.status_message.emit(f'点 {point_id} 已选中')
                return False
            self._selected_point_ids.append(point_id)
            if hasattr(view, 'status_message'):
                view.status_message.emit(f'已选中点: {point_id} (总计 {len(self._selected_point_ids)} 个点)')
            return True
        else:
            return False
    
    def finalize_plane(self, view) -> Optional[str]:
        """
        右键点击：根据已选中的点/线生成面
        Returns: 创建的面ID（若成功），否则 None
        """
        # 先尝试线段闭合
        if len(self._selected_line_ids) >= 3:
            vertices = self._build_polygon_vertices(self._selected_line_ids)
            if vertices is not None and vertices.shape[0] >= 3:
                plane_id = self._generate_plane_id()
                plane_obj = Plane(id=plane_id, vertices=vertices)
                if self.edit_manager.add_plane(plane_id, plane_obj.vertices, view, color=plane_obj.color):
                    if hasattr(view, 'status_message'):
                        view.status_message.emit(f'已生成面(线): {plane_id}')
                    self.reset()
                    return plane_id
                else:
                    if hasattr(view, 'status_message'):
                        view.status_message.emit('生成面失败')
                    return None

        # 再尝试点集生成
        if len(self._selected_point_ids) >= 3:
            vertices = self._build_polygon_from_points(self._selected_point_ids)
            if vertices is not None and vertices.shape[0] >= 3:
                plane_id = self._generate_plane_id()
                plane_obj = Plane(id=plane_id, vertices=vertices)
                if self.edit_manager.add_plane(plane_id, plane_obj.vertices, view, color=plane_obj.color):
                    if hasattr(view, 'status_message'):
                        view.status_message.emit(f'已生成面(点): {plane_id}')
                    self.reset()
                    return plane_id
                else:
                    if hasattr(view, 'status_message'):
                        view.status_message.emit('生成面失败')
                    return None
        
        # 选中的点/线不足
        if hasattr(view, 'status_message'):
            view.status_message.emit(f'需要至少3条线户63个点才能生成面 (当前: {len(self._selected_line_ids)}线, {len(self._selected_point_ids)}点)')
        return None

    # ========== 帮助方法 ==========
    def _build_polygon_vertices(self, line_ids: List[str], tol: float = 1e-4) -> Optional[np.ndarray]:
        """
        根据线段ID顺序尝试构建闭合多边形顶点序列。
        要求：相邻线段首尾相接；最后一个端点需回到起点。
        自动对线段方向做反转以匹配。
        """
        if not line_ids:
            return None

        lines = []
        for lid in line_ids:
            if lid not in self.edit_manager._lines:
                return None
            start, end = self.edit_manager._lines[lid]
            # resolve if stored as point ids
            try:
                if isinstance(start, str):
                    start = self.edit_manager._points[start].position
                if isinstance(end, str):
                    end = self.edit_manager._points[end].position
            except Exception:
                # fallback: assume arrays
                start = np.array(start, dtype=np.float64)
                end = np.array(end, dtype=np.float64)
            lines.append((start, end))

        # 初始化顶点序列
        vertices = [lines[0][0].copy(), lines[0][1].copy()]
        current_end = lines[0][1]

        for start, end in lines[1:]:
            if np.allclose(start, current_end, atol=tol):
                vertices.append(end.copy())
                current_end = end
            elif np.allclose(end, current_end, atol=tol):
                # 反转线方向
                vertices.append(start.copy())
                current_end = start
            else:
                return None  # 无法连续首尾相接

        # 闭合性检查
        if not np.allclose(vertices[-1], vertices[0], atol=tol):
            return None

        # 去掉重复的最后一个点
        vertices = vertices[:-1]

        # 确保至少3个顶点
        if len(vertices) < 3:
            return None

        return np.array(vertices, dtype=np.float64)

    def _build_polygon_from_points(self, point_ids: List[str], tol: float = 1e-5) -> Optional[np.ndarray]:
        """
        根据同一平面上的点生成有序多边形顶点
        """
        points = []
        for pid in point_ids:
            p = self.edit_manager._points.get(pid)
            if p is None:
                return None
            pos = p.position
            # 去重
            if any(np.allclose(pos, q, atol=tol) for q in points):
                continue
            points.append(pos)

        if len(points) < 3:
            return None

        pts = np.vstack(points)

        # 计算法向和投影基
        centroid = pts.mean(axis=0)
        pts_centered = pts - centroid
        try:
            _, _, vh = np.linalg.svd(pts_centered)
            normal = vh[-1]
        except Exception:
            return None

        if np.linalg.norm(normal) < 1e-8:
            return None
        normal = normal / np.linalg.norm(normal)

        # 构造平面基向量
        ref = np.array([1.0, 0.0, 0.0]) if abs(normal[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        u = np.cross(normal, ref)
        u_norm = np.linalg.norm(u)
        if u_norm < 1e-8:
            return None
        u = u / u_norm
        v = np.cross(normal, u)

        # 投影到 2D
        pts_2d = np.column_stack((np.dot(pts_centered, u), np.dot(pts_centered, v)))
        angles = np.arctan2(pts_2d[:, 1], pts_2d[:, 0])
        order = np.argsort(angles)
        ordered_pts = pts[order]

        if ordered_pts.shape[0] < 3:
            return None

        return ordered_pts.astype(np.float64)

    def _generate_plane_id(self) -> str:
        existing = set(self.edit_manager._planes.keys())
        i = 0
        while True:
            pid = f"plane_{i}"
            if pid not in existing:
                return pid
            i += 1

