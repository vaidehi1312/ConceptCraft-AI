import httpx
import asyncio
import subprocess
import os
import trimesh
import sys

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
    raise Exception("No image found on Wikipedia")

async def download_image(url: str, path: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers={
            "User-Agent": "ConceptCraftAI/1.0 (hackathon)"
        })
        with open(path, "wb") as f:
            f.write(resp.content)

def run_triposr(image_path: str, concept: str) -> str:
    safe_concept = concept.replace(" ", "_").replace("/", "_")
    output_dir = f"fallback_generator/generated/{safe_concept}"
    os.makedirs(output_dir, exist_ok=True)
    
    subprocess.run([
        sys.executable, "fallback_generator/run.py",
        image_path,
        "--output-dir", output_dir,
        "--mc-resolution", "256",
        "--model-save-format", "obj",
        "--bake-texture"
    ], check=True)
    
    obj_path = f"{output_dir}/0/mesh.obj"
    mtl_path = f"{output_dir}/0/mesh.mtl"
    glb_path = f"{output_dir}/0/mesh.glb"
    
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
    
    # Convert with textures
    scene = trimesh.load(
        obj_path,
        force='scene',
        resolver=trimesh.visual.resolvers.FilePathResolver(obj_path)
    )
    scene.export(glb_path)
    
    return os.path.abspath(glb_path)

async def generate_from_concept(concept: str) -> dict:
    try:
        img_url = await fetch_wikipedia_image(concept)
        safe_concept = concept.replace(" ", "_").replace("/", "_")
        img_path = f"/tmp/{safe_concept}.jpg"
        await download_image(img_url, img_path)
        
        loop = asyncio.get_event_loop()
        glb_path = await loop.run_in_executor(None, run_triposr, img_path, concept)
        
        return {"success": True, "glb_path": glb_path, "source": "wikipedia_triposr"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_static_glb_url(glb_path: str) -> str:
    if "generated/" in glb_path:
        parts = glb_path.split("generated/")
        return f"/generated/{parts[-1]}"
    return ""
