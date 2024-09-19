from docxtpl import DocxTemplate, RichText

# template to use
doc = DocxTemplate("template-test.docx")

# variables to replace in the template
context = { "user": "Ethan Jansen",
            "user_bold": RichText("Ethan Jansen", bold=True),
            "date": "2021<>09<>01",
            "parType": "",
            }
doc.render(context, autoescape=True)

# save the generated document
doc.save("generated-doc.docx")