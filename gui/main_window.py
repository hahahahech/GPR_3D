"""
主窗口
"""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QHBoxLayout,
                             QStatusBar, QMessageBox,
                             QFileDialog, QDockWidget, QPlainTextEdit)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import pyvista as pv

from gui.interactive_view import InteractiveView
from gui.view_axes_2d import ViewAxes2D
import numpy as np


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("道路地下三维建模与网格划分软件")
        self.setGeometry(100, 100, 1600, 900)
        
        # 创建UI
        self._create_menu_bar()
        self._create_status_bar()
        self._create_main_widget()
        self._create_log_dock()
        
        # 更新状态栏
        self.statusBar().showMessage('就绪')
        
        # 连接InteractiveView的状态消息信号
        if hasattr(self, 'plotter') and hasattr(self.plotter, 'status_message'):
            self.plotter.status_message.connect(self.statusBar().showMessage)
            # 同时连接到日志窗口
            if hasattr(self, '_log_widget'):
                self.plotter.status_message.connect(self._append_log_message)
        
    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件(&F)')
        file_menu.addAction('新建项目(&N)', self.new_project, 'Ctrl+N')
        file_menu.addAction('打开项目(&O)', self.open_project, 'Ctrl+O')
        file_menu.addAction('保存项目(&S)', self.save_project, 'Ctrl+S')
        file_menu.addSeparator()
        file_menu.addAction('退出(&X)', self.close, 'Ctrl+Q')
        
        # 编辑菜单
        edit_menu = menubar.addMenu('编辑(&E)')
        edit_menu.addAction('撤销(&U)', self.undo, 'Ctrl+Z')
        edit_menu.addAction('重做(&R)', self.redo, 'Ctrl+Y')
        edit_menu.addSeparator()
        edit_menu.addAction('清除模型(&C)', self.clear_model)
        
        # 视图菜单
        view_menu = menubar.addMenu('视图(&V)')
        view_menu.addAction('重置视图(&R)', self.reset_view)
        view_menu.addAction('显示方向组件(&A)', self.toggle_axes)
        view_menu.addAction('显示网格(&G)', self.toggle_grid)
        view_menu.addAction('显示原点坐标轴(&O)', self.toggle_origin_axes)
        view_menu.addSeparator()
        view_menu.addAction('显示日志窗口(&L)', self.toggle_log_dock)
        view_menu.addSeparator()
        view_menu.addAction('设置区域大小(&W)', self.set_workspace_size)
        
        # 帮助菜单
        help_menu = menubar.addMenu('帮助(&H)')
        help_menu.addAction('关于(&A)', self.show_about)
        
    def _create_main_widget(self):
        """创建主界面"""
        # 直接使用InteractiveView作为中央部件，占据整个窗口
        pv.set_plot_theme("default")  # 使用默认主题（浅色）
        
        self.plotter = InteractiveView(
            self,
            workspace_bounds=np.array([-100.0, 100.0, -100.0, 100.0, -50.0, 0.0]),
            background_color='white'
        )
        self.setCentralWidget(self.plotter)
        
        # 添加方向组件（固定在右上角）
        self.view_axes = ViewAxes2D(self.plotter, size=100)
        self.view_axes.setParent(self.plotter)
        self.view_axes.raise_()  # 确保在最上层
        
        # 连接相机变化信号到方向组件更新
        def update_view_axes():
            if hasattr(self, 'view_axes') and hasattr(self, 'plotter'):
                try:
                    camera = self.plotter.renderer.GetActiveCamera()
                    position = np.array(camera.GetPosition())
                    focal_point = np.array(camera.GetFocalPoint())
                    view_up = np.array(camera.GetViewUp())
                    
                    direction = position - focal_point
                    direction_norm = np.linalg.norm(direction)
                    if direction_norm > 1e-6:
                        direction = direction / direction_norm
                        self.view_axes.update_camera_direction(direction, view_up)
                except Exception as e:
                    pass  # 忽略更新错误
        
        self.plotter.view_changed.connect(update_view_axes)
        
        # 初始更新一次方向组件位置和方向
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(100, lambda: [update_view_axes(), self._update_view_axes_position()])
        
    def _create_status_bar(self):
        """创建状态栏"""
        self.statusBar().showMessage('就绪')
    
    def _create_log_dock(self):
        """创建日志停靠窗口"""
        # 创建停靠窗口
        self._log_dock = QDockWidget("操作日志", self)
        self._log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self._log_dock.setFeatures(
            QDockWidget.DockWidgetMovable | 
            QDockWidget.DockWidgetClosable | 
            QDockWidget.DockWidgetFloatable
        )
        
        # 创建日志文本框
        self._log_widget = QPlainTextEdit()
        self._log_widget.setReadOnly(True)
        self._log_widget.setMaximumBlockCount(500)  # 最多保留500行
        self._log_widget.setFont(QFont('Consolas', 9))
        self._log_widget.setStyleSheet(
            "QPlainTextEdit {"
            "   background-color: #2b2b2b;"
            "   color: #e0e0e0;"
            "   border: none;"
            "   padding: 4px;"
            "}"
        )
        self._log_widget.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        
        # 设置为停靠窗口的内容
        self._log_dock.setWidget(self._log_widget)
        
        # 添加到主窗口底部
        self.addDockWidget(Qt.BottomDockWidgetArea, self._log_dock)
        
        # 设置初始高度
        self._log_dock.setMinimumHeight(100)
        self._log_dock.setMaximumHeight(300)
        
        # 初始日志
        self._append_log_message("系统已启动，准备就绪")
    
    def _append_log_message(self, msg: str):
        """追加日志消息"""
        if hasattr(self, '_log_widget'):
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            self._log_widget.appendPlainText(f"[{timestamp}] {msg}")
            # 自动滚动到底部
            scrollbar = self._log_widget.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
    def reset_view(self):
        """重置视图"""
        self.plotter.reset_camera()
        
    def toggle_axes(self):
        """切换方向组件显示"""
        if hasattr(self, 'view_axes'):
            self.view_axes.setVisible(not self.view_axes.isVisible())
            status = '显示' if self.view_axes.isVisible() else '隐藏'
            self.statusBar().showMessage(f'方向组件已{status}', 2000)
        else:
            self.statusBar().showMessage('方向组件未初始化', 2000)
    
    def toggle_origin_axes(self):
        """切换原点坐标轴显示"""
        if hasattr(self, 'plotter'):
            self.plotter.toggle_origin_axes()
            status = '显示' if self.plotter.get_show_origin_axes() else '隐藏'
            self.statusBar().showMessage(f'原点坐标轴已{status}', 2000)
        else:
            self.statusBar().showMessage('视图未初始化', 2000)
    
    def toggle_log_dock(self):
        """切换日志窗口显示"""
        if hasattr(self, '_log_dock'):
            self._log_dock.setVisible(not self._log_dock.isVisible())
            status = '显示' if self._log_dock.isVisible() else '隐藏'
            self.statusBar().showMessage(f'日志窗口已{status}', 2000)
        else:
            self.statusBar().showMessage('日志窗口未初始化', 2000)
    
    def _update_view_axes_position(self):
        """更新方向组件位置到右上角"""
        if hasattr(self, 'view_axes') and hasattr(self, 'plotter'):
            plotter_size = self.plotter.size()
            axes_size = self.view_axes.size().width()
            margin = 10
            self.view_axes.move(
                plotter_size.width() - axes_size - margin,
                margin
            )
            self.view_axes.show()
    
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        self._update_view_axes_position()
        
    def toggle_grid(self):
        """切换网格显示"""
        if hasattr(self, 'plotter'):
            self.plotter.toggle_grid()
            status = '显示' if self.plotter.get_show_grid() else '隐藏'
            self.statusBar().showMessage(f'网格已{status}', 2000)
        else:
            self.statusBar().showMessage('视图未初始化', 2000)
        
    def new_project(self):
        """新建项目"""
        reply = QMessageBox.question(
            self, '新建项目',
            '是否保存当前项目？',
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )
        
        if reply == QMessageBox.Cancel:
            return
        elif reply == QMessageBox.Yes:
            self.save_project()
        
        # 创建新项目
        self.plotter.clear()
        self.statusBar().showMessage('已创建新项目', 2000)
        
    def open_project(self):
        """打开项目"""
        filename, _ = QFileDialog.getOpenFileName(
            self, '打开项目', '', 'JSON Files (*.json);;All Files (*)'
        )
        if filename:
            # TODO: 实现项目加载
            QMessageBox.information(self, '提示', '项目加载功能待实现')
            
    def save_project(self):
        """保存项目"""
        filename, _ = QFileDialog.getSaveFileName(
            self, '保存项目', '', 'JSON Files (*.json);;All Files (*)'
        )
        if filename:
            # TODO: 实现项目保存
            QMessageBox.information(self, '提示', '项目保存功能待实现')
            
    def undo(self):
        """撤销"""
        # TODO: 实现撤销功能
        self.statusBar().showMessage('撤销功能待实现', 2000)
        
    def redo(self):
        """重做"""
        # TODO: 实现重做功能
        self.statusBar().showMessage('重做功能待实现', 2000)
        
    def clear_model(self):
        """清除模型"""
        reply = QMessageBox.question(
            self, '清除模型',
            '确定要清除所有模型数据吗？此操作不可撤销。',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.plotter.clear()
            self.statusBar().showMessage('模型已清除', 2000)
            
    def set_workspace_size(self):
        """设置工作空间大小"""
        from PyQt5.QtWidgets import QDialog, QFormLayout, QDoubleSpinBox, QDialogButtonBox
        
        # 获取当前边界
        current_bounds = self.plotter.get_workspace_bounds()
        
        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle('设置区域大小')
        dialog.setModal(True)
        
        layout = QFormLayout(dialog)
        
        # X范围
        x_min_spin = QDoubleSpinBox()
        x_min_spin.setRange(-10000, 10000)
        x_min_spin.setValue(current_bounds[0])
        x_min_spin.setDecimals(2)
        layout.addRow("X 最小值:", x_min_spin)
        
        x_max_spin = QDoubleSpinBox()
        x_max_spin.setRange(-10000, 10000)
        x_max_spin.setValue(current_bounds[1])
        x_max_spin.setDecimals(2)
        layout.addRow("X 最大值:", x_max_spin)
        
        # Y范围
        y_min_spin = QDoubleSpinBox()
        y_min_spin.setRange(-10000, 10000)
        y_min_spin.setValue(current_bounds[2])
        y_min_spin.setDecimals(2)
        layout.addRow("Y 最小值:", y_min_spin)
        
        y_max_spin = QDoubleSpinBox()
        y_max_spin.setRange(-10000, 10000)
        y_max_spin.setValue(current_bounds[3])
        y_max_spin.setDecimals(2)
        layout.addRow("Y 最大值:", y_max_spin)
        
        # Z范围
        z_min_spin = QDoubleSpinBox()
        z_min_spin.setRange(-10000, 10000)
        z_min_spin.setValue(current_bounds[4])
        z_min_spin.setDecimals(2)
        layout.addRow("Z 最小值:", z_min_spin)
        
        z_max_spin = QDoubleSpinBox()
        z_max_spin.setRange(-10000, 10000)
        z_max_spin.setValue(current_bounds[5])
        z_max_spin.setDecimals(2)
        layout.addRow("Z 最大值:", z_max_spin)
        
        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        # 显示对话框
        if dialog.exec_() == QDialog.Accepted:
            # 验证输入
            if (x_min_spin.value() >= x_max_spin.value() or 
                y_min_spin.value() >= y_max_spin.value() or 
                z_min_spin.value() >= z_max_spin.value()):
                QMessageBox.warning(self, '错误', '最小值必须小于最大值')
                return
            
            # 设置新的边界
            new_bounds = np.array([
                x_min_spin.value(),
                x_max_spin.value(),
                y_min_spin.value(),
                y_max_spin.value(),
                z_min_spin.value(),
                z_max_spin.value()
            ])
            
            self.plotter.set_workspace_bounds(new_bounds)
            self.statusBar().showMessage(f'区域大小已更新: X[{new_bounds[0]:.2f}, {new_bounds[1]:.2f}], '
                                       f'Y[{new_bounds[2]:.2f}, {new_bounds[3]:.2f}], '
                                       f'Z[{new_bounds[4]:.2f}, {new_bounds[5]:.2f}]', 3000)
            
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self, '关于',
            '道路地下三维建模与网格划分软件\n\n'
            '版本: 0.1.0\n\n'
            '功能：\n'
            '- 交互式三维视图\n'
            '- 轨道摄像机控制\n'
            '- 网格生成\n'
            '- 可视化\n'
            '- 数据导出'
        )
