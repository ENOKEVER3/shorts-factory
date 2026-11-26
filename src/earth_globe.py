"""Render the official NASA Earth mesh with NASA's geographic texture using Mesa/EGL.

No generated continents, drawn planets, network requests or Blender startup at render time.
Geometry and texture provenance are recorded in assets/earth/SOURCES.md.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "earth"


class EarthGlobe:
    def __init__(self, width: int = 1080, height: int = 1920):
        import moderngl

        self.width, self.height = width, height
        self.ctx = moderngl.create_standalone_context(backend="egl", require=330)
        self.program = self.ctx.program(vertex_shader="""
            #version 330
            in vec3 position;
            uniform mat3 rotation;
            uniform vec2 scale;
            out vec3 surface;
            out vec3 normal;
            void main() {
                surface = position;
                normal = rotation * normalize(position);
                vec3 p = rotation * position;
                gl_Position = vec4(p.x * scale.x, p.y * scale.y, -p.z * 0.4, 1.0);
            }
        """, fragment_shader="""
            #version 330
            uniform sampler2D earth;
            in vec3 surface;
            in vec3 normal;
            out vec4 color;
            void main() {
                vec3 p = normalize(surface);
                vec2 uv = vec2(atan(p.z, p.x) / 6.283185307 + 0.5,
                               asin(clamp(p.y, -1.0, 1.0)) / 3.141592654 + 0.5);
                vec3 n = normalize(normal);
                float sunlight = max(dot(n, normalize(vec3(-0.5, 0.3, 0.9))), 0.0);
                vec3 photo = texture(earth, uv).rgb;
                float rim = pow(1.0 - max(n.z, 0.0), 4.0);
                color = vec4(photo * (0.10 + 0.90 * sunlight)
                            + vec3(0.05, 0.18, 0.32) * rim * sunlight, 1.0);
            }
        """)
        with np.load(ASSETS / "nasa-earth-mesh.npz", allow_pickle=False) as data:
            vertices, faces = data["vertices"], data["faces"]
        self.vbo = self.ctx.buffer(vertices.astype("f4").tobytes())
        self.ibo = self.ctx.buffer(faces.astype("i4").tobytes())
        self.vao = self.ctx.vertex_array(self.program, [(self.vbo, "3f", "position")], self.ibo)
        with Image.open(ASSETS / "nasa-earth.jpg") as image:
            image = image.convert("RGB").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            self.texture = self.ctx.texture(image.size, 3, image.tobytes())
        self.texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.texture.repeat_x, self.texture.repeat_y = True, False
        self.target = self.ctx.simple_framebuffer((width, height), components=3)
        self.target.use()
        self.ctx.enable(moderngl.DEPTH_TEST)

    def frame(self, seconds: float, kind: str = "rotation") -> Image.Image:
        # Axial tilt, geographically correct spin, documentary time-compression (not real time).
        angle, tilt = seconds * 0.35, math.radians(23.44)
        ca, sa, ct, st = math.cos(angle), math.sin(angle), math.cos(tilt), math.sin(tilt)
        rotation = np.array([[ca, 0, sa], [0, 1, 0], [-sa, 0, ca]], dtype="f4")
        tilt_matrix = np.array([[ct, -st, 0], [st, ct, 0], [0, 0, 1]], dtype="f4")
        self.program["rotation"].write((tilt_matrix @ rotation).T.tobytes())
        self.program["scale"].value = (0.78, 0.78 * self.width / self.height)
        self.target.clear(0.004, 0.006, 0.012, 1.0, depth=1.0)
        self.texture.use()
        self.vao.render()
        image = Image.frombytes("RGB", (self.width, self.height), self.target.read(components=3))
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if kind == "orbit":
            # Earth-centred satellite path, not a misleading tiny Earth/Mars/Sun diagram.
            from PIL import ImageDraw
            draw = ImageDraw.Draw(image)
            cx, cy = self.width / 2, self.height / 2
            a, b = self.width * 0.45, self.height * 0.10
            phase = seconds * 0.7
            points = [(cx + a * math.cos(phase - j * 0.016),
                       cy + b * math.sin(phase - j * 0.016)) for j in range(80)]
            # Far side is occluded by the globe; only the near-side trail is visible.
            visible = [p for j, p in enumerate(points) if math.sin(phase - j * 0.016) >= 0]
            if len(visible) > 1:
                draw.line(visible, fill=(150, 180, 200), width=2)
            if math.sin(phase) >= 0:
                x, y = points[0]
                draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(230, 230, 230))
        return image

    def close(self):
        for item in (self.vao, self.vbo, self.ibo, self.texture, self.program, self.target):
            item.release()
        self.ctx.release()