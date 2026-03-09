import json

with open("modelnet40_dataset/modelnet40_sample.json") as f:
    data = json.load(f)

print("Total models:", len(data))

for obj in data:
    print(obj["category"], "->", obj["model"])