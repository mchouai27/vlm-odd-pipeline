import time
import streamlit as st

from utils import *


def main(client, json_data, files, config):

    # UI layout
    tab1, tab2 = st.columns([0.7, 0.3], gap="large", vertical_alignment="top", border=True)
    st.title(f"ODD Data Validation") 

    # set session state data
    if 'counter' not in st.session_state: st.session_state.counter = config["last_index"]
    if "json_data" not in st.session_state: st.session_state.json_data = json_data
    if "t0" not in st.session_state: st.session_state.t0 = time.time()
    
    # slider for adjustable json length and image width
    image_width = st.slider("Adjust image width", 100, 2000, config["image_width"])
    json_height = st.slider("Adjust JSON height", 100, 2000, config["json_height"])

    # collect and save the preference from the labeller 
    if image_width or json_height:
        config["image_width"] = image_width
        config["json_height"] = json_height  
    config["last_index"] = st.session_state.counter
    save_json(config, config_path)

    # load next json 
    data = st.session_state.json_data[files[st.session_state.counter]]

    # add and track additional variables
    if "Status" not in data.keys():
        data.update({"Status": {
                            "Modified": False,
                            "Visited": False,
                            "time":0
                    }})
        data.update({"Comments": "Write your comment here.."}) 
    editable_keys = ['Scenery', 'EnvironmentalConditions', 'DynamicElements', 'Comments']
    data_editable = {key:value for key, value in data.items() if key in editable_keys}

    # Display the images in first column
    with tab1:
        
        # Display progress
        st.markdown(f"""
        📂Currenty at index: **{st.session_state.counter+1} out of {len(files)}** 
        """, unsafe_allow_html=True)

        # Display file info with styled status
        file_visited = data['Status']['Visited']
        file_edited = data['Status']['Modified']
        st.markdown(f"""
        {"**Visited**: ✅" if file_visited else "**Visited**: ❌"}
        {"**Modified**:  ✅" if file_edited else "**Modified**: ❌"}
        """, unsafe_allow_html=True)

        image_paths = data['Metadata']['Sample']['ImagePaths']
        image_paths = {key:value.replace("s3://aimotion-private-panoptic/", "") for key, value in image_paths.items()}
        cols = [st.columns(i+1, vertical_alignment = "center") for i in range(2)]

        # display images
        with cols[0][0]:
            image_front = read_image( client, s3_bucket_name, s3_object_name=image_paths["CAM_FRONT"])
            st.image(image_front, caption="Front Camera", width = image_width)

        with cols[1][0]:
            image_front_left = read_image(client, s3_bucket_name, s3_object_name=image_paths["CAM_FRONT_LEFT"])
            st.image(image_front_left, caption="Front Left Camera")

        with cols[1][1]:
            image_front_right = read_image(client, s3_bucket_name, s3_object_name=image_paths["CAM_FRONT_RIGHT"])
            st.image(image_front_right, caption="Front Right Camera")
    
    # Display and edit the JSON in second columnn
    with tab2:
        with st.container(height=json_height):	
        
            st.write("Please validate the data below:")
            edited_data = nested_dict_editor(data_editable)
        
        # Add a button to save the updated dictionary
        if st.button("Save & Next ➡️"):
            
            print(data["Responsible"])
            if edited_data != data_editable:
                data["Status"]["Modified"]=True
                data["Status"]["Visited"]=True
                                    
            
            else:
                data["Status"]["Modified"]=False
                data["Status"]["Visited"]=True
                    
            data.update(edited_data)

            # track time per sample
            t1 = time.time()
            t_delta = t1-st.session_state.t0
            data["Status"]["time"] += t_delta
            st.session_state.t0 = time.time()

            st.session_state.json_data[files[st.session_state.counter]].update(data)
            
            save_to_s3(st.session_state.json_data, client, s3_bucket_name, s3_object_name)
            st.session_state.counter += 1
            
            if st.session_state.counter >= len(files):
                st.success("🎉 All files have been validated!")
                save_json(config, config_path)
                st.stop()
            else:
                st.rerun()
                
        if st.button("⬅️Previous"):
            if st.session_state.counter  > 0:
                st.session_state.counter  += -1
            st.session_state.t0 = time.time()
            st.rerun()
        
        if st.button("Skip"):
            st.session_state.counter  += 1
            st.rerun()

if __name__ == "__main__":

    secret_keys_path = "./credentials.json"
    config_path = "./config.json"
    s3_object_name = "JSON_Files/extracted_samples_with_responsible.json"
    s3_bucket_name = "aimotion-private-panoptic"

    st.set_page_config(layout="wide")
    client = login_to_s3(secret_keys_path)
    config = load_config()
    json_data = s3_read_data(client, s3_bucket_name, s3_object_name)
    files = get_list(json_data, config)

    main(client, json_data, files, config)
    