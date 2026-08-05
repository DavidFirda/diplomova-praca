import re

def extract_starter_code(output_code: str) -> str:
    lines = output_code.strip().splitlines()
    starter = []
    top_prints = []
    found_def = False
    has_non_print_logic = False
    has_only_top_print = True

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("import") or stripped.startswith("from"):
            starter.append(line)
            has_non_print_logic = True
            has_only_top_print = False
        
        if stripped.startswith("def") and not found_def:
            starter.append(line)
            starter.append("    pass")
            found_def = True
            has_non_print_logic = True
            has_only_top_print = False
        
        if "print" in line and "print(" in line:
            indent = len(line) - len(line.lstrip())
            if indent == 0:
                paren_count = 0
                start = line.find("print(")
                i = start
                while i < len(line):
                    if line[i] == '(':
                        paren_count += 1
                    elif line[i] == ')':
                        paren_count -= 1
                        if paren_count == 0:
                            break
                    i += 1
                full_expr = line[start:i+1] if paren_count == 0 else line[start:]
                top_prints.append(full_expr)

        if stripped and not stripped.startswith("#") and not re.match(r'^\s*print\s*\(.*\)\s*$', line):
            has_non_print_logic = True

    if has_only_top_print and top_prints:
        return "print(...)"

    if has_non_print_logic and top_prints:
        starter.append("")  
        starter.extend(top_prints)    

    return "\n".join(starter)