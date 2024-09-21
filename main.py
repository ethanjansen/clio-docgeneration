# Main for docGeneration/main.py:
from translate_io import translate_io
from doc import generate_doc

#### Functions ####
def main():
    print("Running proof of concept")

    # run test1
    input = {"username": "Ethan Jansen",
             "person": "Not Ethan Jansen",
             "date": "2021-09-01",
             "par_type": "",
             }
    generate_doc("test1_template.docx", "test1_generated.docx", translate_io(input, "test1_mapping.json"))


#### Main ####
if __name__ == "__main__":
    main()