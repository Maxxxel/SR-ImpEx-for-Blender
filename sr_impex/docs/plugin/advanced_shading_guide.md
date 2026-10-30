# Advanced Shading Guide

For the current Blender 5 material system, use the [Artist Material Workflow](material_artist_workflow.md). This page is a practical overview; this guide covers extra painting and shading tasks and preview limits.

## 1. Start with the DRS material layout

Select the render mesh and open **DRS Editor > Material Editor**. Choose **Create / Upgrade DRS Material** when needed. An upgrade creates a new material; keep the previous version until you have checked the result. Choose the appropriate engine material handler and assign its textures and parameters. An arbitrary Blender node graph is not baked into a game shader.

## 2. Texture suffixes and channels

For inspected Default variants, the parameter map uses **R smoothness, G metalness, B flow mask or reflection input depending on the shader variant, and A emissivity**. The same texture identifier has other meanings in legacy specular handlers, so use the selected material type rather than guessing from a filename. Color-map opacity is separate from parameter-map alpha.

When using separate artist maps, the current packer converts roughness to `1 - roughness` for R, writes metalness to G, the flow/reflection input to B and emissivity to A. Use matching dimensions; missing separate maps fall back to the packed map or zero.

## 3. Material flags: supported controls versus unknowns

Flag labels depend on the material handler; a bit does not necessarily have a universal meaning. **Calculate Map Flags** or **Auto map flags** calculates the Default material's parameter and normal map bits from enabled images while retaining other bits. Preserve unknown imported flags unless you have a reason to change them. Review the resulting material in the game.

## 4. Normal maps

Assign the normal image to its supported texture slot and enable the appropriate flag. Treat it as non-color data. The exporter calculates geometry tangents from the active UV layer; check UV seams and compare a fresh import.

## 5. Refraction and environment cubemaps

Default refraction uses a refraction texture, color and scale. For the inspected shader, RG shifts a screen-color sample, B influences mip bias and alpha contributes the filtered background. The camera compositor reproduces part of this behavior; its B-channel blur, render ordering, lighting and edge behavior are incomplete. Viewport refraction is a separate approximation. Refraction does not automatically enable an environment-map flag. Validate this effect in the Map Editor.

Environment map handling also varies by material; Blender's environment response is an approximation of the game's renderer. Test it with the intended game resources.

## 6. Flow animation

Assign a fluid map and parameter map, adjust the Default Flow controls, and play or scrub the timeline. Parameter-map B is the flow mask in the inspected flow shader. The preview uses recovered turbulence math and a deterministic animation sequence; game random history, texture format, shading coordinates and lighting can differ. **Write Flow** controls whether the named flow vectors are serialized, not whether the presence of a fluid map selects the game shader's flow path. Use the Custom Flow Settings controls to change movement.

Flow uses the mesh's rest positions and advances while the timeline plays. Moving a bone should not drag the procedural fluid pattern through the surface; keeping the body still should not stop the flow. The plugin supplies the rest-position attribute automatically and upgrades older flow graphs when the timeline advances.

During playback, flow continues when the SKA animation loops. Pausing holds the fluid; pressing Space again resumes it. Changing clips or clip FPS does not restart its motion. Scrubbing while paused sets the fluid to that timeline time. Renders use timeline time too, so rendering the same frame gives the same fluid pattern. This can differ from the continuously running viewport after several clip loops.

The preview integrates flow at a fixed 60 updates per second. This is a repeatable Blender preview policy; the game's shared random state and rendering history can still produce a different pattern.

## 7. Wind

In Default **Material Parameters**, enable WindResponse and WindHeight.
The preview modifier is managed automatically. Play the timeline to see the
movement. The engine uses height along local game Y and a world-space wind
displacement. The preview follows the default engine wind field; individual
maps can supply different wind. Wind pauses while painting and resumes when leaving Texture Paint.

## 8. Export and verification checklist

- Use the correct active material and UV layer for each exported mesh. Confirm enabled images are present.
- Export to a separate folder, then inspect the DRS and DDS files and any referenced resources.
- Reimport the exported model into a fresh scene and compare the material and mesh.
- Check animations, wind, flow, refraction, alpha edges and lighting in the Map Editor or game. Blender preview is not a pixel-match guarantee.

For supported and unresolved material families, raw records and texture conversion, see the [Artist Material Workflow](material_artist_workflow.md). For the complete model workflow, start with the [Artist Model Pipeline](model_artist_pipeline.md).


## Soft transparency for a simple surface

For a simple transparent mesh, try **SimpleTextured**. Assign its Texture with
a grayscale opacity gradient in the image alpha channel: white is visible,
black is transparent, and gray gives partial visibility. Start with white
Color, material Alpha **1**, and UseVertexColor disabled. Lower material
Alpha for an additional fade across the whole surface. Use a texture format
that retains alpha.

Alpha Test is a cutout operation and does not enable smooth transparency by
itself. Do not put the opacity gradient in Default's ParamMap alpha; that
channel controls emissivity.

If transparent surfaces overlap incorrectly, try DisableDepthWrite while
keeping depth testing enabled, and check the result in the Map Editor.
Changing to SimpleTextured also changes the shader: it does not preserve
Default's normal/PAR lighting or FluidMap flow. Test a flowing waterfall
separately before replacing its existing material. This recipe is supported
by engine/shader analysis; it has not been visually checked on every model.


### Keep flow on a soft-edged waterfall

If a waterfall already uses Default's FluidMap, keep that material for the
first test. The game supports flow together with its refraction screen lookup.
Start with **RefractionScale 0**, a white **RefractionColor**, and a refraction
map with neutral RG and black B. This brings in the background without adding
distortion or an extra blur bias.

For a soft bottom edge, reduce the water contribution while increasing the
background contribution in the same area. Refraction-map alpha adds background;
it does not automatically fade out the water. Use the ParamMap blue flow mask
to fade flow locally, and make sure the underlying ColorMap and any glow or
highlights do not leave a solid edge. Disable Alpha Test for this test.

A readable moving body with a fade near the bottom is a useful starting point.
Only add subtle distortion after the edge works. Review the actual model in
the Map Editor: this setup follows the engine shader, but a finished visual
match depends on the model's existing textures and lighting.
