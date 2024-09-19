from docxtpl import DocxTemplate, RichText

######## Functions ########
def generate_doc(templateDocx: str, outputDocx: str, context: dict) -> None:
    # template to use
    doc = DocxTemplate(templateDocx)

    # variables to replace in the template
    doc.render(context, autoescape=True)

    # save the generated document
    doc.save(outputDocx)



####### Tests #######
def test_doc():
    print("Testing doc.py")
    # variables to replace in test1-template.docx
    context1 = { "user": "Ethan Jansen",
                "user_bold": RichText("Ethan Jansen", bold=True),
                "date": "2021<>09<>01",
                "parType": "",
                }
    generate_doc("test1_template.docx", "test1_generated.docx", context1)


####### Main #######
if __name__ == "__main__":
    print("Invoking doc.py directly. Running tests:")
    test_doc()