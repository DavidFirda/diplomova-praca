import os
import sys
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
from app import app
from models import db, Question

with app.app_context():
    # Ak už databáza obsahuje otázky, nepridávaj znova
    if Question.query.first():
        print("📦 Otázky už existujú v databáze. Preskakujem načítanie.")
    else:
        # Načítaj CSV
        df = pd.read_csv("final_dataset.csv")

        for _, row in df.iterrows():
            question = Question(
                id=int(row["ID"]),
                instruction=row["Instruction"],
                input_data=str(row["Input"]),
                output=row["Output"],
                category=row["Category"],
                subcategory=row["Subcategory"],
                incorrect_output=row["IncorrectOutput"]
            )
            db.session.add(question)

        db.session.commit()
        print("✅ Otázky úspešne načítané do databázy.")   