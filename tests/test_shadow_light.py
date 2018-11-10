import pyredner
import numpy as np
import torch

# Optimize light translation to match shadow

# Use GPU if available
pyredner.set_use_gpu(torch.cuda.is_available())

# Set up the scene using Pytorch tensor
position = torch.tensor([0.0, 2.0, -5.0])
look_at = torch.tensor([0.0, 0.0, 0.0])
up = torch.tensor([0.0, 1.0, 0.0])
fov = torch.tensor([45.0])
clip_near = 1e-2

resolution = (256, 256)
cam = pyredner.Camera(position = position,
                     look_at = look_at,
                     up = up,
                     fov = fov,
                     clip_near = clip_near,
                     resolution = resolution)

mat_grey = pyredner.Material(\
    diffuse_reflectance = torch.tensor([0.5, 0.5, 0.5],
    device = pyredner.get_device()))
mat_black = pyredner.Material(\
    diffuse_reflectance = torch.tensor([0.0, 0.0, 0.0],
    device = pyredner.get_device()))
materials = [mat_grey, mat_black]

floor_vertices = torch.tensor([[-2.0,0.0,-2.0],[-2.0,0.0,2.0],[2.0,0.0,-2.0],[2.0,0.0,2.0]],
	device = pyredner.get_device())
floor_indices = torch.tensor([[0,1,2], [1,3,2]],
    device = pyredner.get_device(), dtype = torch.int32)
shape_floor = pyredner.Shape(floor_vertices, floor_indices, None, None, 0)
blocker_vertices = torch.tensor(\
    [[-0.5,3.0,-0.5],[-0.5,3.0,0.5],[0.5,3.0,-0.5],[0.5,3.0,0.5]],
    device = pyredner.get_device())
blocker_indices = torch.tensor([[0,1,2], [1,3,2]],
    device = pyredner.get_device(), dtype = torch.int32)
shape_blocker = pyredner.Shape(blocker_vertices, blocker_indices, None, None, 0)
light_vertices = torch.tensor(\
    [[-0.1,5,-0.1],[-0.1,5,0.1],[0.1,5,-0.1],[0.1,5,0.1]],
    device = pyredner.get_device())
light_indices = torch.tensor([[0,2,1], [1,2,3]],
    device = pyredner.get_device(), dtype = torch.int32)
shape_light = pyredner.Shape(light_vertices, light_indices, None, None, 1)
shapes = [shape_floor, shape_blocker, shape_light]
light_intensity = torch.tensor([1000.0, 1000.0, 1000.0])
# The first argument is the shape id of the light
light = pyredner.Light(2, light_intensity)
lights = [light]
scene = pyredner.Scene(cam, shapes, materials, lights)
args = pyredner.RenderFunction.serialize_scene(\
    scene = scene,
    num_samples = 256,
    max_bounces = 1)

# Alias of the render function
render = pyredner.RenderFunction.apply
# Render our target
img = render(0, *args)
pyredner.imwrite(img.cpu(), 'results/test_shadow_light/target.exr')
pyredner.imwrite(img.cpu(), 'results/test_shadow_light/target.png')
target = pyredner.imread('results/test_shadow_light/target.exr')
if pyredner.get_use_gpu():
    target = target.cuda()

# Perturb the scene, this is our initial guess
light_translation = torch.tensor([-0.4, -0.4, -0.4],
    device = pyredner.get_device(), requires_grad=True)
shape_light.vertices = light_vertices + light_translation
args = pyredner.RenderFunction.serialize_scene(\
    scene = scene,
    num_samples = 256,
    max_bounces = 1)
# Render the initial guess
img = render(1, *args)
pyredner.imwrite(img.cpu(), 'results/test_shadow_light/init.png')
diff = torch.abs(target - img)
pyredner.imwrite(diff.cpu(), 'results/test_shadow_light/init_diff.png')

# Optimize for blocker vertices
optimizer = torch.optim.Adam([light_translation], lr=1e-2)
for t in range(200):
    print('iteration:', t)
    optimizer.zero_grad()
    # Forward pass: render the image
    shape_light.vertices = light_vertices + light_translation
    args = pyredner.RenderFunction.serialize_scene(\
        scene = scene,
        num_samples = 4,
        max_bounces = 1)
    img = render(t+1, *args)
    pyredner.imwrite(img.cpu(), 'results/test_shadow_light/iter_{}.png'.format(t))
    loss = (img - target).pow(2).sum()
    print('loss:', loss.item())

    loss.backward()
    print('grad:', light_translation.grad)

    optimizer.step()
    print('light_translation:', light_translation)

args = pyredner.RenderFunction.serialize_scene(\
    scene = scene,
    num_samples = 256,
    max_bounces = 1)
img = render(202, *args)
pyredner.imwrite(img.cpu(), 'results/test_shadow_light/final.exr')
pyredner.imwrite(img.cpu(), 'results/test_shadow_light/final.png')
pyredner.imwrite(torch.abs(target - img).cpu(), 'results/test_shadow_light/final_diff.png')

from subprocess import call
call(["ffmpeg", "-framerate", "24", "-i",
    "results/test_shadow_light/iter_%d.png", "-vb", "20M",
    "results/test_shadow_light/out.mp4"])
