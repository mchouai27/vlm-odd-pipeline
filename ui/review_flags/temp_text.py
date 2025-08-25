"""
        # Add a button to save the updated dictionary
        if st.button("Save & Next ➡️"):
            
            #print(data["Responsible"])
            if edited_data != data:
                data["Modified"]=True
                data["Visited"]=True
                                    
            else:
                data["Modified"]=False
                data["Visited"]=True
                    
            data.update(edited_data)

            # track time per sample
            t1 = time.time()
            t_delta = t1-st.session_state.t0
            data["time"] += t_delta
            st.session_state.t0 = time.time()

            st.session_state.json_data.iloc[st.session_state.counter] = pd.Series(data)
            
            # save to source csv path
            st.session_state.json_data.to_csv(save_path)   
            
            #save_to_s3(st.session_state.json_data, client, s3_bucket_name, s3_object_name)
            st.session_state.counter += 1
            st.session_state.image_paths = None 
            st.session_state.current_token = None
            st.session_state.frame = 0

            if st.session_state.counter >= len(annotation_data):
                st.success("🎉 All files have been validated!")
                save_json(config, config_path)
                st.stop()
            else:
                #st.rerun()
                pass
                
        if st.button("⬅️Previous"):
            if st.session_state.counter  > 0:
                st.session_state.counter  += -1
                st.session_state.image_paths = None 
                st.session_state.current_token = None
                st.session_state.frame = 0
            st.session_state.t0 = time.time()
            #st.rerun()
        
        if st.button("Skip"):
            st.session_state.counter  += 1
            st.session_state.image_paths = None 
            st.session_state.current_token = None
            st.session_state.frame = 0
            #st.rerun()
        """




"""
        if st.button("Next Frame"):
            next_token = json_file[f"{json_file[scene_sample]["Metadata"]["Scene"]["SceneToken"]}__{st.session_state.current_token}"]['Metadata']['Sample']['NextSampleToken']
            if len(next_token) != 0:
                st.session_state.image_paths = json_file[f"{json_file[scene_sample]["Metadata"]["Scene"]["SceneToken"]}__{next_token}"]['Metadata']['Sample']['ImagePaths']
                st.session_state.current_token = next_token
                st.session_state.frame += 1
            
                #st.rerun()
                
        
        if st.button("Previous Frame"):
            prev_token = json_file[f"{json_file[scene_sample]["Metadata"]["Scene"]["SceneToken"]}__{st.session_state.current_token}"]["Metadata"]["Sample"]["PrevSampleToken"]
            if len(prev_token) != 0:
                st.session_state.image_paths = json_file[f"{json_file[scene_sample]["Metadata"]["Scene"]["SceneToken"]}__{prev_token}"]['Metadata']['Sample']['ImagePaths']
                st.session_state.current_token = prev_token
                st.session_state.frame -= 1
                #st.rerun()
        
        if st.button("Default Frame"):
            st.session_state.image_paths = json_file[scene_sample]['Metadata']['Sample']['ImagePaths']
            st.session_state.current_token = json_file[scene_sample]['Metadata']['Sample']['SampleToken']
            st.session_state.frame = 0
            #st.rerun()
        """