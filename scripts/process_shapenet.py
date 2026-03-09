import json

with open("shapenet_dataset/shapenet_sample.json") as f:
    data = json.load(f)

print("Number of models:", len(data))

for obj in data:
    print(obj["category"], "->", obj["model"])