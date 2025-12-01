# my_streamlit
test streamlit deploy


# prepare for run
pip install -r requirements.txt

# setting the folder with following step in Drive:
https://drive.google.com/drive/folders/17qHpIHABuO6pZlq9WJ9GjOKzm9MwsSaV?usp=share_link

# step:
1. add .env file
2. activate virtual environment
    if use the default venv >> On terminal >>pip install -r requirements.txt
    if create new on terminal >>> 1. python -m venv .venv
                      2. for windows OS >> .venv/Scripts/activate
                         for macOS >> source .venv/bin/activate
                      3. pip install -r requirements.txt

3. On terminal >> streamlit run Welcome.py