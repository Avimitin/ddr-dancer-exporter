# Static frontend

The browser converter is implemented. See [the user guide](../README.md) for
usage and [the architecture and adapter reference](LOCAL-SERVICE.md) for
implementation details.

PMX conversion runs entirely in the static page. Blender import uses the optional
local Blender bridge; the page detects it and enables that adapter dynamically.
Raw `.blend` evaluation still uses Blender. Direct FBX, glTF/GLB, VRM and Unity
project adapters are not implemented.
