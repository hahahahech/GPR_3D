"""
模式切换和工具选择工具栏
"""
from PyQt5.QtWidgets import QToolButton, QMenu, QWidget, QHBoxLayout, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap
import os
from typing import Optional


class ModeToolbar:
    """模式切换和工具选择工具栏管理器"""
    
    def __init__(self, parent_widget):
        """
        初始化工具栏管理器
        
        Parameters:
        -----------
        parent_widget : QWidget
            父窗口部件（通常是InteractiveView）
        """
        self.parent = parent_widget
        # 固定为编辑模式（移除物体模式）
        self._current_mode = 'edit'
        
        # 工具选择（仅编辑模式）
        self._current_tool = None  # 当前工具
        self._select_enabled = False
        self._tool_buttons = {}  # 存储工具按钮引用
        self._toolbar_widget = None  # 共享工具栏容器
        self._toolbar_layout = None  # 工具栏布局
        
        # 定义工具列表
        self._edit_tools = [
            ('edit_select', '选择.png', '选择'),  # 编辑模式的选择工具（与物体模式区分）
            ('point', '点.png', '点'),
            ('polyline', '直线.png', '折线'),
            ('curve', '曲线.png', '曲线'),
            ('lashen', '拉伸.png', '拉伸'),
            ('plane', '平面.png', '平面'),
            ('color_select', '颜色选择器.png', '颜色')
        ]
        # 创建工具栏（仅编辑工具）
        self._create_toolbar()
    
    def _get_icon_path(self, filename: str) -> str:
        """获取图标文件路径"""
        # 获取项目根目录（假设img文件夹在项目根目录）
        current_dir = os.path.dirname(os.path.abspath(__file__))  # gui/interactive_view/
        # 从 gui/interactive_view/ 返回到项目根目录（需要两次dirname）
        project_root = os.path.dirname(os.path.dirname(current_dir))  # 项目根目录
        icon_path = os.path.join(project_root, 'img', filename)
        return icon_path
    
    def _create_object_icon(self) -> QIcon:
        """创建物体模式图标（从PNG文件加载）"""
        icon_path = self._get_icon_path('货物体积.png')
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                return QIcon(pixmap)
        return QIcon()
    
    def _create_edit_icon(self) -> QIcon:
        """创建编辑模式图标（从PNG文件加载）"""
        icon_path = self._get_icon_path('编辑.png')
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                return QIcon(pixmap)
        return QIcon()
    
    # ========== 模式选择 ==========
    
    def _create_mode_selector(self):
        """创建模式选择控件"""
        # 已移除模式选择控件，工具栏固定为编辑模式
        return
    
    def _create_object_icon(self) -> QIcon:
        """创建物体模式图标（从PNG文件加载）"""
        icon_path = self._get_icon_path('货物体积.png')
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            # 缩放图标到合适大小（20x20）
            if not pixmap.isNull():
                pixmap = pixmap.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                return QIcon(pixmap)
        # 如果文件不存在，返回空图标
        return QIcon()
    
    def _create_edit_icon(self) -> QIcon:
        """创建编辑模式图标（从PNG文件加载）"""
        icon_path = self._get_icon_path('编辑.png')
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            # 缩放图标到合适大小（20x20）
            if not pixmap.isNull():
                pixmap = pixmap.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                return QIcon(pixmap)
        # 如果文件不存在，返回空图标
        return QIcon()
    
    def _update_mode_button_display(self, mode: str):
        """更新按钮显示（图标和文字）"""
        if mode == 'object':
            self._mode_button.setIcon(self._create_object_icon())
            self._mode_button.setText("物体模式")
        elif mode == 'edit':
            self._mode_button.setIcon(self._create_edit_icon())
            self._mode_button.setText("编辑模式")
    
    def _update_mode_selector_position(self):
        """更新模式选择控件位置（左上角）"""
        # 模式选择控件已移除
        return
    
    def _on_mode_selected(self, mode: str):
        """模式选择事件处理"""
        # 仅支持编辑模式；忽略切换请求或设置为编辑
        if mode == 'edit':
            self._current_mode = 'edit'
            self._update_toolbar_buttons()
            self._current_tool = None
            if hasattr(self.parent, 'status_message'):
                self.parent.status_message.emit('已切换到编辑模式')
            if hasattr(self.parent, 'mode_changed'):
                self.parent.mode_changed.emit(self._current_mode)
        else:
            # 不支持其他模式
            return
    
    def get_current_mode(self) -> str:
        """获取当前模式"""
        return self._current_mode
    
    def set_mode(self, mode: str):
        """设置模式"""
        # 仅支持设置为编辑模式
        if mode != 'edit':
            raise ValueError(f"仅支持 'edit' 模式，收到: {mode}")
        self._on_mode_selected('edit')
    
    # ========== 共享工具栏 ==========
    
    def _create_toolbar(self):
        """创建共享工具栏（两个模式共用）"""
        # 创建工具栏容器
        self._toolbar_widget = QWidget(self.parent)
        self._toolbar_widget.setStyleSheet("""
            QWidget {
                background-color: #e8e8e8;
                border: 2px solid #333333;
                border-radius: 6px;
            }
        """)
        
        # 创建水平布局（编辑工具横向排列）
        self._toolbar_layout = QHBoxLayout(self._toolbar_widget)
        self._toolbar_layout.setContentsMargins(4, 4, 4, 4)
        self._toolbar_layout.setSpacing(4)
        self._toolbar_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # 根据当前模式初始化按钮
        self._update_toolbar_buttons()
        
        # 设置初始位置
        self._update_toolbar_position()
    
    def _update_toolbar_buttons(self):
        """根据当前模式更新工具栏按钮"""
        # 清除所有现有按钮
        for button in self._tool_buttons.values():
            self._toolbar_layout.removeWidget(button)
            button.deleteLater()
        self._tool_buttons.clear()
        
        # 仅显示编辑工具
        tools = self._edit_tools
        
        # 创建新的工具按钮
        for tool_id, icon_file, tool_name in tools:
            button = QToolButton(self._toolbar_widget)
            button.setCheckable(True)  # 设置为可切换按钮
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)  # 只显示图标
            button.setIconSize(QSize(24, 24))  # 设置图标大小
            
            # 加载图标
            icon_path = self._get_icon_path(icon_file)
            try:
                if os.path.exists(icon_path):
                    pixmap = QPixmap(icon_path)
                    if not pixmap.isNull():
                        # 缩放图标到24x24
                        pixmap = pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        button.setIcon(QIcon(pixmap))
                    else:
                        print(f"警告: 无法加载图标文件: {icon_path}")
                else:
                    # 如果图标文件不存在，打印调试信息
                    print(f"警告: 图标文件不存在: {icon_path}")
            except Exception as e:
                print(f"警告: 加载图标时出错 {icon_path}: {e}")
            
            # 设置样式（白色背景，深色边框，圆角，图标居中）
            button.setStyleSheet("""
                QToolButton {
                    background-color: white;
                    border: 1px solid #666666;
                    border-radius: 4px;
                    padding: 4px;
                    min-width: 36px;
                    min-height: 36px;
                    max-width: 36px;
                    max-height: 36px;
                }
                QToolButton:hover {
                    background-color: #f5f5f5;
                    border: 1px solid #333333;
                }
                QToolButton:checked {
                    background-color: #d0d0d0;
                    border: 1px solid #000000;
                }
            """)
            # 设置按钮对齐方式为居中
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            
            # 设置工具提示
            button.setToolTip(tool_name)
            
            # 连接信号
            button.clicked.connect(lambda checked, tid=tool_id: self._on_tool_selected(tid))
            
            # 存储按钮引用
            self._tool_buttons[tool_id] = button
            self._toolbar_layout.addWidget(button, alignment=Qt.AlignVCenter)  # 水平布局中垂直居中
        
        # 移除弹性空间，让工具栏大小完全由按钮决定
        
        # 更新工具栏位置和可见性
        self._update_toolbar_position()
        self._update_toolbar_visibility()
    
    def _update_toolbar_position(self):
        """更新工具栏位置（模式按钮下方）"""
        if hasattr(self, '_toolbar_widget') and self._toolbar_widget:
            position_margin = 10  # 工具栏在窗口中的位置边距
            button_height = 32
            toolbar_spacing = 8  # 工具栏与模式按钮的间距
            
            # 计算工具栏大小（横向排列）
            # 按钮数量
            button_count = len(self._edit_tools)

            button_size = 36  # 每个按钮大小（min-width/max-width）
            content_margin = 4  # 布局内边距（从setContentsMargins获取）
            button_spacing = 4  # 按钮间距（从setSpacing获取）
            border_width = 4  # 外边框宽度（2px * 2）

            # 针对横向布局：高度固定，宽度由父容器/停靠管理
            toolbar_height = button_size + 2 * content_margin + border_width
            try:
                # 优先设置固定高度以保持横向工具栏外观
                self._toolbar_widget.setFixedHeight(toolbar_height)
            except:
                pass

            # 如果未在停靠中（直接作为父控件子控件），设置位置与宽度
            try:
                parent_widget = self.parent
                if parent_widget is not None and not hasattr(parent_widget, 'addDockWidget'):
                    # 仅在非主窗口父级时设置几何
                    toolbar_width = button_size * button_count + button_spacing * (button_count - 1) + 2 * content_margin + border_width
                    self._toolbar_widget.setFixedSize(toolbar_width, toolbar_height)
                    self._toolbar_widget.setGeometry(
                        position_margin,
                        position_margin,
                        toolbar_width,
                        toolbar_height
                    )
            except:
                pass
    
    def _update_toolbar_visibility(self):
        """更新工具栏显示状态"""
        if hasattr(self, '_toolbar_widget') and self._toolbar_widget:
            # 工具栏始终显示（根据模式显示不同的按钮）
            self._toolbar_widget.show()
            # 取消所有工具选择
            for tid, button in self._tool_buttons.items():
                button.setChecked(False)
            self._current_tool = None
            self._select_enabled = False
    
    def _on_tool_selected(self, tool_id: str):
        """工具选择事件处理"""
        if tool_id == 'edit_select':
            enabled = False
            try:
                enabled = self._tool_buttons[tool_id].isChecked()
            except Exception:
                enabled = False
            self._select_enabled = enabled
            if not enabled:
                try:
                    if hasattr(self.parent, '_edit_mode_manager'):
                        self.parent._edit_mode_manager.set_active_plane(None)
                except Exception:
                    pass
            if hasattr(self.parent, 'status_message'):
                self.parent.status_message.emit('选择模式已开启' if enabled else '选择模式已关闭')
            return

        # 如果点击已选中的工具，则取消选择
        if self._current_tool == tool_id:
            self._tool_buttons[tool_id].setChecked(False)
            self._current_tool = None
            if hasattr(self.parent, 'status_message'):
                self.parent.status_message.emit('已取消工具选择')
            if hasattr(self.parent, 'tool_changed'):
                self.parent.tool_changed.emit(None)
        else:
            # 取消其他工具的选择
            for tid, button in self._tool_buttons.items():
                if tid == 'edit_select':
                    continue
                button.setChecked(tid == tool_id)
            
            self._current_tool = tool_id
            
            # 发送状态消息
            # 合并两个模式的工具名称字典
            tool_names = {
                # 编辑模式工具
                'edit_select': '选择',
                'point': '点',
                'polyline': '折线',
                'curve': '曲线',
                'plane': '平面',
                'color_select': '颜色',
            }
            tool_name = tool_names.get(tool_id, tool_id)
            if hasattr(self.parent, 'status_message'):
                self.parent.status_message.emit(f'已选择工具：{tool_name}')
            if hasattr(self.parent, 'tool_changed'):
                self.parent.tool_changed.emit(tool_id)
    
    def get_current_tool(self) -> Optional[str]:
        """获取当前选择的工具"""
        return self._current_tool

    def is_select_enabled(self) -> bool:
        return getattr(self, '_select_enabled', False)
    
    def set_tool(self, tool_id: Optional[str]):
        """设置工具"""
        if tool_id is None:
            # 取消所有工具选择
            for tid, button in self._tool_buttons.items():
                if tid == 'edit_select':
                    continue
                button.setChecked(False)
            self._current_tool = None
            if hasattr(self.parent, 'tool_changed'):
                self.parent.tool_changed.emit(None)
        elif tool_id == 'edit_select':
            if 'edit_select' in self._tool_buttons:
                self._tool_buttons['edit_select'].setChecked(True)
                self._select_enabled = True
                if hasattr(self.parent, 'status_message'):
                    self.parent.status_message.emit('选择模式已开启')
        elif tool_id in self._tool_buttons:
            # 选择指定工具
            self._on_tool_selected(tool_id)
        else:
            raise ValueError(f"未知工具: {tool_id}")
    
    # ========== 物体模式工具访问方法（兼容性） ==========
    
    def get_current_object_tool(self) -> Optional[str]:
        """获取当前选择的物体操作工具（兼容性方法）"""
        if self._current_mode == 'object':
            return self._current_tool
        return None
    
    def set_object_tool(self, tool_id: Optional[str]):
        """设置物体操作工具（兼容性方法）"""
        if self._current_mode != 'object':
            raise ValueError("只能在物体模式下设置物体操作工具")
        self.set_tool(tool_id)
    
    def update_positions(self):
        """更新所有控件位置（窗口大小改变时调用）"""
        self._update_mode_selector_position()
        self._update_toolbar_position()