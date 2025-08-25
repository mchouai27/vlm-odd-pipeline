import os
import json
import streamlit as st
from io import BytesIO
from minio import Minio

def nested_dict_editor(nested_dict, parent_key="", columns=None):
    """Recursively display and edit a nested dictionary."""
    edited_dict = {}
    if columns is None:
        columns = st.columns(2)
    for key, value in nested_dict.items():
        full_key = f"{parent_key}.{key}" if parent_key else key  # Create a unique key for each input
        col = columns[0] if "Scenery" in full_key else columns[1]
        with col:
            if isinstance(value, dict):
                st.write(f"#### {key}")
                edited_dict[key] = nested_dict_editor(value, parent_key=full_key, columns=columns)
                # Recursive call
            else:
                if key in  ["NumberOfLanes", "Comments"]:
                    edited_value = st.text_input(f"{key}", value=str(value), key=full_key)
                elif key in  ["Signs", "TimeOfOperation"]:
                    if len(value)==0: 
                        edited_value = value
                    else:
                        st.write("Part-Time / Full-Time")
                        edited_value = st.data_editor({f"{key}": value}, num_rows="dynamic", key=full_key, hide_index=True)
                        edited_value = edited_value[key]
                              
                elif key == "HorizontalPlane":
                    options = ["Straight", "Curved", ""]
                    if "straight".lower() in value.lower():
                        index = 0
                        options[index] = value
                    elif "Curved".lower() in value.lower():
                        index = 1
                        options[index] = value
                    else: 
                        index=2
                        options[index] = value
                    edited_value =  st.selectbox(
                                                    f"{key}",
                                                    tuple(options),
                                                    index=index,
                                                    key=full_key
                                                )
                elif key == "Visibility":
                    options = ["Light", "Moderate", "Heavy", ""]
                    if "Light".lower() in value.lower():
                        index = 0
                        options[index] = value
                    elif "Moderate".lower() in value.lower():
                        index = 1
                        options[index] = value
                    elif "Heavy".lower() in value.lower():
                        index=2
                        options[index] = value
                    else:
                        index=3
                        options[index] = value
                    
                    edited_value =  st.selectbox(
                                                    f"{key}",
                                                    tuple(options),
                                                    index=index,
                                                    key=full_key
                                                )
                elif key == "TimeOfOperation":
                    options=["Part-Time", "Full-Time", ""]
                    if "Part-Time".lower() in value.lower():
                        index = 0
                        options[index] = value 
                    elif "Full-Time".lower() in value.lower():
                        index = 1
                        options[index] = value 
                    else:
                        index=2
                        options[index] = value
                    edited_value =  st.selectbox(
                                                    f"{key}",
                                                    tuple(options),
                                                    index=index,
                                                    key=full_key
                                                )
                elif key in ["DensityOfAgents", "VolumeOfTraffic"]:
                    options = ["Low", "Medium", "High", ""] 
                    if "Low".lower() in value.lower():
                        index = 0
                        options[index] = value 
                    elif "Medium".lower() in value.lower():
                        index = 1
                        options[index] = value
                    elif "High".lower() in value.lower():
                        index = 2
                        options[index] = value
                    else:
                        index=3
                        options[index] = value
                    edited_value =  st.selectbox(
                                                    f"{key}",
                                                    tuple(options),
                                                    index=index,
                                                    key=full_key
                                                )
        
                elif key == "FlowRate":
                    options=["Smooth", "Congested", ""]
                    if "Smooth".lower() in value.lower():
                        index = 0
                        options[index] = value
                    elif "Congested".lower() in value.lower():
                        index = 1
                        options[index] = value
                    else:
                        index=2
                        options[index] = value
                    edited_value =  st.selectbox(
                                                    f"{key}",
                                                    tuple(options),
                                                    index=index,
                                                    key=full_key
                                                )
                else:
                    value = True if value in ["Yes"]  else False
                    edited_value = st.toggle(label=f"{key}", value=value, key=full_key)
                    edited_value = "Yes" if edited_value else "No"
                try:
                    # Attempt to convert back to original type (int, float, etc.)
                    if value.isdigit():
                        edited_value = str(edited_value)
                    elif value.isnan():
                        edited_value = str(value)
                    else:
                        pass
                except:
                    pass  # Keep it as string if conversion fails
                edited_dict[key] = edited_value
    return edited_dict

def login_to_s3(s3_credentials_json):
    with open(s3_credentials_json, "r") as f:
        secret_keys = json.load(f)

    # Access keys from the .ini file
    MINIO_ACCESS_KEY = secret_keys["accessKey"]
    MINIO_SECRET_KEY = secret_keys["secretKey"]

    client = Minio(
        "s3api.aimotions1.rz.fh-ingolstadt.de",                            
        access_key=MINIO_ACCESS_KEY,                      
        secret_key=MINIO_SECRET_KEY, 
        secure=True
    )
    return client

@st.cache_data
def s3_read_data(_client, bucket_name, object_name):
    """Login to S3 and read data from the bucket."""
    
    #objects = _client.list_objects(bucket_name, recursive=True)
    data = _client.get_object(bucket_name, object_name)
    data = data.read()
    data = json.load(BytesIO(data))
    return data

@st.cache_data
def local_read_data(_client, bucket_name, object_name):
    """Login to S3 and read data from the bucket."""
    d = {}
    with open("./combined_results_with_metadata_test.json",'r') as f:
        data = json.load(f)
    count=0
    for key, val in data.items():
        count+=1
        if count < 250:
            d.update({key:val})
        else:
            break
    return d

@st.cache_data
def load_config(path="./config.json"):
    # load config file
    with open(path, 'r') as c:
        config = json.load(c)
    return config

def save_json(data, path):
    # save config file
    with open(path, 'w') as c:
        json.dump(data, c)   

def save_to_s3(data, client, bucket_name, object_name):
    
    json_bytes = json.dumps(data, indent=4).encode("utf-8")
    json_stream = BytesIO(json_bytes)
    # Save the data to the bucket
    client.put_object(bucket_name, 
                      object_name, 
                      data=json_stream,
                      length=len(json_bytes))

def read_image(client, s3_bucket_name, s3_object_name):
    # read image from s3
    
    # Save the data to the bucket
    image = client.get_object(s3_bucket_name, s3_object_name)
    return image.read()

def download_data(client, local_dir="./"):
    data_path = os.path.join(local_dir, "sets")
    if not os.path.exists(data_path):
            
        bucket_name = 'aimotion-private-panoptic'
        prefix = 'panoptic/data/'  # Folder in the bucket
        
        # List all objects under the 'data' prefix
        objects = client.list_objects(bucket_name, prefix=prefix, recursive=True)
        
        # Download each file
        for obj in objects:
            s3_file_path = obj.object_name
            local_file_path = os.path.join(local_dir, os.path.relpath(s3_file_path, prefix))
        
            # Ensure the local directory structure is replicated
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
        
            # Download file from bucket to local storage
            client.fget_object(bucket_name, s3_file_path, local_file_path)
            print(f"Downloaded {s3_file_path} to {local_file_path}")

@st.cache_data
def get_list(json_data, config):
    user_keys = []
    for key in json_data.keys():
        if json_data[key]["Responsible"] == config["username_thi"]:
            user_keys.append(key)
    return tuple(user_keys)