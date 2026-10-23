import os
import time
import pandas as pd
import json
import streamlit as st

from utils import *


def get_json():
        with open(path_json, 'r') as f:
            json_data = json.load(f)
        return json_data
     
def main(data_csv, config, json_file, save_path, data_path):

    # UI layout
    tab1, tab2 = st.columns([0.7, 0.3], gap="large", vertical_alignment="top", border=True)
    st.title(f"ODD Data Validation") 

    # unpack data
    indexes, data_og = data_csv

    # set session state data
    if 'counter' not in st.session_state: st.session_state.counter = config["last_index"]
    if 'index' not in st.session_state: st.session_state.index = indexes
    if "json_data" not in st.session_state: st.session_state.json_data = data_og
    if "t0" not in st.session_state: st.session_state.t0 = time.time()
    if "frame" not in st.session_state: st.session_state.frame = 0
    if "image_paths" not in st.session_state: st.session_state.image_paths = None
    if "current_token" not in st.session_state: st.session_state.current_token = None
    if not indexes or st.session_state.counter >= len(indexes):
        st.success("All flagged frames have been reviewed.")
        st.stop()
    
    # slider for adjustable json length and image width
    image_width = st.slider("Adjust image width", 100, 2000, config["image_width"])
    json_height = st.slider("Adjust JSON height", 100, 2000, config["json_height"])

    # collect and save the preference from the labeller 
    if image_width or json_height:
        config["image_width"] = image_width
        config["json_height"] = json_height  
    config["last_index"] = st.session_state.counter
    save_json(config, config_path)

    # add the validation status and timining for each sample
    if "Modified" not in st.session_state.json_data.columns:
         st.session_state.json_data["Modified"] = False
         st.session_state.json_data["Visited"] = False
         st.session_state.json_data["time"] = 0.00

    # load next json 
    data = st.session_state.json_data.iloc[st.session_state.index[st.session_state.counter]]
    scene_sample = f"{data['Scene']}__{data['Sample']}"
    data = data.to_dict()
    
    
    # Display the images in first column
    with tab1:
        
        # Display progress
        st.markdown(f"""
        📂Currenty at index: **{st.session_state.counter+1} out of {len(indexes)}** 
        """, unsafe_allow_html=True)

        # Display file info with styled status
        file_visited = data['Visited']
        file_edited = data['Modified']
        st.markdown(f"""
        {"**Visited**: ✅" if file_visited else "**Visited**: ❌"}
        {"**Modified**:  ✅" if file_edited else "**Modified**: ❌"}
        """, unsafe_allow_html=True)

        st.markdown(f"""
        Currently at Frame: **{st.session_state.frame}** 
        """, unsafe_allow_html=True)

        cols = [st.columns(i+1, vertical_alignment = "center") for i in range(2)]
        
        if st.session_state.image_paths is None : st.session_state.image_paths = json_file[scene_sample]['Sample']['ImagePaths']
        if st.session_state.current_token is None :  st.session_state.current_token = json_file[scene_sample]['Sample']['SampleToken']
        
        # do this on "Next Frame" click buttom
        def click_nf():
            next_token = json_file[f"{json_file[scene_sample]['Scene']['SceneToken']}__{st.session_state.current_token}"]['Sample']['NextSampleToken']
            if len(next_token) != 0:
                st.session_state.image_paths = json_file[f"{json_file[scene_sample]['Scene']['SceneToken']}__{next_token}"]['Sample']['ImagePaths']
                st.session_state.current_token = next_token
                st.session_state.frame += 1
        
        # do this on "Previous Frame" click buttom
        def click_pf():
            prev_token = json_file[f"{json_file[scene_sample]['Scene']['SceneToken']}__{st.session_state.current_token}"]["Sample"]["PrevSampleToken"]
            if len(prev_token) != 0:
                st.session_state.image_paths = json_file[f"{json_file[scene_sample]['Scene']['SceneToken']}__{prev_token}"]['Sample']['ImagePaths']
                st.session_state.current_token = prev_token
                st.session_state.frame -= 1 
        
        # do this on "Default Frame" click buttom
        def click_df():
            st.session_state.image_paths = json_file[scene_sample]['Sample']['ImagePaths']
            st.session_state.current_token = json_file[scene_sample]['Sample']['SampleToken']
            st.session_state.frame = 0

        st.button("Next Frame", on_click=click_nf)
        st.button("Previous Frame", on_click=click_pf)
        st.button("Default Frame", on_click=click_df)


        # display images
        with cols[0][0]:
            image_front = st.session_state.image_paths["CAM_FRONT"].replace("./data", data_path)
            st.image(image_front, caption="Front Camera", width = image_width)

        with cols[1][0]:
            image_front_left = st.session_state.image_paths["CAM_FRONT_LEFT"].replace("./data", data_path)
            st.image(image_front_left, caption="Front Left Camera")

        with cols[1][1]:
            image_front_right = st.session_state.image_paths["CAM_FRONT_RIGHT"].replace("./data", data_path)
            st.image(image_front_right, caption="Front Right Camera")
       

    # Display and edit the JSON in second columnn
    with tab2:
        

        with st.container(height=json_height):	
        
            st.write("Please validate the data below:")

            # constanlty dsiplay the data and take user inputs
            edited_data = data_editor(data)
            
        if st.button("Save & Next ➡️"):
                if edited_data != data:
                        edited_data["Modified"]=True
                        edited_data["Visited"]=True
                       
                else:
                    edited_data["Visited"]=True
                   
                # track time per sample
                t1 = time.time()
                t_delta = t1-st.session_state.t0
                edited_data["time"] += t_delta
                st.session_state.t0 = time.time()

                # update the csv file with user modifications
                st.session_state.json_data.iloc[st.session_state.index[st.session_state.counter]] = edited_data
               
                # save to source csv path
                st.session_state.json_data.to_csv(save_path, index=False)
                
                # set the state variables
                st.session_state.counter += 1
                st.session_state.image_paths = None 
                st.session_state.current_token = None
                st.session_state.frame = 0

                if st.session_state.counter >= len(indexes):
                    st.success("🎉 All files have been validated!")
                    save_json(config, config_path)
                    st.stop()
                else:
                  
                  st.rerun()
        if  st.button("⬅️Previous"):
             if st.session_state.counter  > 0:
                st.session_state.counter  += -1
                st.session_state.image_paths = None 
                st.session_state.current_token = None
                st.session_state.frame = 0
             st.session_state.t0 = time.time()
             st.rerun()
        if st.button("Skip"):
            st.session_state.counter  += 1
            st.session_state.image_paths = None 
            st.session_state.current_token = None
            st.session_state.frame = 0
            st.session_state.t0 = time.time()
            st.rerun()
        
        
if __name__ == "__main__":

    st.set_page_config(layout="wide")

    # load config file
    config_path = "./config.json"
    config = load_config()
    
    # load the paths for the data
    path_csv = os.getenv("ODD_FLAGS_CSV")
    path_json = os.getenv("ODD_METADATA_JSON")
    data_path = os.getenv("ODD_IMAGE_ROOT")
    save_path = os.getenv("ODD_FLAGS_OUTPUT_CSV", path_csv)
    if not all([path_csv, path_json, data_path, save_path]):
        st.error("Set ODD_FLAGS_CSV, ODD_METADATA_JSON, and ODD_IMAGE_ROOT.")
        st.stop()

    # load the files
    json_data = get_json()
    annotation_data = get_annotable_samples(path_csv)
    
    main(annotation_data, config, json_data, save_path=save_path, data_path=data_path)
    
