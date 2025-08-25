# GUI: ODD Data Validation

![Alt text](ui.png?raw=true "GUI: ODD Data Validation")

Follow these steps to run and validate the ODD data.

### Clone this repository
```bash
git clone <this repo>
```

### Change the directory
```bash
cd Data-Labelling-GUI
```

### Install the dependencies
```bash
pip install -r requirements.txt
```

### Configure your user name
Please change you username into the config.json file of this repository(required to allot you your pool of data to be validated). 
```json
{
    "username_thi": "Mittal" // or 'Chouai', 'Klaumann', 'Okumus' 
}
```

### Launch the app from the terminal
```bash
streamlit run app.py
```

## Make sure !!
### You have "credentials.json" into the "GUI" directory required for S3 credentials. (you can download it when you generate a new key/token at s3)
### You have already gone through the instructions on how to label.