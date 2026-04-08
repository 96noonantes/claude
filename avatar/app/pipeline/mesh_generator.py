"""Generate triangle meshes from part PNG alpha contours.

For each part: extract alpha outline → simplify → Delaunay triangulate.
Output mesh data for WebGL rendering on mobile (iPhone 15 PWA).
"""

import cv2
import numpy as np
from scipy.spatial import Delaunay
from dataclasses import dataclass, field


@dataclass
class MeshData:
    vertices: list = field(default_factory=list)   # [[x, y], ...] local px coords
    uvs: list = field(default_factory=list)         # [[u, v], ...] 0-1 normalized
    indices: list = field(default_factory=list)      # [i0, i1, i2, ...] flat triangle indices
    vertex_count: int = 0
    triangle_count: int = 0


def generate_mesh(part_image: np.ndarray, max_vertices: int = 120) -> MeshData:
    """Generate a triangle mesh from a part's RGBA image.

    Args:
        part_image: RGBA numpy array
        max_vertices: target max vertices (controls simplification)

    Returns:
        MeshData with vertices, UVs, and triangle indices
    """
    h, w = part_image.shape[:2]
    if h < 3 or w < 3:
        return _make_quad_mesh(w, h)

    alpha = (part_image[:, :, 3] > 30).astype(np.uint8)

    # Find contour
    contours, _ = cv2.findContours(alpha, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return _make_quad_mesh(w, h)

    # Use largest contour
    contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(contour)
    if area < 50:
        return _make_quad_mesh(w, h)

    # Simplify contour
    perimeter = cv2.arcLength(contour, True)
    target_boundary = min(max_vertices * 2 // 3, 80)
    epsilon = perimeter * 0.005
    simplified = cv2.approxPolyDP(contour, epsilon, True)

    # If still too many points, increase epsilon
    while len(simplified) > target_boundary and epsilon < perimeter * 0.1:
        epsilon *= 1.5
        simplified = cv2.approxPolyDP(contour, epsilon, True)

    boundary_pts = simplified.reshape(-1, 2).astype(float)

    # Add interior grid points for mesh density
    interior_pts = _sample_interior(alpha, boundary_pts, max_vertices - len(boundary_pts))

    if len(interior_pts) > 0:
        all_pts = np.vstack([boundary_pts, interior_pts])
    else:
        all_pts = boundary_pts

    if len(all_pts) < 3:
        return _make_quad_mesh(w, h)

    # Delaunay triangulation
    try:
        tri = Delaunay(all_pts)
    except Exception:
        return _make_quad_mesh(w, h)

    # Filter triangles: remove those whose centroid is outside the alpha mask
    valid_indices = []
    for simplex in tri.simplices:
        cx = int(np.mean(all_pts[simplex, 0]))
        cy = int(np.mean(all_pts[simplex, 1]))
        if 0 <= cy < h and 0 <= cx < w and alpha[cy, cx] > 0:
            valid_indices.extend(simplex.tolist())

    if not valid_indices:
        return _make_quad_mesh(w, h)

    # UV coordinates (normalize to 0-1 within part bounds)
    uvs = all_pts.copy()
    uvs[:, 0] /= max(w, 1)
    uvs[:, 1] /= max(h, 1)

    vertices = [[round(float(p[0]), 1), round(float(p[1]), 1)] for p in all_pts]
    uv_list = [[round(float(u[0]), 5), round(float(u[1]), 5)] for u in uvs]

    return MeshData(
        vertices=vertices,
        uvs=uv_list,
        indices=valid_indices,
        vertex_count=len(vertices),
        triangle_count=len(valid_indices) // 3,
    )


def _sample_interior(alpha: np.ndarray, boundary: np.ndarray, max_pts: int) -> np.ndarray:
    """Sample interior grid points that are inside the alpha mask."""
    h, w = alpha.shape
    if max_pts <= 0:
        return np.array([]).reshape(0, 2)

    # Calculate grid spacing to get roughly max_pts points
    area = alpha.sum()
    if area < 100:
        return np.array([]).reshape(0, 2)

    spacing = max(8, int(np.sqrt(area / max(max_pts, 1))))

    pts = []
    for y in range(spacing, h - spacing, spacing):
        for x in range(spacing, w - spacing, spacing):
            if alpha[y, x] > 0:
                # Check it's not too close to boundary
                dists = np.sqrt(np.sum((boundary - [x, y]) ** 2, axis=1))
                if dists.min() > spacing * 0.5:
                    pts.append([x, y])

    if not pts:
        return np.array([]).reshape(0, 2)

    pts = np.array(pts, dtype=float)
    if len(pts) > max_pts:
        indices = np.random.choice(len(pts), max_pts, replace=False)
        pts = pts[indices]

    return pts


def _make_quad_mesh(w: int, h: int) -> MeshData:
    """Fallback: simple quad mesh covering the entire part."""
    w = max(1, w)
    h = max(1, h)
    return MeshData(
        vertices=[[0, 0], [w, 0], [w, h], [0, h]],
        uvs=[[0, 0], [1, 0], [1, 1], [0, 1]],
        indices=[0, 1, 2, 0, 2, 3],
        vertex_count=4,
        triangle_count=2,
    )
