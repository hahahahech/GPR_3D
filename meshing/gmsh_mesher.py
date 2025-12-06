"""
Gmsh网格生成器
"""
import gmsh
import numpy as np
from typing import Tuple, Optional
# from core.geological_model import GeologicalModel  # 暂时注释，待实现


class GmshMesher:
    """Gmsh网格生成器"""
    
    def __init__(self, model: GeologicalModel):
        """
        初始化Gmsh网格生成器
        
        Parameters:
        -----------
        model : GeologicalModel
            地质模型对象
        """
        self.model = model
        gmsh.initialize()
        gmsh.model.add("underground_model")
        self.surface_tags = []
        self.volume_tags = []
        
    def generate_tetrahedral_mesh(self, element_size: Optional[float] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        生成四面体网格
        
        Parameters:
        -----------
        element_size : float, optional
            单元尺寸，如果为None则自动计算
            
        Returns:
        --------
        nodes : np.ndarray
            节点坐标 (Nx3)
        elements : np.ndarray
            单元节点索引 (Mx4)
        """
        # 清除之前的几何
        gmsh.model.remove()
        gmsh.model.add("underground_model")
        
        # 创建几何模型
        self._create_geometry()
        
        # 设置网格尺寸
        if element_size is None:
            # 根据模型尺寸自动计算
            bounds = self.model.get_bounds()
            model_size = max(
                bounds[1] - bounds[0],
                bounds[3] - bounds[2],
                bounds[5] - bounds[4]
            )
            element_size = model_size / 20.0
        
        # 设置全局网格尺寸
        gmsh.model.mesh.setSize(
            gmsh.model.getEntities(0), element_size
        )
        
        # 生成3D网格
        gmsh.model.mesh.generate(3)
        
        # 提取节点和单元
        node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
        element_types, element_tags, element_node_tags = gmsh.model.mesh.getElements()
        
        # 找到四面体单元（类型4）
        tet_index = None
        for i, elem_type in enumerate(element_types):
            if elem_type == 4:  # 4-node tetrahedron
                tet_index = i
                break
        
        if tet_index is None:
            raise ValueError("No tetrahedral elements found in mesh")
        
        # 转换为numpy数组
        nodes = node_coords.reshape(-1, 3)
        elements = element_node_tags[tet_index].reshape(-1, 4) - 1  # Gmsh从1开始，转为从0开始
        
        return nodes, elements
        
    def generate_hexahedral_mesh(self, nx: int, ny: int, nz: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        生成六面体结构化网格
        
        Parameters:
        -----------
        nx, ny, nz : int
            各方向的单元数量
            
        Returns:
        --------
        nodes : np.ndarray
            节点坐标 (Nx3)
        elements : np.ndarray
            单元节点索引 (Mx8)
        """
        bounds = self.model.get_bounds()
        x = np.linspace(bounds[0], bounds[1], nx + 1)
        y = np.linspace(bounds[2], bounds[3], ny + 1)
        z = np.linspace(bounds[4], bounds[5], nz + 1)
        
        # 创建结构化网格的点
        points = []
        for k in range(nz + 1):
            for j in range(ny + 1):
                for i in range(nx + 1):
                    points.append([x[i], y[j], z[k]])
        
        nodes = np.array(points)
        
        # 创建六面体单元
        elements = []
        for k in range(nz):
            for j in range(ny):
                for i in range(nx):
                    # 计算8个节点的索引
                    n0 = k * (ny + 1) * (nx + 1) + j * (nx + 1) + i
                    n1 = n0 + 1
                    n2 = n0 + (nx + 1)
                    n3 = n2 + 1
                    n4 = n0 + (ny + 1) * (nx + 1)
                    n5 = n1 + (ny + 1) * (nx + 1)
                    n6 = n2 + (ny + 1) * (nx + 1)
                    n7 = n3 + (ny + 1) * (nx + 1)
                    elements.append([n0, n1, n3, n2, n4, n5, n7, n6])
        
        elements = np.array(elements)
        
        return nodes, elements
        
    def _create_geometry(self):
        """从地质模型创建Gmsh几何"""
        bounds = self.model.get_bounds()
        
        # 创建模型边界框（立方体）
        # 定义8个顶点
        x_min, x_max = bounds[0], bounds[1]
        y_min, y_max = bounds[2], bounds[3]
        z_min, z_max = bounds[4], bounds[5]
        
        # 创建点
        p1 = gmsh.model.geo.addPoint(x_min, y_min, z_min)
        p2 = gmsh.model.geo.addPoint(x_max, y_min, z_min)
        p3 = gmsh.model.geo.addPoint(x_max, y_max, z_min)
        p4 = gmsh.model.geo.addPoint(x_min, y_max, z_min)
        p5 = gmsh.model.geo.addPoint(x_min, y_min, z_max)
        p6 = gmsh.model.geo.addPoint(x_max, y_min, z_max)
        p7 = gmsh.model.geo.addPoint(x_max, y_max, z_max)
        p8 = gmsh.model.geo.addPoint(x_min, y_max, z_max)
        
        # 创建线
        l1 = gmsh.model.geo.addLine(p1, p2)
        l2 = gmsh.model.geo.addLine(p2, p3)
        l3 = gmsh.model.geo.addLine(p3, p4)
        l4 = gmsh.model.geo.addLine(p4, p1)
        l5 = gmsh.model.geo.addLine(p5, p6)
        l6 = gmsh.model.geo.addLine(p6, p7)
        l7 = gmsh.model.geo.addLine(p7, p8)
        l8 = gmsh.model.geo.addLine(p8, p5)
        l9 = gmsh.model.geo.addLine(p1, p5)
        l10 = gmsh.model.geo.addLine(p2, p6)
        l11 = gmsh.model.geo.addLine(p3, p7)
        l12 = gmsh.model.geo.addLine(p4, p8)
        
        # 创建面
        s1 = gmsh.model.geo.addPlaneSurface([gmsh.model.geo.addCurveLoop([l1, l2, l3, l4])])
        s2 = gmsh.model.geo.addPlaneSurface([gmsh.model.geo.addCurveLoop([l5, l6, l7, l8])])
        s3 = gmsh.model.geo.addPlaneSurface([gmsh.model.geo.addCurveLoop([l1, l10, -l5, -l9])])
        s4 = gmsh.model.geo.addPlaneSurface([gmsh.model.geo.addCurveLoop([l2, l11, -l6, -l10])])
        s5 = gmsh.model.geo.addPlaneSurface([gmsh.model.geo.addCurveLoop([l3, l12, -l7, -l11])])
        s6 = gmsh.model.geo.addPlaneSurface([gmsh.model.geo.addCurveLoop([l4, l9, -l8, -l12])])
        
        # 创建体
        v1 = gmsh.model.geo.addVolume([
            gmsh.model.geo.addSurfaceLoop([s1, s2, s3, s4, s5, s6])
        ])
        
        # 同步几何模型
        gmsh.model.geo.synchronize()
        
        self.volume_tags = [v1]
        
    def save_mesh(self, filename: str):
        """保存网格到文件"""
        gmsh.write(filename)
        
    def __del__(self):
        """清理资源"""
        try:
            gmsh.finalize()
        except:
            pass

