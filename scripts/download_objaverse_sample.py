import json

# example sample objects
objects = [
    {"id": "object_1", "file": "chair.glb"},
    {"id": "object_2", "file": "table.glb"},
    {"id": "object_3", "file": "lamp.glb"}
]

with open("objaverse_dataset/objaverse_sample.json", "w") as f:
    json.dump(objects, f, indent=4)

print("Objaverse sample dataset created!")