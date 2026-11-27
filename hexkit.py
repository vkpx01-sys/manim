"""
hexkit.py - shared polygon / hex-lattice geometry for the Reducible-style scenes.
Pure geometry: every colour comes from reducible_style constants.
Keep next to reducible_style.py.  Part 3 and Part 4 both use it:
    from hexkit import *
"""
from reducible_style import *


def reg_poly(n, R, pos, phase=0.0, stroke=RING_IDLE, sw=1.8, op=0.6, fill=0.0):
    """Regular n-gon, circumradius R, CENTROID at pos (shift, not move_to)."""
    pts = [np.array([R * np.cos(phase + k * TAU / n),
                     R * np.sin(phase + k * TAU / n), 0]) for k in range(n)]
    return Polygon(*pts, stroke_color=stroke, stroke_width=sw, stroke_opacity=op,
                   fill_color=CARD, fill_opacity=fill).shift(pos).set_z_index(2)


HEX_DIRS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def hex_coords(rings):
    return [(q, r) for q in range(-rings, rings + 1)
            for r in range(-rings, rings + 1) if abs(q + r) <= rings]


def hex_pt(q, r, R, origin):
    """Pointy-top axial -> pixel. All 6 neighbours are sqrt(3)*R away."""
    return np.array([origin[0] + R * np.sqrt(3) * (q + r / 2),
                     origin[1] + R * 1.5 * r, 0])


def hex_ring(rings, R, origin, only_outer=False, **kw):
    cs = hex_coords(rings)
    if only_outer:
        cs = [(q, r) for q, r in cs if max(abs(q), abs(r), abs(q + r)) == rings]
    return VGroup(*[reg_poly(6, R, hex_pt(q, r, R, origin), phase=PI / 6, **kw)
                    for q, r in cs])


# ---- H3 aperture-7 subdivision: scale 1/sqrt(7), rotate 19.107 deg ----------
AP7_THETA = float(np.arctan2(np.sin(PI / 3), 2 + np.cos(PI / 3)))   # 0.33347 rad
AP7_SCALE = float(1 / np.sqrt(7))                                  # 0.37796


def _rot2(p, a):
    c, s = np.cos(a), np.sin(a)
    return np.array([c * p[0] - s * p[1], s * p[0] + c * p[1]])


def aperture7(center, R, **kw):
    """(parent, 7 children, overhang segments). The 6 outer children each poke
    one vertex past the parent edge - H3 containment is approximate."""
    center = np.array([center[0], center[1], 0.0])
    parent = reg_poly(6, R, center, phase=PI / 6, **kw)
    Rc = R * AP7_SCALE
    offs = [np.array([0.0, 0.0])] + [np.array([np.sqrt(3) * Rc * (q + r / 2),
                                               1.5 * Rc * r]) for q, r in HEX_DIRS]
    apo = R * np.cos(PI / 6)
    normals = [np.array([np.cos(k * PI / 3), np.sin(k * PI / 3)]) for k in range(6)]
    kids, spill = VGroup(), VGroup()
    for o in offs:
        c = _rot2(o, AP7_THETA)
        vs = []
        for k in range(6):
            a = PI / 6 + AP7_THETA + k * TAU / 6
            vs.append(c + Rc * np.array([np.cos(a), np.sin(a)]))
        pts = [np.array([center[0] + v[0], center[1] + v[1], 0]) for v in vs]
        kids.add(Polygon(*pts, stroke_color=RING_IDLE, stroke_width=1.8,
                         stroke_opacity=0.85, fill_color=CARD,
                         fill_opacity=0.0).set_z_index(3))
        for k in range(6):
            a, b = vs[k], vs[(k + 1) % 6]
            if max(a @ n for n in normals) > apo + 1e-9 or \
               max(b @ n for n in normals) > apo + 1e-9:
                spill.add(Line(np.array([center[0] + a[0], center[1] + a[1], 0]),
                               np.array([center[0] + b[0], center[1] + b[1], 0]),
                               stroke_color=AMBER, stroke_width=3.5).set_z_index(4))
    return parent, kids, spill


def icosahedron_wire(center, R, rx=0.60, ry=0.20):
    """2D orthographic wireframe (no 3D scene). Returns
    (front_edges, back_edges, projected_vertices, front_flags). 12 V, 30 E, 20 F."""
    phi = (1 + 5 ** 0.5) / 2
    V = np.array([[0, a, b] for a in (-1, 1) for b in (-phi, phi)] +
                 [[a, b, 0] for a in (-1, 1) for b in (-phi, phi)] +
                 [[a, 0, b] for a in (-phi, phi) for b in (-1, 1)], float)
    V /= np.linalg.norm(V, axis=1, keepdims=True)
    cx, sx, cy, sy = np.cos(rx), np.sin(rx), np.cos(ry), np.sin(ry)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    W = V @ Rx.T @ Ry.T
    P = [np.array([center[0] + R * w[0], center[1] + R * w[1], 0]) for w in W]
    d = np.linalg.norm(V[:, None] - V[None, :], axis=-1)
    elen = 2 / np.linalg.norm(np.array([0, 1, phi]))
    front, back = VGroup(), VGroup()
    for i in range(12):
        for j in range(i + 1, 12):
            if abs(d[i, j] - elen) < 1e-6:
                seg = Line(P[i], P[j])
                (front if (W[i, 2] + W[j, 2]) / 2 > 0 else back).add(seg)
    front.set_stroke(RING_IDLE, 2.4, 0.95).set_z_index(3)
    back.set_stroke(RING_IDLE, 1.4, 0.30).set_z_index(1)
    return front, back, P, [bool(w[2] > 0) for w in W]