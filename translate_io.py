# Take an input with multiple options (3) and translate it to a single output.
# Does this for an entire dictionary of outputs.

from typing import Dict
from collections.abc import Mapping
import json # for reading mapping file
from docxtpl import RichText

def translate_io(input: Dict[str, str], mapping: str) -> Dict[str, str]:
    """
    Translate the input dictionary to the output dictionary using the mapping file.
    Mapping order matters! The first key that matches the input key will be used.
    Avoid duplicate output keys in the mapping file!

    Args:
    input: the input dictionary to translate
    mapping: the file name of the mapping file

    Returns:
    the translated output dictionary
    """
    if not isinstance(mapping, Mapping): # support direct dictionary input (for testing)
        # read the mapping file
        with open(mapping, 'r') as f:
            mapping = json.load(f)

    # translate the input dictionary to the output dictionary
    output = {}
    for outputKey in mapping:                                       # TODO: ensure keys are all lowercase
        for inputKey in mapping[outputKey]:
            if inputKey in input:
                output[outputKey] = str(input[inputKey])
                break
        if outputKey not in output:
            output[outputKey] = "" # default to empty string if no match
    return output

def addRichText(input: Dict[str, str]) -> Dict[str, str]:
    """
    Add RichText to the input dictionary.
    Support bold, italic, underline, and strikethrough.
    Keys name must contain "_bold", "_italic", "_underline", or "_strikethrough", and match another existing key.

    Args:
    input: the input dictionary to add RichText to

    Returns:
    the input dictionary with RichText added
    """
    for key in input:
        if key.endswith("_bold"):
            normalKey = key[:-len("_bold")]
            if normalKey in input:
                input[key] = RichText(input[normalKey], bold=True)
        elif key.endswith("_italic"):
            normalKey = key[:-len("_italic")]
            if normalKey in input:
                input[key] = RichText(input[normalKey], italic=True)
        elif key.endswith("_underline"):
            normalKey = key[:-len("_underline")]
            if normalKey in input:
                input[key] = RichText(input[normalKey], underline=True)
        elif key.endswith("_strikethrough"):
            normalKey = key[:-len("_strikethrough")]
            if normalKey in input:
                input[key] = RichText(input[normalKey], strikethrough=True)
        else:
            input[key] = RichText(input[key])
    return input


#### Testing ####
def test_translate_io():
    print("Testing translate_io.py")
    # test input
    input = {"input2": 2,
             "input3": 3,
             "input3_1": "3_1",
             }
    # test mapping file
    mapping = {"outputKey": ["input1", "input2", "input3"],
               "outputKey2": ["input2_1", "input2_2", "input2_3"],
               "outputKey3": ["input3_1", "input3_2", "input3_3"],
               }
    # expected output
    expected_output = {"outputKey": "2",
                       "outputKey2": "",
                       "outputKey3": "3_1",
                       }
    # test
    output = translate_io(input, mapping)
    if output == expected_output:
        print("translate_io.py passed")
    else:
        print("translate_io.py failed")
        print("Expected:", expected_output)
        print("Output:", output)


#### Main ####
if __name__ == "__main__":
    print("Invoking translate_io.py directly. Running tests:")
    test_translate_io()