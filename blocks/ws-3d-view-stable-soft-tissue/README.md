# 3D view (stable soft tissue)

The project's 3D view: draws whatever the project gives it (scenes, 3D files, live positions, robots with any number of joints, several at once, fleets, rockets, vehicles), with the models, textures a

One 3D view for every kind of project: it draws what the project gives it, through its inputs (scenes, 3D files, telemetry) and the project's assets (Data > Assets), so a new project needs data and assets, not a new view. With nothing to show yet, the view is an empty floor with the esacode logo at the origin and the axes rising from it (x red, y green, z blue). Connect a scene (for example the Landing sweep's trajectories), 3D files (GLB, glTF, OBJ, STL, PLY, for example from the Library block) or Telemetry with positions: while a run goes on, the bodies it streams ({"drone": [x, y, z], "pad": [x, y, z]}) move live, smoothly and at real speed, and the recorded runs replay when it ends. With a scene and models together, a model can take the place of an entity (Model for). What it draws comes from the project: the 3D models, textures and sounds in the project's Assets (Data > Assets: models/robot-spot.json, models/forklift.glb, textures/flashlight.jpg…) are the ones it uses, found by name; the view's own copies serve only projects that have none. Robots (arms, hands, legs, mobile bases, whole cells: any number of joints, chains or trees, several robots at once): connect a robot model (esasim.robot/1, such as xarm6.robot.json.gz from xArm 6 model: joints with name, parent, type revolute, continuous, prismatic or fixed, xyz, rpy and axis, a mesh per link; or put it in the project's assets) and the live telemetry of the block that moves it: the joints channel poses it, with any number of joints ({"j1": 12.5, "j2": …}, a list {"q": […]}, or by name {"joints": {"shoulder": 12.5}}; degrees, or "units": "rad"), serial arms or trees (hands, legs, several arms on one body; revolute, prismatic and fixed joints), and several robots at once ("robot": its name), the twin channel poses a see-through copy (the digital twin beside the real worker), and the scene channel places the table, sheets with live pictures, cameras and the tool around it. Orbit with the mouse, play back with the timeline, follow the drone. Lighting, shadows and the environment are set in the settings. Fly the camera with a 3Dconnexion SpaceMouse (3D mouse button, in Chrome, Edge or Opera), save pictures, and record videos of what you see or render the replay frame by frame (MP4, WebM or PNG frames) to download or keep in a dataset. Fleets: a block that streams a grid world (esasim.warehouse/1, such as Warehouse fleet) and its robots is drawn as a hall with racks, stations and docks from the 3D files wired in (rack_d, amr…): robots move smoothly, show what they do with their light strip, draw their routes (Routes), colour where they wait (Heat map), and the run plays back on the timeline when it ends; click a robot to follow it, Cinematic for a slow orbit. With inbound flow, receiving stations get a conveyor through the wall with the deliveries waiting on it, pack-out desks one where packed orders leave, and the shelves show the run's real packages, put away and picked one by one; Shelf use

An [EsaSim](https://esacode.com/) blueprint block: a view that draws in the browser, in JavaScript (`frontend.js`, `function render(ctx)`).

| | |
|---|---|
| Block | `ws-3d-view-stable-soft-tissue` · version 48 |
| Workspace | Gianluca De Novi's workspace |
| Author | Gianluca De Novi |

## Inputs

| Port | Type | Description |
|---|---|---|
| `scene` Scene or 3D files | Anything (json, gz, glb, gltf, obj, stl, ply) | A scene (esasim.scene/1 JSON), 3D models and point clouds, a robot model (.robot.json.gz) and/or live telemetry; a soft-body model (esasim.softbody/1, from Soft body model) with the anatomy of the sam Several connections. |

## Settings

| Key | Type | Default | Description |
|---|---|---|---|
| `environment` Environment | select | `"outdoor"` |  |
| `quality` Quality | select | `"high"` |  |
| `floor` Show the floor | bool | `true` | Off: models float at the centre of the view, with no ground |
| `models` Models | select | `"side by side"` | Several 3D files: all of them side by side, or one at a time with a list to choose which |
| `first_model` First model | text | `""` | Models one at a time: the file shown first, by name or part of it (ToyCar); empty: the first |
| `link_views` Link views | bool | `true` | With 3D files: moving this view moves the other 3D views on the page the same way (and choosing a model chooses it in them), so the same detail can be compared in each, the 3D view (WebGPU) too |
| `model_list` Model list in the view | bool | `true` | Models one at a time: the list in the corner to choose the model; off when a Model list block beside the views chooses for all of them |
| `stage` Stage | select | `"off"` | With 3D files: the EsaSim stage, the same as the 3D view (WebGPU) and the Ray-traced render: the model at the origin on a plain floor, the same lights at the same places (studio soft boxes, the sun, the night), the same camera, so the three can be compared; off: the view's own ground, sky and lights |
| `stage_fov` Stage field of view (degrees) | number | `35` |  |
| `stage_sun` Stage sun height (degrees) | number | `35` |  |
| `textures` Tissue textures | bool | `true` | Anatomy: each tissue gets its own surface, computed on the graphics card (liver lobules, muscle fibres, bowel folds, the heart's fat, the lung's air sacs, bone darker in its hollows…). Also a switch in the Parts list |
| `metaballs` Show the metaballs | bool | `false` | Soft tissue: draw the spheres of the soft-body model moving with the tissue, the anatomy see-through around them. Also a switch in the Parts list |
| `grid` Show the grid | bool | `true` |  |
| `trails` Show trajectories | bool | `true` |  |
| `speed` Playback speed | number | `1` |  |
| `model_for` Model for | text | `""` | With a scene and 3D files (for example from the Library block): the scene entity the first model replaces, such as drone. Entities can also name their model in the scene ("model": "quadcopter.glb"). |
| `live_channel` Live channel | text | `""` | Positions streamed while a run goes on are drawn live. Leave empty to use any telemetry item with positions ({"drone": [x, y, z]}), or name its channel, such as pose. |
| `joints_channel` Robot: joints channel | text | `"joints"` | Telemetry channel whose items carry the robot's joint angles in degrees: {"j1": 12.5, "j2": -30, …} |
| `ghost_channel` Robot: twin channel | text | `"twin"` | Joint angles of a see-through copy, such as the digital twin beside the real robot |
| `scene_channel` Robot: objects channel | text | `"scene"` | Objects around the robot: {"units": "mm", "objects": [boxes, sheets with live pictures, cameras, the tool]} |
| `delay` Robot: behind real time (seconds) | number | `1.2` | Live data comes in batches: a small delay keeps the motion smooth |
| `mouse_speed` 3D mouse speed | number | `1` | How fast a 3Dconnexion SpaceMouse moves the camera. |
| `mouse_mode` 3D mouse moves | select | `"The camera"` | The camera: it flies as the cap moves (push to go forward, twist to turn). Move the scene: the scene follows the cap instead, as if you held it. The model (3D files): the model turns around its centre as you tilt and twist the cap, moves as you push it, and comes closer as you pull it; the camera st |
| `model_title` Model title | bool | `true` | 3D files one at a time: "Model 3 of 20" in the corner |
| `parts` Parts list | bool | `true` | The Parts button and list of a model with several parts |
| `show_fps` Frames per second | bool | `false` | How many frames a second the view draws, by its buttons |
| `numbers` Numbers | text | `""` | Live fields shown as tiles: channel.field=Label:format, separated by commas (format time or %), such as kpi.orders_h=Orders / hour, kpi.avg_order_s=Average order:time. Empty = none (a fleet shows its own). |
| `events_channel` Events channel | text | `"event"` | Items of this channel with a text appear on the right, newest last |
| `controls` Controls | textarea | `""` | One per line, as in the Controls view: button LABEL · slider NAME MIN MAX START [STEP] · select NAME a,b,c · switch NAME · text NAME · pick NAME (then a click on the floor sends NAME = [x, y]: a cell of a grid world, else metres). A control named like a live field follows its value. |
| `control_channel` Controls: channel | text | `"control"` | The controls send {"control": NAME, "value": …} on this channel, like the Controls view |
| `routes` Fleets: show the routes | bool | `true` |  |
| `heat` Fleets: show the heat map | bool | `false` |  |
| `camera` Camera | select | `"free"` | Rockets: free gives the orbit and tracking cameras with the buttons in the bar; the others fix this view on a camera on board the booster, on the second stage, on the drone ship's deck or on the ground, for a wall of views of the same flight. Cars (esasim.car/1, such as Ramp stunt): car: chase and c |

## Use it in EsaSim

In a workspace, open **Projects > Blocks > New block**, choose this kind of block, copy the ports and settings above and paste the code; or ask an AI assistant connected to EsaSim (MCP) to create it from this folder.
