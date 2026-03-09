import zipfile

zip_path = "mnist3d_dataset/archive.zip"
extract_path = "mnist3d_dataset"

with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(extract_path)

print("MNIST3D extraction complete!")