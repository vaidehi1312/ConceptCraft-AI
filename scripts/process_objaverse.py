import json

input_file = "objaverse_dataset/objaverse_sample.json"
output_file = "objaverse_dataset/objaverse_dataset.json"

with open(input_file) as f:
    data = json.load(f)

processed = []

for obj in data:
    processed.append({
        "id": obj["id"],
        "model_file": obj["file"],
        "dataset": "Objaverse"
    })

with open(output_file, "w") as f:
    json.dump(processed, f, indent=4)

print("Objaverse dataset JSON created!")
print("Total objects:", len(processed))