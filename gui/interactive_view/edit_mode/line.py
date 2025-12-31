"""
直线工具：通过点击依次生成线段
- 前两个点击生成首条线段
- 随后每次点击与上一个点连线（第三个点连第二个，以此类推）
"""
from typing import Optional, List
import numpy as np
from PyQt5.QtCore import QPoint
import pyvista as pv

from model.geometry import Point


class LineOperator:
    """
    线操作器：管理基于已有点的连线逻辑
    点击仅选择已存在的点，不再新建点；连续两次点选即生成一条线段
    """

    def __init__(self, edit_mode_manager):
        self.edit_manager = edit_mode_manager
        # 记录已创建的点ID顺序，用于连续连线
        self._click_point_ids: List[str] = []
        # 记录用于曲线的控制点ID（按点击顺序）
        self._curve_control_point_ids: List[str] = []
        # 记录用于折线的控制点ID（按点击顺序）
        self._polyline_control_point_ids: List[str] = []

    # ========== 折线功能 ==========
    def handle_polyline_click(self, screen_pos: QPoint, view, finalize: bool = False) -> Optional[str]:
        """
        在折线模式下处理一次点击：
        - 左键点击：选择已有点并加入控制点列表
        - 右键/调用 finalize=True：结束控制点输入，生成折线
        返回生成的 polyline_id（如果生成），否则 None
        """
        try:
            pid = view.pick_point_at_screen(screen_pos, pixel_threshold=10)
        except Exception:
            pid = None

        if pid is None:
            # 如果是 finalize 请求且已有足够控制点（>=2）则生成折线
            if finalize and len(self._polyline_control_point_ids) >= 2:
                return self._generate_polyline_from_control_points(view)
            return None

        # 避免重复添加相同点（连续点击同一点）
        if not self._polyline_control_point_ids or self._polyline_control_point_ids[-1] != pid:
            self._polyline_control_point_ids.append(pid)
            # 视觉反馈：把控制点设为黄色以便识别
            self.edit_manager.set_point_color(pid, (1.0, 1.0, 0.0), view=view)
            # 状态消息

            if hasattr(view, 'status_message'):
                view.status_message.emit(f'Added polyline control point: {pid} ({len(self._polyline_control_point_ids)})')

        # 如果是 finalize 操作（例如右键），生成折线
        if finalize:
            if len(self._polyline_control_point_ids) >= 2:
                return self._generate_polyline_from_control_points(view)
            else:
                # 清空控制点并提示至少需要2个点
                if hasattr(view, 'status_message'):
                    view.status_message.emit('折线至少需要 2 个控制点')
                self._polyline_control_point_ids = []
                return None

        # 未生成折线，返回None
        return None

    def _generate_polyline_from_control_points(self, view) -> Optional[str]:
        """使用当前控制点生成折线并在 edit_manager 中创建"""
        control_ids = list(self._polyline_control_point_ids)
        # 清空控制点缓存（不管成功与否）
        self._polyline_control_point_ids = []
        if len(control_ids) < 2:
            return None

        # 生成唯一折线ID
        polyline_id = self._generate_polyline_id()
        if self.edit_manager.add_polyline(polyline_id, control_ids, view=view):
            if hasattr(view, 'status_message'):
                view.status_message.emit(f'创建折线成功: {polyline_id}')
            return polyline_id
        else:
            if hasattr(view, 'status_message'):
                view.status_message.emit('创建折线失败')
            return None

    def _generate_polyline_id(self) -> str:
        """生成唯一折线ID"""
        existing = set(self.edit_manager._polylines.keys())
        i = 0
        while True:
            pid = f"polyline_{i}"
            if pid not in existing:
                return pid
            i += 1
    # ========== 曲线功能 ==========
    def handle_curve_click(self, screen_pos: QPoint, view, finalize: bool = False) -> Optional[str]:
        """
        在曲线模式下处理一次点击：
        - 左键点击：选择已有点并加入控制点列表
        - 右键/调用 finalize=True：结束控制点输入，生成曲线（B-spline），并在场景中创建曲线点与线段
        返回生成的 curve_id（如果生成），否则 None
        """
        # 使用视图提供的公共屏幕点拾取函数
        try:
            pid = view.pick_point_at_screen(screen_pos, pixel_threshold=10)
        except Exception:
            pid = None

        if pid is None:
            # 如果是 finalize 请求且已有足够控制点（>=3）则生成曲线
            if finalize and len(self._curve_control_point_ids) >= 3:
                return self._generate_curve_from_control_points(view)
            return None
        # 避免重复添加相同点（连续点击同一点）
        if not self._curve_control_point_ids or self._curve_control_point_ids[-1] != pid:
            self._curve_control_point_ids.append(pid)
            # 视觉反馈：把控制点设为青色以便识别
            self.edit_manager.set_point_color(pid, (0.0, 1.0, 1.0), view=view)

            # 状态消息
            if hasattr(view, 'status_message'):
                view.status_message.emit(f'Added control point: {pid} ({len(self._curve_control_point_ids)})')


        # 如果是 finalize 操作（例如右键），生成曲线
        if finalize:
            if len(self._curve_control_point_ids) >= 3:
                return self._generate_curve_from_control_points(view)
            else:
                # 清空控制点并提示至少需要3个点
                try:
                    if hasattr(view, 'status_message'):
                        view.status_message.emit('曲线至少需要 3 个控制点')
                except Exception:
                    pass
                self._curve_control_point_ids = []
                return None

        # 未生成曲线，返回None
        return None


    def _generate_curve_from_control_points(self, view, degree: int = 3, num_points: int = 20) -> Optional[str]:
        """使用当前控制点生成曲线并在 edit_manager 中创建对应的点和线段"""
        control_ids = list(self._curve_control_point_ids)
        # 清空控制点缓存（不管成功与否）
        self._curve_control_point_ids = []
        if len(control_ids) < 2:
            return None

        # 准备控制点对象（model.geometry.Point）
        control_points = []
        for cid in control_ids:
            pobj = self.edit_manager._points.get(cid)
            if pobj is None:
                continue
            # pobj may already be a Point dataclass
            if isinstance(pobj, Point):
                control_points.append(pobj)
            else:
                control_points.append(Point(id=cid, position=np.array(pobj, dtype=np.float64)))

        if len(control_points) < 2:
            return None

        # 注册曲线元数据到 edit_manager，并渲染为单一曲线对象（不在 _points 中加入采样点）
        curve_id = self._generate_curve_id()
        try:
            self.edit_manager.add_curve(curve_id, control_ids, degree=degree, num_points=num_points, view=view)
            return curve_id
        except Exception:
            # 回退：如果 add_curve 不可用或失败，则使用简单折线方式在场景中建立线段（仍不创建采样点数据）
            try:
                # 生成折线：直接用控制点顺序创建一个 polyline 对象并渲染
                poly_id = f"{curve_id}_poly"
                self.edit_manager.add_polyline(poly_id, control_ids, view=view)
                return poly_id
            except Exception:
                return None
    
    # ========== 曲线生成算法 ==========
    
    def generate_smooth_curve(self, control_points: List[np.ndarray], degree: int, num_points: int) -> List[np.ndarray]:
        """生成平滑曲线点"""
        if len(control_points) == 2:
            # 只有两个点，直接返回直线
            return control_points
        
        # 使用 Catmull-Rom 样条或简化的 B 样条
        if len(control_points) >= 3:
            return self._catmull_rom_spline(control_points, num_points)
        else:
            # 回退到线性插值
            return self._linear_interpolation(control_points, num_points)
    
    def _catmull_rom_spline(self, points: List[np.ndarray], num_samples: int) -> List[np.ndarray]:
        """Catmull-Rom 样条插值"""
        if len(points) < 3:
            return self._linear_interpolation(points, num_samples)
        
        # 添加重复的端点以处理边界
        extended_points = [points[0]] + points + [points[-1]]
        
        curve_points = []
        n_segments = len(points) - 1
        
        for i in range(num_samples):
            t = i / (num_samples - 1) * n_segments
            segment = int(t)
            local_t = t - segment
            
            if segment >= n_segments:
                curve_points.append(points[-1])
                continue
            
            # Catmull-Rom 样条公式
            p0 = extended_points[segment]
            p1 = extended_points[segment + 1]
            p2 = extended_points[segment + 2]
            p3 = extended_points[segment + 3]
            
            t2 = local_t * local_t
            t3 = t2 * local_t
            
            point = 0.5 * (
                (2 * p1) +
                (-p0 + p2) * local_t +
                (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                (-p0 + 3 * p1 - 3 * p2 + p3) * t3
            )
            
            curve_points.append(point)
        
        return curve_points
    
    def _linear_interpolation(self, points: List[np.ndarray], num_samples: int) -> List[np.ndarray]:
        """线性插值"""
        if len(points) < 2:
            return points
        
        curve_points = []
        total_length = 0
        segment_lengths = []
        
        # 计算每段长度
        for i in range(len(points) - 1):
            length = np.linalg.norm(points[i + 1] - points[i])
            segment_lengths.append(length)
            total_length += length
        
        # 按长度比例采样
        for i in range(num_samples):
            t = i / (num_samples - 1) if num_samples > 1 else 0
            target_length = t * total_length
            
            current_length = 0
            for j, seg_length in enumerate(segment_lengths):
                if current_length + seg_length >= target_length:
                    # 在这一段内
                    local_t = (target_length - current_length) / seg_length if seg_length > 0 else 0
                    point = points[j] + local_t * (points[j + 1] - points[j])
                    curve_points.append(point)
                    break
                current_length += seg_length
            else:
                curve_points.append(points[-1])
        
        return curve_points
    
    def render_curve_mesh(self, curve_points: List[np.ndarray], curve_id: str, view, color=None):
        """渲染曲线网格"""
        if len(curve_points) < 2:
            return None
        
        line_mesh = pv.lines_from_points(np.array(curve_points))
        if color is None:
            color = self.edit_manager._line_colors.get(curve_id, (0.0, 1.0, 1.0))
        
        actor = view.add_mesh(line_mesh, color=color, line_width=3, name=f'curve_{curve_id}')
        return actor

    def _generate_curve_id(self) -> str:
        """生成唯一曲线ID"""
        existing = set(self.edit_manager._curves.keys())
        # also consider existing curve segment prefixes
        i = 0
        while True:
            cid = f"curve_{i}"
            # ensure no segment of same prefix exists
            conflict = any(k.startswith(cid) for k in existing)
            if not conflict:
                return cid
            i += 1

