# Scene-anchor review interface

This Streamlit interface was present in the original annotation pipeline. It reads reviewer-assigned records and nuScenes camera images from privately configured object storage. The repository **does not** include that object-store data or access credentials.

## Local configuration

Run from this folder. Create a local `credentials.json` outside Git or excluded by `.gitignore` with JSON keys `accessKey` and `secretKey`. Set these environment variables to values from **your own authorized storage**:

    export ODD_STORAGE_ENDPOINT=your-endpoint.example.org
    export ODD_STORAGE_BUCKET=your-bucket
    export ODD_STORAGE_OBJECT=your-review-records.json
    export ODD_STORAGE_CREDENTIALS=./credentials.json

Edit `config.json` so `annotator_id` matches the `Responsible` field of **your own** reviewer records, preferably using pseudonymous values for any public demonstration.

    python -m pip install -r requirements.txt
    streamlit run app.py

The original project used institution-specific access paths, which were deliberately removed for blind review. This interface has not been end-to-end tested against the private data in the uploaded ZIP.
