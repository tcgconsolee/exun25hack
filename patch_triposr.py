import os

isosurface_path = "TripoSR/tsr/models/isosurface.py"

if not os.path.exists(isosurface_path):
    print(f"❌ Error: {isosurface_path} not found!")
    print("Make sure you're running this from the project root directory.")
    exit(1)

# Read the original file
with open(isosurface_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Backup original
backup_path = isosurface_path + ".backup"
if not os.path.exists(backup_path):
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Created backup: {backup_path}")

# Replace torchmcubes import with PyMCubes fallback
new_import = """try:
    from torchmcubes import marching_cubes
    USE_TORCHMCUBES = True
except ImportError:
    import mcubes
    USE_TORCHMCUBES = False
    print("[INFO] Using PyMCubes instead of torchmcubes")
    
    def marching_cubes(vol, isolevel):
        # Convert to numpy for PyMCubes
        import numpy as np
        vol_np = vol.cpu().numpy() if hasattr(vol, 'cpu') else vol
        vertices, triangles = mcubes.marching_cubes(vol_np, isolevel)
        
        # Convert back to torch tensors
        import torch
        vertices = torch.from_numpy(vertices).float()
        triangles = torch.from_numpy(triangles).long()
        return vertices, triangles"""

# Replace the import line
content = content.replace(
    "from torchmcubes import marching_cubes",
    new_import
)

# Write patched file
with open(isosurface_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"✓ Successfully patched {isosurface_path}")
print("\n✅ TripoSR is now configured to use PyMCubes!")
print("You can now run: python app.py")