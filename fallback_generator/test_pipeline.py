import httpx
import asyncio
import subprocess
import os
import trimesh

async def fetch_wikipedia_image(concept: str) -> str:
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "pageimages",
        "titles": concept,
        "pithumbsize": 800,
        "redirects": 1
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10.0, headers={
            "User-Agent": "ConceptCraftAI/1.0 (hackathon)"
        })
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if page_id == "-1":
                continue
            if "thumbnail" in page_data:
                return page_data["thumbnail"]["source"]
    raise Exception("No image found")

async def download_image(url: str, path: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers={
            "User-Agent": "ConceptCraftAI/1.0 (hackathon)"
        })
        with open(path, "wb") as f:
            f.write(resp.content)

def run_triposr(image_path: str, concept: str) -> str:
    output_dir = f"./generated/{concept}"
    os.makedirs(output_dir, exist_ok=True)
    
    subprocess.run([
        "python3", "run.py",
        image_path,
        "--output-dir", output_dir,
        "--mc-resolution", "256",
        "--model-save-format", "obj",
        "--bake-texture"
    ])
    
    obj_path = f"{output_dir}/0/mesh.obj"
    mtl_path = f"{output_dir}/0/mesh.mtl"
    glb_path = f"{output_dir}/0/mesh.glb"
    texture_path = f"{output_dir}/0/texture.png"
    
    if not os.path.exists(obj_path):
        raise Exception("TripoSR failed to generate OBJ")
    
    # Manually create MTL file pointing to texture.png
    with open(mtl_path, "w") as f:
        f.write("newmtl material0\n")
        f.write("Ka 1.0 1.0 1.0\n")
        f.write("Kd 1.0 1.0 1.0\n")
        f.write("Ks 0.0 0.0 0.0\n")
        f.write("map_Kd texture.png\n")
    
    # Patch mesh.obj to reference the MTL file
    with open(obj_path, "r") as f:
        obj_content = f.read()
    
    if "mtllib" not in obj_content:
        with open(obj_path, "w") as f:
            f.write("mtllib mesh.mtl\n")
            f.write("usemtl material0\n")
            f.write(obj_content)
    
    # Now convert with textures
    print("Converting OBJ to GLB with textures...")
    scene = trimesh.load(
        obj_path,
        force='scene',
        resolver=trimesh.visual.resolvers.FilePathResolver(obj_path)
    )
    scene.export(glb_path)
    print("Conversion done.")
    
    return glb_path

async def main():
    concept = input("Enter concept: ")
    
    print(f"\nFetching Wikipedia image for '{concept}'...")
    try:
        img_url = await fetch_wikipedia_image(concept)
        print(f"Found: {img_url}")
        
        img_path = f"/tmp/{concept.replace(' ', '_')}.jpg"
        await download_image(img_url, img_path)
        print(f"Downloaded to {img_path}")
        
    except Exception as e:
        print(f"Wikipedia failed: {e}")
        return
    
    print("\nRunning TripoSR (this takes ~15-20 seconds)...")
    glb_path = run_triposr(img_path, concept)
    
    abs_path = os.path.abspath(glb_path)
    
    print(f"\n✅ Done!")
    print(f"📁 File: {abs_path}")
    print(f"\n🌐 View it here (drag and drop the file above):")
    print(f"   https://gltf.report")
    print(f"\n🔗 Or open directly:")
    print(f"   file://{abs_path}")

asyncio.run(main())