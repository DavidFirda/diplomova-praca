import io, contextlib
import builtins
from random import Random
import re

RANDOM_STATE = 82

def capture_output(source_code):
    source_code = "\n".join([
        line for line in source_code.splitlines()
        if not re.match(r"^\s*(import random|from random import)", line)
    ]) 

    buffer = io.StringIO()
    try:
        rnd = Random(RANDOM_STATE) 

        local_env = {
            "__builtins__": builtins.__dict__,
            "random": rnd,
            "shuffle": rnd.shuffle, 
        }

        with contextlib.redirect_stdout(buffer):
            exec(source_code, local_env, {})

        return buffer.getvalue().strip(), None
    except Exception as e:
        return "", str(e)
        

def normalize_output(output):
    return re.sub(r'\s+', '', output).lower().strip()

def extract_numbers(output):
    """ Extrahuje všetky čísla z textu ako floaty """
    return [float(num) for num in re.findall(r'[-+]?\d*\.\d+|\d+', output)]

def floats_close(a, b, tol=1e-2):
    return abs(a - b) < tol

def compare_outputs(student_output, expected_output):
    try:
        student_eval = eval(student_output)
        expected_eval = eval(expected_output)
        return student_eval == expected_eval
    except:
        student_nums = extract_numbers(student_output)
        expected_nums = extract_numbers(expected_output)
        
        if student_nums and expected_nums:
            for s in student_nums:
                if any(floats_close(s, e) for e in expected_nums):
                    return True

        return normalize_output(student_output) == normalize_output(expected_output)