"""
场景面板（对象管理器）
显示已创建的点、线、面，按层级组织并支持多选复选框控制可见性。
"""
from PyQt5.QtWidgets import QWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QCheckBox, \
    QLabel, QHBoxLayout, QPushButton, QDoubleSpinBox, QMenu, QAction, QDialog, QDialogButtonBox, QHeaderView
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
import numpy as np
from utils.undo import MovePointCommand, RemovePointCommand, RemoveLineCommand, RemovePolylineCommand, RemoveCurveCommand, RemovePlaneCommand
from gui.dialog import CoordinateInputDialog
from gui.interactive_view.camera import CameraController
from model.geometry import Plane

class SceneInspector(QWidget):
    """
    右侧停靠面板，用于展示场景中的点/线/面。
    使用方法：实例化后将该 widget 放入 QDockWidget。
    """
    def __init__(self, view, parent=None):
        """
        Parameters:
        -----------
        view : InteractiveView
            视图实例（包含 _edit_mode_manager）
        parent : QWidget, optional
        """
        super().__init__(parent)
        self.view = view
        self.edit_manager = getattr(view, '_edit_mode_manager', None)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(2)
        # 设置列宽模式：第一列拉伸占据空间，第二列固定宽度靠右
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.tree)

        # 编辑器：用于修改点坐标（默认隐藏，只有选中点时显示）
        # 布局为两行：第一行 X/Y，第二行 Z/应用 按钮
        self._x_spin = QDoubleSpinBox()
        self._y_spin = QDoubleSpinBox()
        self._z_spin = QDoubleSpinBox()
        for s in (self._x_spin, self._y_spin, self._z_spin):
            s.setRange(-1e6, 1e6)
            s.setDecimals(1)
            s.setSingleStep(0.1)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("X:"))
        row1.addWidget(self._x_spin)
        row1.addWidget(QLabel("Y:"))
        row1.addWidget(self._y_spin)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Z:"))
        row2.addWidget(self._z_spin)
        self._apply_btn = QPushButton("应用")
        self._apply_btn.setEnabled(False)
        row2.addWidget(self._apply_btn)

        editor_container = QVBoxLayout()
        editor_container.addLayout(row1)
        editor_container.addLayout(row2)
        layout.addLayout(editor_container)

        # 限制面板宽度，稍微减小一点
        try:
            self.setMaximumWidth(220)
        except Exception:
            pass

        # 当前正在编辑的点ID
        self._editing_point_id = None
        # 当前选中视觉高亮信息
        self._prev_selected = None  # {'type': 'point'|'line'|'plane', 'id': str, 'color': (r,g,b)}

        # highlight tracking: (type, id, original_color)
        self._last_highlight = None

        # 连接编辑器事件
        self._apply_btn.clicked.connect(self._apply_point_edit)
        # 响应树项选择以填充编辑器
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)

        # 缓存mapping：使用 id(item) 映射到 meta 和保存 item 引用
        self._item_meta = {}   # id(item) -> {'type':..., 'id':...}
        self._item_refs = {}   # id(item) -> item

        # 使用事件驱动刷新：绑定 InteractiveView 的 view_changed 信号触发刷新
        try:
            if hasattr(self.view, 'view_changed'):
                self.view.view_changed.connect(self.refresh)
            if hasattr(self.view, 'status_message'):
                self.view.status_message.connect(lambda *_: self.refresh())
        except Exception:
            pass

        # 初始刷新
        self.refresh()
    
    # ========== 辅助函数 ==========
    def _find_point_ids_by_pos(self, pos, points):
        """根据位置查找点ID（使用 allclose）"""
        res = []
        for pid, pobj in points.items():
            try:
                ppos = pobj.position
            except Exception:
                ppos = pobj
            if np.allclose(ppos, pos, atol=1e-4):
                res.append(pid)
        return res
    
    def _is_boundary_id(self, pid):
        """判断是否为边界点ID"""
        return isinstance(pid, str) and pid.startswith("boundary_")
    
    def _line_to_point_ids(self, start, end, points):
        """线端点 -> 点ID（可能返回多个匹配；选择第一个）"""
        # 如果 start/end 存储为点ID，直接返回
        pid1 = None
        pid2 = None
        if isinstance(start, str):
            pid1 = start if start in points else None
        else:
            p1 = self._find_point_ids_by_pos(start, points)
            pid1 = p1[0] if p1 else None
        if isinstance(end, str):
            pid2 = end if end in points else None
        else:
            p2 = self._find_point_ids_by_pos(end, points)
            pid2 = p2[0] if p2 else None
        return pid1, pid2
    
    def _line_in_any_plane(self, start, end, planes):
        """判断给定线段（start,end）是否属于任何面"""
        # 解析 start/end 如果它们是点ID
        try:
            if isinstance(start, str):
                start_pos = self.edit_manager._points[start].position
            else:
                start_pos = start
        except Exception:
            start_pos = np.array(start, dtype=np.float64)
        try:
            if isinstance(end, str):
                end_pos = self.edit_manager._points[end].position
            else:
                end_pos = end
        except Exception:
            end_pos = np.array(end, dtype=np.float64)

        for verts in planes.values():
            n = verts.shape[0]
            for i in range(n):
                a = verts[i]
                b = verts[(i + 1) % n]
                if (np.allclose(a, start_pos, atol=1e-4) and np.allclose(b, end_pos, atol=1e-4)) or \
                   (np.allclose(a, end_pos, atol=1e-4) and np.allclose(b, start_pos, atol=1e-4)):
                    return True
        return False
    
    # ========== 主要刷新逻辑 ==========
    def refresh(self):
        """从 edit_manager 中读取数据并重建树结构"""
        if self.edit_manager is None:
            return
        # 如果用户正在与面板交互（鼠标悬停或面板有焦点），跳过自动刷新以避免折叠/闪烁
        try:
            if self.tree.hasFocus() or self.tree.underMouse():
                return
        except Exception:
            pass

        # 保存当前选中状态（checked）以及展开状态以便重建后恢复状态
        checked_ids = set()
        expanded_ids = set()
        for item_id, meta in list(self._item_meta.items()):
            try:
                item = self._item_refs.get(item_id)
                if item is not None:
                    if item.checkState(0) == Qt.Checked:
                        checked_ids.add((meta['type'], meta['id']))
                    if item.isExpanded():
                        expanded_ids.add((meta['type'], meta['id']))
            except Exception:
                pass

        # 避免重复连接信号
        try:
            self.tree.itemChanged.disconnect(self._on_item_changed)
        except Exception:
            pass
        self.tree.clear()
        self._item_meta.clear()
        self._item_refs.clear()

        # 计算点/线/面关系
        points = self.edit_manager._points  # id -> Point
        lines = self.edit_manager._lines    # id -> (start, end)
        planes = self.edit_manager._planes  # id -> vertices

        # 顶层：点分组（只显示游离点）
        points_root = QTreeWidgetItem(self.tree)
        points_root.setText(0, "点")
        points_root.setFlags(points_root.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
        points_root.setCheckState(0, Qt.Unchecked)
        rid = id(points_root)
        self._item_refs[rid] = points_root
        self._item_meta[rid] = {'type': 'group', 'id': 'points'}
        if ('group', 'points') in expanded_ids:
            points_root.setExpanded(True)
        
        # 在"点"分组旁添加"增加"按钮
        self._add_point_button_to_tree(points_root)

        # 标记所有点是否被某条折线/线段/曲线或面使用（用于在点分组中只显示游离点）
        used_point_ids = set()
        # 先收集显式折线和曲线的控制点
        polylines_explicit = getattr(self.edit_manager, '_polylines', {}) or {}
        for plid, polyline_data in polylines_explicit.items():
            # 适配新的数据结构
            if isinstance(polyline_data, dict) and 'point_ids' in polyline_data:
                pids = polyline_data['point_ids']
            else:
                pids = polyline_data  # 旧格式，直接是点ID列表
            
            for pid in pids:
                used_point_ids.add(pid)
        curves_meta = getattr(self.edit_manager, '_curves', {}) or {}
        for cid, meta in curves_meta.items():
            for pid in meta.get('control_point_ids', []):
                used_point_ids.add(pid)
        # 其次，收集散落的单段线中涉及的点，将它们也视为已被使用
        for lid, (s, e) in lines.items():
            p1, p2 = self._line_to_point_ids(s, e, points)
            if p1:
                used_point_ids.add(p1)
            if p2:
                used_point_ids.add(p2)
        # 面顶点中使用的点
        for verts in planes.values():
            for v in verts:
                pids = self._find_point_ids_by_pos(v, points)
                for pid in pids:
                    used_point_ids.add(pid)
        # 隐藏系统边界点
        for pid in list(points.keys()):
            if isinstance(pid, str) and pid.startswith("boundary_"):
                used_point_ids.add(pid)
        # 隐藏曲线采样生成的样本点（id 模式中包含 "_curve_point_"）
        for pid in list(points.keys()):
            if isinstance(pid, str) and "_curve_point_" in pid:
                used_point_ids.add(pid)

        # 只添加游离点（跳过边界点）
        for pid in sorted(points.keys()):
            if self._is_boundary_id(pid):
                continue
            if pid in used_point_ids:
                continue
            item = QTreeWidgetItem(points_root)
            item.setText(0, pid)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Checked if pid in self.edit_manager._point_actors else Qt.Unchecked)
            iid = id(item)
            self._item_refs[iid] = item
            self._item_meta[iid] = {'type': 'point', 'id': pid}
            # 恢复展开/勾选状态
            if ('point', pid) in checked_ids:
                item.setCheckState(0, Qt.Checked)
            if ('point', pid) in expanded_ids:
                item.setExpanded(True)
            # 通过树项变化信号连接状态变化（在下面处理）

        # 线分组根节点（只显示未组成面的线以避免重复）
        lines_root = QTreeWidgetItem(self.tree)
        lines_root.setText(0, "折线")
        lines_root.setFlags(lines_root.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
        lines_root.setCheckState(0, Qt.Unchecked)
        rid = id(lines_root)
        self._item_refs[rid] = lines_root
        self._item_meta[rid] = {'type': 'group', 'id': 'lines'}
        if ('group', 'lines') in expanded_ids:
            lines_root.setExpanded(True)

        # 使用折线（显式或由单段线合并而成）展示连续线对象（每个折线包含若干点）
        polylines_effective = {}
        # 显式折线优先并记录已包含的边以避免重复；过滤边界点
        polylines_explicit = getattr(self.edit_manager, '_polylines', {}) or {}
        included_edges = set()
        for plid, polyline_data in polylines_explicit.items():
            # 适配新的数据结构
            if isinstance(polyline_data, dict) and 'point_ids' in polyline_data:
                pids = polyline_data['point_ids']
            else:
                pids = polyline_data  # 旧格式，直接是点ID列表
            
            filtered = [pid for pid in pids if not self._is_boundary_id(pid)]
            if len(filtered) < 2:
                continue
            polylines_effective[plid] = list(filtered)
            for i in range(len(filtered) - 1):
                a, b = filtered[i], filtered[i+1]
                included_edges.add(frozenset((a, b)))
        # 其次，从单段线中构建连通折线（跳过已包含的边）
        # 从剩余线字典构建邻接表（解析为点ID）
        adj = {}
        for lid, (s, e) in lines.items():
            # 完全跳过边界线
            if isinstance(lid, str) and lid.startswith("boundary_line_"):
                continue
            p1, p2 = self._line_to_point_ids(s, e, points)
            if p1 is None or p2 is None:
                continue
            # 跳过接触边界点的边
            if self._is_boundary_id(p1) or self._is_boundary_id(p2):
                continue
            edge = frozenset((p1, p2))
            if edge in included_edges:
                continue
            adj.setdefault(p1, set()).add(p2)
            adj.setdefault(p2, set()).add(p1)
        # 查找连通分量并将它们排序为路径
        visited = set()
        group_idx = 0
        for node in list(adj.keys()):
            if node in visited:
                continue
            # BFS 收集分量
            comp_nodes = []
            stack = [node]
            while stack:
                n = stack.pop()
                if n in visited:
                    continue
                visited.add(n)
                comp_nodes.append(n)
                for nb in adj.get(n, []):
                    if nb not in visited:
                        stack.append(nb)
            # 如果可能，沿路径排序节点（优先选择度为1的端点）
            ends = [n for n in comp_nodes if len(adj.get(n, [])) == 1]
            ordered = []
            if len(ends) >= 1:
                start = ends[0]
                ordered = [start]
                prev = None
                cur = start
                while True:
                    neighbors = [x for x in adj.get(cur, []) if x != prev]
                    if not neighbors:
                        break
                    nxt = neighbors[0]
                    ordered.append(nxt)
                    prev, cur = cur, nxt
            else:
                # 环形或孤立，直接列出分量节点
                ordered = comp_nodes
            polylines_effective[f"poly_from_lines_{group_idx}"] = ordered
            group_idx += 1

        for plid in sorted(polylines_effective.keys()):
            item = QTreeWidgetItem(lines_root)
            item.setText(0, plid)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsTristate)
            checked = Qt.Checked if plid in getattr(self.edit_manager, '_polyline_actors', {}) else Qt.Unchecked
            item.setCheckState(0, checked)
            iid = id(item)
            self._item_refs[iid] = item
            self._item_meta[iid] = {'type': 'polyline', 'id': plid}
            if ('polyline', plid) in checked_ids:
                item.setCheckState(0, Qt.Checked)
            if ('polyline', plid) in expanded_ids:
                item.setExpanded(True)
            # 子项：组成点（按顺序）
            for pid in polylines_effective[plid]:
                child = QTreeWidgetItem(item)
                child.setText(0, pid)
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Checked if pid in self.edit_manager._point_actors else Qt.Unchecked)
                cid = id(child)
                self._item_refs[cid] = child
                self._item_meta[cid] = {'type': 'point', 'id': pid}
                if ('point', pid) in checked_ids:
                    child.setCheckState(0, Qt.Checked)
                if ('point', pid) in expanded_ids:
                    child.setExpanded(True)

        # 曲线根节点（显示曲线对象，但子项仅显示控制点）
        curves_root = QTreeWidgetItem(self.tree)
        curves_root.setText(0, "曲线")
        curves_root.setFlags(curves_root.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
        curves_root.setCheckState(0, Qt.Unchecked)
        rid = id(curves_root)
        self._item_refs[rid] = curves_root
        self._item_meta[rid] = {'type': 'group', 'id': 'curves'}
        if ('group', 'curves') in expanded_ids:
            curves_root.setExpanded(True)

        curves_meta = getattr(self.edit_manager, '_curves', {})
        for cid in sorted(curves_meta.keys()):
            item = QTreeWidgetItem(curves_root)
            item.setText(0, cid)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsTristate)
            checked = Qt.Checked if cid in getattr(self.edit_manager, '_curve_actors', {}) else Qt.Unchecked
            item.setCheckState(0, checked)
            iid = id(item)
            self._item_refs[iid] = item
            self._item_meta[iid] = {'type': 'curve', 'id': cid}
            if ('curve', cid) in checked_ids:
                item.setCheckState(0, Qt.Checked)
            if ('curve', cid) in expanded_ids:
                item.setExpanded(True)
            # 子项：控制点
            curve_data = curves_meta[cid]
            control_point_ids = curve_data.get('control_point_ids', []) if isinstance(curve_data, dict) else []
            for pid in control_point_ids:
                child = QTreeWidgetItem(item)
                child.setText(0, pid)
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Checked if pid in self.edit_manager._point_actors else Qt.Unchecked)
                cid2 = id(child)
                self._item_refs[cid2] = child
                self._item_meta[cid2] = {'type': 'point', 'id': pid}
                if ('point', pid) in checked_ids:
                    child.setCheckState(0, Qt.Checked)
                if ('point', pid) in expanded_ids:
                    child.setExpanded(True)

        # 面根节点
        planes_root = QTreeWidgetItem(self.tree)
        planes_root.setText(0, "面")
        planes_root.setFlags(planes_root.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
        planes_root.setCheckState(0, Qt.Unchecked)
        rid = id(planes_root)
        self._item_refs[rid] = planes_root
        self._item_meta[rid] = {'type': 'group', 'id': 'planes'}
        if ('group', 'planes') in expanded_ids:
            planes_root.setExpanded(True)

        for pid in sorted(planes.keys()):
            verts = planes[pid]
            item = QTreeWidgetItem(planes_root)
            item.setText(0, pid)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsTristate)
            item.setCheckState(0, Qt.Checked if pid in self.edit_manager._plane_actors else Qt.Unchecked)
            iid = id(item)
            self._item_refs[iid] = item
            self._item_meta[iid] = {'type': 'plane', 'id': pid}
            if ('plane', pid) in checked_ids:
                item.setCheckState(0, Qt.Checked)
            if ('plane', pid) in expanded_ids:
                item.setExpanded(True)

            # 找到构成该面的线（通过顶点对匹配）
            n = verts.shape[0]
            for i in range(n):
                a = verts[i]
                b = verts[(i + 1) % n]
                # 查找匹配的线ID
                found_lid = None
                for lid, (s, e) in lines.items():
                    # 如果 s/e 是点ID，解析为位置
                    try:
                        s_pos = self.edit_manager._points[s].position if isinstance(s, str) else s
                    except Exception:
                        s_pos = np.array(s, dtype=np.float64)
                    try:
                        e_pos = self.edit_manager._points[e].position if isinstance(e, str) else e
                    except Exception:
                        e_pos = np.array(e, dtype=np.float64)
                    if (np.allclose(s_pos, a, atol=1e-4) and np.allclose(e_pos, b, atol=1e-4)) or \
                       (np.allclose(s_pos, b, atol=1e-4) and np.allclose(e_pos, a, atol=1e-4)):
                        found_lid = lid
                        break
                if found_lid is not None:
                    line_item = QTreeWidgetItem(item)
                    line_item.setText(0, found_lid)
                    line_item.setFlags(line_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsTristate)
                    line_item.setCheckState(0, Qt.Checked if found_lid in self.edit_manager._line_actors else Qt.Unchecked)
                    lidid = id(line_item)
                    self._item_refs[lidid] = line_item
                    self._item_meta[lidid] = {'type': 'line', 'id': found_lid}
                    if ('line', found_lid) in checked_ids:
                        line_item.setCheckState(0, Qt.Checked)
                    if ('line', found_lid) in expanded_ids:
                        line_item.setExpanded(True)
                    # 在线下添加点
                    p1id, p2id = self._line_to_point_ids(*lines[found_lid], points)
                    if p1id:
                        ch = QTreeWidgetItem(line_item)
                        ch.setText(0, p1id)
                        ch.setFlags(ch.flags() | Qt.ItemIsUserCheckable)
                        ch.setCheckState(0, Qt.Checked if p1id in self.edit_manager._point_actors else Qt.Unchecked)
                        cid = id(ch)
                        self._item_refs[cid] = ch
                        self._item_meta[cid] = {'type': 'point', 'id': p1id}
                        if ('point', p1id) in checked_ids:
                            ch.setCheckState(0, Qt.Checked)
                        if ('point', p1id) in expanded_ids:
                            ch.setExpanded(True)
                    if p2id:
                        ch2 = QTreeWidgetItem(line_item)
                        ch2.setText(0, p2id)
                        ch2.setFlags(ch2.flags() | Qt.ItemIsUserCheckable)
                        ch2.setCheckState(0, Qt.Checked if p2id in self.edit_manager._point_actors else Qt.Unchecked)
                        cid2 = id(ch2)
                        self._item_refs[cid2] = ch2
                        self._item_meta[cid2] = {'type': 'point', 'id': p2id}
                        if ('point', p2id) in checked_ids:
                            ch2.setCheckState(0, Qt.Checked)
                        if ('point', p2id) in expanded_ids:
                            ch2.setExpanded(True)

        # 连接信号（最后连接以避免构建过程中触发）
        try:
            self.tree.itemChanged.disconnect(self._on_item_changed)
        except Exception:
            pass
        self.tree.itemChanged.connect(self._on_item_changed)

    # ========== 选择与编辑 ==========
    def _on_selection_changed(self):
        """当树项选中变化，填充编辑器（仅在选中单个点时启用）"""
        selected = self.tree.selectedItems()
        # 先处理视觉高亮（无论多少选中，优先只高亮第一个选中项）
        if selected and len(selected) >= 1:
            sel_item = selected[0]
            iid = id(sel_item)
            meta = self._item_meta.get(iid)
            
            # 自动切换到选择模式并选中对象
            if meta is not None and meta.get('type') in ['point', 'line', 'plane']:
                # 切换到编辑模式
                if hasattr(self.view, 'set_mode'):
                    current_mode = self.view.get_current_mode()
                    if current_mode != 'edit':
                        self.view.set_mode('edit')
                
                # 选中对象
                obj_type = meta.get('type')
                obj_id = meta.get('id')
                
                if obj_type == 'point':
                    self.edit_manager._selected_point_id = obj_id
                    self.edit_manager._selected_line_id = None
                    self.edit_manager._selected_plane_id = None
                    self.edit_manager.set_active_plane(None)
                elif obj_type == 'line':
                    self.edit_manager._selected_point_id = None
                    self.edit_manager._selected_line_id = obj_id
                    self.edit_manager._selected_plane_id = None
                    self.edit_manager.set_active_plane(None)
                elif obj_type == 'plane':
                    self.edit_manager._selected_point_id = None
                    self.edit_manager._selected_line_id = None
                    self.edit_manager._selected_plane_id = obj_id
                    self.edit_manager.set_active_plane(obj_id)
            
            self._apply_visual_selection(meta)

        else:
            # 恢复之前高亮
            self._clear_visual_selection()

        if not selected or len(selected) != 1:
            self._editing_point_id = None
            self._apply_btn.setEnabled(False)
            return
        item = selected[0]
        iid = id(item)
        meta = self._item_meta.get(iid)
        if meta is None or meta.get('type') != 'point':
            self._editing_point_id = None
            self._apply_btn.setEnabled(False)
            return
        pid = meta.get('id')
        # 获取当前位置
        pos = None
        try:
            pobj = self.edit_manager._points.get(pid)
            if pobj is None:
                return
            pos = getattr(pobj, 'position', pobj)
        except Exception:
            return
        try:
            self._x_spin.setValue(float(pos[0]))
            self._y_spin.setValue(float(pos[1]))
            self._z_spin.setValue(float(pos[2]))
            self._editing_point_id = pid
            self._apply_btn.setEnabled(True)
        except Exception:
            self._editing_point_id = None
            self._apply_btn.setEnabled(False)

    # ========== 视觉高亮 ==========
    def _apply_visual_selection(self, meta):
        """在视图中高亮选中的对象（恢复上一个的颜色）"""
        if meta is None:
            return
        sel_type = meta.get('type')
        sel_id = meta.get('id')

        # 如果相同则不重复处理
        current_highlight = self.edit_manager._selection_manager.get_current_highlight()
        if current_highlight and current_highlight[0] == sel_type and current_highlight[1] == sel_id:
            return

        # 使用 SelectionManager 的切换高亮功能
        try:
            self.edit_manager._selection_manager.switch_highlight(sel_type, sel_id, self.view)
            # 保存高亮信息用于兼容性
            current = self.edit_manager._selection_manager.get_current_highlight()
            if current:
                self._prev_selected = {'type': current[0], 'id': current[1], 'color': current[2]}
            else:
                self._prev_selected = None
        except Exception:
            self._prev_selected = None

    def _clear_visual_selection(self):
        """恢复之前被高亮对象的颜色"""
        self.edit_manager._selection_manager.clear_highlight(self.view)
        self._prev_selected = None
        
    def _apply_point_edit(self):
        """应用点坐标修改，保持线/面连接关系"""
        pid = self._editing_point_id
        if pid is None:
            return
        try:
            new_pos = np.array([self._x_spin.value(), self._y_spin.value(), self._z_spin.value()], dtype=np.float64)
        except Exception:
            return

        # 获取旧位置（复制）
        old_obj = self.edit_manager._points.get(pid)
        if old_obj is None:
            return
        # 避免在 getattr 中计算默认值（可能触发类型错误），显式判断
        if hasattr(old_obj, 'position'):
            old_pos = old_obj.position.copy()
        else:
            old_pos = np.array(old_obj, dtype=np.float64).copy()

        # 1) 更新点位置（使用命令模式）
        command = MovePointCommand(self.edit_manager, pid, old_pos, new_pos)
        success = self.edit_manager._undo_manager.execute_and_push(command, self.view)
        if not success:
            return

        # 2) 更新所有引用该点的线（如果线使用的是坐标则替换坐标；如果使用的是点ID则无需修改数据，只需重渲染）
        def _find_point_id_by_pos(pos):
            for pid_lookup, pobj in self.edit_manager._points.items():
                try:
                    ppos = pobj.position
                except Exception:
                    ppos = pobj
                if np.allclose(ppos, pos, atol=1e-6):
                    return pid_lookup
            return None

        for lid, (s, e) in list(self.edit_manager._lines.items()):
            updated = False
            # 如果线已经以 point id 存储，直接重渲染（位置已随 point 更新）
            if isinstance(s, str) or isinstance(e, str):
                if (isinstance(s, str) and s == pid) or (isinstance(e, str) and e == pid):
                    # 修改行为：将线修改为其它端点（ID）连接到修改后的点（ID）
                    other_id = s if isinstance(s, str) and s != pid else (e if isinstance(e, str) and e != pid else None)
                    if other_id is None:
                        # 尝试解析坐标端点为 point id（向后兼容）
                        if isinstance(s, str):
                            other_id = None
                        else:
                            other_id = _find_point_id_by_pos(s) if not isinstance(s, str) else None
                        if other_id is None and not isinstance(e, str):
                            other_id = _find_point_id_by_pos(e)
                    if other_id is not None:
                        # 将线改为 (other_id, pid) 或 (pid, other_id) 保证顺序为 (start,end)：如果 s was pid then start should be other->pid
                        if isinstance(s, str) and s == pid:
                            self.edit_manager._lines[lid] = (other_id, pid)
                        elif isinstance(e, str) and e == pid:
                            self.edit_manager._lines[lid] = (pid, other_id)
                        else:
                            # 默认设为 (other_id, pid)
                            self.edit_manager._lines[lid] = (other_id, pid)
                        updated = True
            else:
                # 线以坐标存储：如果其中一个端点等于旧位置，替换为点ID形式连接到修改后的点
                other_id = None
                if np.allclose(s, old_pos, atol=1e-6):
                    # s 是修改的点；尝试将另一端解析为点ID
                    other_id = _find_point_id_by_pos(e)
                    if other_id is not None:
                        self.edit_manager._lines[lid] = (pid, other_id)
                        updated = True
                    else:
                        # 回退：直接替换坐标
                        self.edit_manager._lines[lid] = (new_pos.copy(), e.copy())
                        updated = True
                elif np.allclose(e, old_pos, atol=1e-6):
                    other_id = _find_point_id_by_pos(s)
                    if other_id is not None:
                        self.edit_manager._lines[lid] = (other_id, pid)
                        updated = True
                    else:
                        self.edit_manager._lines[lid] = (s.copy(), new_pos.copy())
                        updated = True

            if updated:
                # 重新渲染该线
                if lid in self.edit_manager._line_actors:
                    try:
                        self.view.remove_actor(self.edit_manager._line_actors[lid])
                    except Exception:
                        pass
                try:
                    self.edit_manager._render_line(lid, self.view)
                except Exception:
                    pass

        # 3) 更新所有包含该点的面的顶点
        for plid, verts in list(self.edit_manager._planes.items()):
            changed = False
            new_verts = verts.copy()
            for i in range(new_verts.shape[0]):
                if np.allclose(new_verts[i], old_pos, atol=1e-6):
                    new_verts[i] = new_pos.copy()
                    changed = True
            if changed:
                self.edit_manager._planes[plid] = new_verts
                # 更新渲染 actor
                if plid in self.edit_manager._plane_actors:
                    try:
                        self.view.remove_actor(self.edit_manager._plane_actors[plid])
                    except Exception:
                        pass
                    try:
                        self.edit_manager._render_plane(plid, self.view)
                    except Exception:
                        pass

        # 4) 发出视图更新信号
        try:
            if hasattr(self.view, 'view_changed'):
                self.view.view_changed.emit()
        except Exception:
            pass

        # 更新树显示（保持选中和展开）
        self.refresh()

    def _clear_last_highlight(self):
        """Restore the last highlighted object's original color."""
        try:
            self.edit_manager._selection_manager.clear_highlight(self.view)
            self._last_highlight = None
        except Exception:
            pass

    def _set_highlight(self, typ: str, ident: str, highlight_color=(1.0, 1.0, 0.0)):
        """
        Highlight the object by changing its color, restoring previous highlight if any.
        typ: 'point' or 'line'
        ident: id string
        """
        try:
            original_color = self.edit_manager._selection_manager.switch_highlight(typ, ident, self.view, highlight_color)
            current = self.edit_manager._selection_manager.get_current_highlight()
            if current:
                self._last_highlight = (current[0], current[1], current[2])
            else:
                self._last_highlight = None
        except Exception:
            self._last_highlight = None

    # ========== 交互逻辑 ==========
    def _on_item_changed(self, item, column):
        """处理复选框变化，控制对应 actor 的可见性"""
        iid = id(item)
        if iid not in self._item_meta:
            return
        meta = self._item_meta.get(iid)
        typ = meta['type']
        ident = meta['id']
        state = item.checkState(0) == Qt.Checked

        try:
            if typ == 'point':
                actor = self.edit_manager._point_actors.get(ident)
                self._set_actor_visibility(actor, state)
            elif typ == 'line':
                actor = self.edit_manager._line_actors.get(ident)
                self._set_actor_visibility(actor, state)
            elif typ == 'polyline':
                actor = self.edit_manager._polyline_actors.get(ident)
                self._set_actor_visibility(actor, state)
            elif typ == 'curve':
                actor = self.edit_manager._curve_actors.get(ident)
                self._set_actor_visibility(actor, state)
            elif typ == 'plane':
                actor = self.edit_manager._plane_actors.get(ident)
                self._set_actor_visibility(actor, state)
            elif typ == 'group':
                # 分组复选框由Qt处理（三态级联）
                pass
        except Exception:
            pass

        # 渲染视图
        try:
            if hasattr(self.view, 'render'):
                self.view.render()
        except Exception:
            pass

    def _set_actor_visibility(self, actor, visible: bool):
        """尝试设置 actor 可见性，兼容不同 actor 接口"""
        if actor is None:
            return
        try:
            # VTK actor
            if hasattr(actor, 'SetVisibility'):
                actor.SetVisibility(1 if visible else 0)
                return
            if hasattr(actor, 'VisibilityOn') and hasattr(actor, 'VisibilityOff'):
                if visible:
                    actor.VisibilityOn()
                else:
                    actor.VisibilityOff()
                return
            # PyVista 包装器
            if hasattr(actor, 'prop') and hasattr(actor.prop, 'SetVisibility'):
                actor.prop.SetVisibility(1 if visible else 0)
                return
            # 回退：尝试通过视图移除/添加actor
            if not visible:
                try:
                    self.view.remove_actor(actor)
                except Exception:
                    pass
            else:
                # 无操作：没有几何引用无法重新添加
                pass
        except Exception:
            pass

    def _show_context_menu(self, position):
        """显示右键上下文菜单"""
        item = self.tree.itemAt(position)
        if item is None:
            return

        # 获取item的元数据
        item_id = id(item)
        meta = self._item_meta.get(item_id)
        if meta is None:
            return

        # 创建菜单
        menu = QMenu(self)

        # 根据类型添加删除操作
        obj_type = meta['type']
        obj_id = meta['id']

        if obj_type == 'point':
            delete_action = QAction("删除点", self)
            delete_action.triggered.connect(lambda: self._delete_point(obj_id))
            menu.addAction(delete_action)
        elif obj_type == 'line':
            delete_action = QAction("删除线", self)
            delete_action.triggered.connect(lambda: self._delete_line(obj_id))
            menu.addAction(delete_action)
        elif obj_type == 'polyline':
            delete_action = QAction("删除折线", self)
            delete_action.triggered.connect(lambda: self._delete_polyline(obj_id))
            menu.addAction(delete_action)
        elif obj_type == 'curve':
            delete_action = QAction("删除曲线", self)
            delete_action.triggered.connect(lambda: self._delete_curve(obj_id))
            menu.addAction(delete_action)
        elif obj_type == 'plane':
            delete_action = QAction("删除面", self)
            delete_action.triggered.connect(lambda: self._delete_plane(obj_id))
            menu.addAction(delete_action)

        # 显示菜单
        if not menu.isEmpty():
            menu.exec_(self.tree.mapToGlobal(position))

    def _delete_point(self, point_id: str):
        """删除指定的点"""
        if self.edit_manager is None:
            return

        # 使用命令模式删除点
        command = RemovePointCommand(self.edit_manager, point_id)
        success = self.edit_manager._undo_manager.execute_and_push(command, self.view)

        if success:
            # 清除编辑器中的点（如果正在编辑此点）
            if self._editing_point_id == point_id:
                self._editing_point_id = None
                self._x_spin.setValue(0.0)
                self._y_spin.setValue(0.0)
                self._z_spin.setValue(0.0)
                self._apply_btn.setEnabled(False)

            # 刷新界面
            self.refresh()

            # 发送状态消息
            if hasattr(self.view, 'status_message'):
                self.view.status_message.emit(f'已删除点: {point_id}')
        else:
            if hasattr(self.view, 'status_message'):
                self.view.status_message.emit('删除点失败')

    def _delete_line(self, line_id: str):
        """删除指定的线"""
        if self.edit_manager is None:
            return

        # 使用命令模式删除线
        command = RemoveLineCommand(self.edit_manager, line_id)
        success = self.edit_manager._undo_manager.execute_and_push(command, self.view)

        if success:
            # 刷新界面
            self.refresh()

            # 发送状态消息
            if hasattr(self.view, 'status_message'):
                self.view.status_message.emit(f'已删除线: {line_id}')
        else:
            if hasattr(self.view, 'status_message'):
                self.view.status_message.emit('删除线失败')

    def _delete_polyline(self, polyline_id: str):
        """删除指定的折线"""
        if self.edit_manager is None:
            return

        # 使用命令模式删除折线
        command = RemovePolylineCommand(self.edit_manager, polyline_id)
        success = self.edit_manager._undo_manager.execute_and_push(command, self.view)

        if success:
            # 刷新界面
            self.refresh()

            # 发送状态消息
            if hasattr(self.view, 'status_message'):
                self.view.status_message.emit(f'已删除折线: {polyline_id}')
        else:
            if hasattr(self.view, 'status_message'):
                self.view.status_message.emit('删除折线失败')

    def _delete_curve(self, curve_id: str):
        """删除指定的曲线"""
        if self.edit_manager is None:
            return

        # 使用命令模式删除曲线
        command = RemoveCurveCommand(self.edit_manager, curve_id)
        success = self.edit_manager._undo_manager.execute_and_push(command, self.view)

        if success:
            # 刷新界面
            self.refresh()

            # 发送状态消息
            if hasattr(self.view, 'status_message'):
                self.view.status_message.emit(f'已删除曲线: {curve_id}')
        else:
            if hasattr(self.view, 'status_message'):
                self.view.status_message.emit('删除曲线失败')

    def _delete_plane(self, plane_id: str):
        """删除指定的面"""
        if self.edit_manager is None:
            return

        # 使用命令模式删除面
        command = RemovePlaneCommand(self.edit_manager, plane_id)
        success = self.edit_manager._undo_manager.execute_and_push(command, self.view)

        if success:
            # 刷新界面
            self.refresh()

            # 发送状态消息
            if hasattr(self.view, 'status_message'):
                self.view.status_message.emit(f'已删除面: {plane_id}')
        else:
            if hasattr(self.view, 'status_message'):
                self.view.status_message.emit('删除面失败')
    
    def _add_point_button_to_tree(self, points_root):
        """在点分组旁添加增加按钮"""
        try:
            # 创建按钮
            add_btn = QPushButton()
            add_btn.setIcon(QIcon(r"h:\3D\img\增加.png"))
            add_btn.setFixedSize(20, 20)
            add_btn.setToolTip("通过输入坐标创建点")
            add_btn.clicked.connect(self._show_add_point_dialog)
            
            # 将按钮添加到第1列（右侧）
            self.tree.setItemWidget(points_root, 1, add_btn)
        except Exception as e:
            print(f"添加按钮失败: {e}")
    
    def _show_add_point_dialog(self):
        """显示坐标输入对话框"""
        dialog = CoordinateInputDialog(self.view, self)
        dialog.exec_()
        # 对话框关闭后刷新场景面板
        self.refresh()
