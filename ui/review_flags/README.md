# Flagged-frame review interface

This Streamlit interface was used to inspect frames flagged by the temporal/semantic checks. The original author-specific filesystem paths have been replaced by configuration variables; private data must be provided locally.

## Local configuration

From this directory, set:

    export ODD_FLAGS_CSV=/path/to/with_semantic_flags.csv
    export ODD_METADATA_JSON=/path/to/extracted_metadata.json
    export ODD_IMAGE_ROOT=/path/to/nuscenes
    export ODD_FLAGS_OUTPUT_CSV=/path/to/flagged_review_output.csv

Then start the existing application:

    python -m pip install -r requirements.txt
    streamlit run app.py

The input CSV must include the check columns used by `get_annotable_samples`. The metadata JSON must contain the scene/sample relationships expected by the app. Make a copy of your own annotations before testing save operations. Source code is supplied, but the original private annotation data was not part of the uploaded archive.
