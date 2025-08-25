#!/bin/bash
#SBATCH --job-name=download_Nuscenes
#SBATCH --output=download_Nuscenes_%j.txt
#SBATCH --error=download_Nuscenes_%j.txt

#SBATCH --nodes=1  # Single node
#SBATCH --cpus-per-task=4  # Number of CPUs
#SBATCH --mem=32G  # Total memory
#SBATCH --time=20:00:00  # Time limit
#SBATCH --partition=debugging
#SBATCH --qos=debugging
#SBATCH --account=debugging

# Activate your virtual environment

# Create a Python script for parallel downloads
cat << EOF > download_files.py
import os
import concurrent.futures
import subprocess

# List of links to download
LINKS = [
    f"https://motional-nuscenes.s3.amazonaws.com/public/v1.0/v1.0-trainval{str(i).zfill(2)}_blobs.tgz"
    for i in range(11)
]


# Download function
def download_file(url):
    output_dir = "/s3_storage/chouai-temp/nuscenes/downloads$"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, os.path.basename(url))
    try:
        subprocess.run(["wget", "-q", url, "-O", output_path], check=True)
        print(f"Downloaded: {url}")
    except subprocess.CalledProcessError:
        print(f"Failed to download: {url}")

# Main execution
if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(download_file, LINKS)
EOF

# Run the Python script
python download_files.py

