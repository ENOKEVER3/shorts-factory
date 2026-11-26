# Earth globe provenance

- **Actual NASA Earth model:** https://science.nasa.gov/3d-resources/earth/
- Original `Earth.stl` download: https://assets.science.nasa.gov/content/dam/science/cds/3d/resources/printable/earth/Earth.zip
- `nasa-earth-mesh.npz` is that mesh reduced from 4,063,232 to 12,000 triangles using trimesh/fast-simplification, converted from Z-up to Y-up and normalized. Exaggerated printable radial relief is compressed to 2% of its original amplitude for a smooth documentary silhouette. No procedural continents are generated.
- **NASA WorldWind Blue Marble geographic texture:** https://github.com/NASAWorldWind/WebWorldWind/blob/develop/images/BMNG_world.topo.bathy.200405.3.2048x1024.jpg
- `nasa-earth.jpg` is the original 2048 × 1024 satellite-derived Blue Marble composite, not a 4K image or a single live photograph. Land, oceans and ice appearance come from this texture. Geographic positioning uses spherical longitude/latitude UVs; this is an explanatory visualization, not a geodetic measurement tool.
- NASA media use guidance: https://www.nasa.gov/nasa-brand-center/images-and-media/

The original 203 MB STL is not shipped. The reduced mesh and texture render offline using ModernGL/Mesa, with no paid API. Spin is time-compressed for explanation. Earth-centred orbital overlays are schematic, not mission ephemerides.